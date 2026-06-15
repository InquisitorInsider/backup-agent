"""Ejecuta el respaldo según la configuración guardada."""
from __future__ import annotations

import os
import shutil
import tarfile
import threading
from datetime import datetime
from typing import Any

from . import config, rclone, scan, settings

try:
    import docker  # type: ignore
except Exception:  # pragma: no cover
    docker = None

_RUN_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"running": False, "started": None}


def is_running() -> bool:
    return _STATE["running"]


# Carpetas que NUNCA se recorren (datos pesados de los stacks: medios, cachés,
# metadatos de Plex/Jellyfin, instalación de Nextcloud, descargas, etc.).
_SKIP_DIRS = {
    "data", "_data", "config", "cache", "caches", "metadata", "media", "movies",
    "tv", "series", "music", "downloads", "download", "incomplete", "transcode",
    "transcodes", "thumbnails", "previews", "node_modules", "logs", "log",
    "appdata", "html", "www", "vendor", "backups", "backup", "db-data", "postgres",
}
# Solo se copian archivos de DEFINICIÓN/configuración (no datos).
_DEF_EXT = (".yml", ".yaml", ".env", ".conf", ".cfg", ".ini", ".toml", ".json",
            ".sh", ".dockerfile", ".xml", ".txt", ".md", ".service")
_DEF_NAMES = ("dockerfile", "caddyfile", ".env", "compose.override.yml")


def _copy_compose(root: str, dest: str) -> None:
    """Copia SOLO las definiciones/configs de los stacks (no sus datos).
    Poda carpetas pesadas, limita la profundidad y aplica un tope de archivos
    para que nunca pueda colgarse aunque un stack tenga datos enormes dentro."""
    small_cap = 5 * 1024 * 1024          # 5 MB por archivo de config
    max_files = 3000                      # tope duro de seguridad
    copied = 0
    root_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip("/").count("/") - root_depth
        # podar: nada de carpetas pesadas, ocultas, ni bajar más de 3 niveles
        if depth >= 3:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
        rel = os.path.relpath(dirpath, root)
        target_dir = os.path.join(dest, rel) if rel != "." else dest
        for f in filenames:
            low = f.lower()
            if not (low.endswith(_DEF_EXT) or low in _DEF_NAMES):
                continue
            src = os.path.join(dirpath, f)
            try:
                if os.path.islink(src) or os.path.getsize(src) > small_cap:
                    continue
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(target_dir, f))
                copied += 1
                if copied >= max_files:
                    settings.log(f"  aviso: tope de {max_files} archivos en {root}; corto aquí")
                    return
            except OSError:
                continue
    # Rescate de archivos importantes que viven dentro de carpetas podadas
    # (ej. el config.php de Nextcloud, en <stack>/html/config/config.php).
    import glob
    for pat in ("*/html/config/config.php", "*/config/config.php", "*/.env"):
        for src in glob.glob(os.path.join(root, pat)):
            try:
                if os.path.getsize(src) > small_cap:
                    continue
                rel = os.path.relpath(os.path.dirname(src), root)
                td = os.path.join(dest, rel)
                os.makedirs(td, exist_ok=True)
                shutil.copy2(src, os.path.join(td, os.path.basename(src)))
                copied += 1
            except OSError:
                continue
    settings.log(f"  compose: {copied} archivos de definición/config copiados de {root}")


def _dump_database(cli, key: str, dest_dir: str) -> bool:
    """Vuelca una base por dump lógico vía docker exec. Lee credenciales del
    entorno del contenedor en caliente (no se guardan en disco)."""
    container_name = key.split("/", 1)[0]
    try:
        c = cli.containers.get(container_name)
    except Exception:
        settings.log(f"  base: contenedor {container_name} no encontrado")
        return False
    image = (c.image.tags[0] if c.image.tags else "").lower()
    env = c.attrs.get("Config", {}).get("Env", [])
    e = {x.split("=", 1)[0]: x.split("=", 1)[1] for x in env if "=" in x}

    if "postgres" in image:
        user = e.get("POSTGRES_USER", "postgres")
        db = e.get("POSTGRES_DB", user)
        pwd = e.get("POSTGRES_PASSWORD", "")
        cmd = ["pg_dump", "-U", user, "-d", db]
        envv = {"PGPASSWORD": pwd}
        out_name = f"{container_name}_{db}.sql"
    else:  # mariadb / mysql
        user = e.get("MYSQL_USER", "root")
        db = e.get("MYSQL_DATABASE", "")
        pwd = e.get("MYSQL_PASSWORD", e.get("MYSQL_ROOT_PASSWORD", ""))
        tool = "mysqldump"
        chk = c.exec_run(["sh", "-c", "command -v mysqldump || command -v mariadb-dump"])
        if b"mariadb-dump" in (chk.output or b"") and b"mysqldump" not in (chk.output or b""):
            tool = "mariadb-dump"
        cmd = [tool, "-u", user, "--single-transaction", db]
        envv = {"MYSQL_PWD": pwd}
        out_name = f"{container_name}_{db or 'db'}.sql"

    try:
        res = c.exec_run(cmd, environment=envv, demux=True)
        stdout, stderr = res.output if isinstance(res.output, tuple) else (res.output, b"")
        if res.exit_code != 0 or not stdout:
            settings.log(f"  base {key}: error en dump ({(stderr or b'').decode(errors='ignore')[:120]})")
            return False
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, out_name), "wb") as fh:
            fh.write(stdout)
        settings.log(f"  base ok: {out_name}")
        return True
    except Exception as exc:
        settings.log(f"  base {key}: excepción {exc}")
        return False


def _destination_target(dest: dict[str, Any], filename: str) -> tuple[str, str]:
    """Devuelve (ruta_destino_archivo, carpeta_destino) para copiar y rotar."""
    path = dest.get("path", "").strip("/")
    if dest["type"] == "local":
        folder = os.path.join(config.LOCAL_DEST_DIR, path) if path else config.LOCAL_DEST_DIR
        return os.path.join(folder, filename), folder
    remote = dest["remote"].rstrip(":")
    folder = f"{remote}:{path}" if path else f"{remote}:"
    return f"{folder}/{filename}", folder


def run_backup(trigger: str = "manual") -> dict[str, Any]:
    if not _RUN_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Ya hay un respaldo en curso"}
    _STATE["running"] = True
    _STATE["started"] = datetime.now().isoformat(timespec="seconds")
    started = datetime.now()
    cfg = settings.load()
    fecha = started.strftime("%Y%m%d-%H%M")
    work = os.path.join(config.DATA_DIR, "work")
    stage = os.path.join(work, f"omv-{fecha}")
    archive = os.path.join(work, f"omv-respaldo-{fecha}.tar.gz")
    result: dict[str, Any] = {"ok": False, "fecha": fecha, "trigger": trigger, "destinos": []}

    try:
        settings.log(f"==== inicio respaldo ({trigger}) ====")
        if os.path.exists(work):
            shutil.rmtree(work, ignore_errors=True)
        os.makedirs(stage, exist_ok=True)

        cli = None
        if docker is not None:
            try:
                cli = docker.from_env()
            except Exception as exc:
                settings.log(f"Docker no accesible: {exc}")

        # 1) config OMV
        if cfg.get("include_omv_config") and os.path.isdir(config.OMV_CONFIG_DIR):
            settings.log("copiando config de OMV...")
            shutil.copytree(config.OMV_CONFIG_DIR, os.path.join(stage, "etc-openmediavault"),
                            dirs_exist_ok=True, ignore_dangling_symlinks=True)

        # 2) manifiesto
        if cfg.get("include_manifest"):
            man = os.path.join(stage, "MANIFIESTO")
            os.makedirs(man, exist_ok=True)
            inv = scan.scan()
            import json
            with open(os.path.join(man, "inventario.json"), "w", encoding="utf-8") as fh:
                json.dump(inv, fh, ensure_ascii=False, indent=2)

        # 3) compose: preferir stacks individuales; si no, raíces completas
        stacks_sel = cfg.get("compose_stacks", [])
        if stacks_sel:
            for sp in stacks_sel:
                if os.path.isdir(sp):
                    settings.log(f"copiando stack: {os.path.basename(sp)}")
                    _copy_compose(sp, os.path.join(stage, "compose", os.path.basename(sp)))
        else:
            for root in cfg.get("compose_roots", []):
                if os.path.isdir(root):
                    settings.log(f"copiando compose: {root}")
                    base = root.strip("/").replace("/", "_")
                    _copy_compose(root, os.path.join(stage, "compose", base))

        # 3b) identidades del sistema (usuarios/contraseñas/Samba) — opt-in
        if cfg.get("include_system_identities"):
            settings.log("copiando identidades del sistema (usuarios/Samba)...")
            ident = os.path.join(stage, "identidades")
            os.makedirs(ident, exist_ok=True)
            for f in ("passwd", "shadow", "group", "gshadow"):
                src = os.path.join(config.SYS_ETC_DIR, f)
                if os.path.exists(src):
                    try:
                        shutil.copy2(src, os.path.join(ident, f))
                    except OSError as exc:
                        settings.log(f"  {f}: {exc}")
            for sub, dst in ((os.path.join(config.SYS_ETC_DIR, "samba"), "etc-samba"),
                             (config.SAMBA_DIR, "var-lib-samba")):
                if os.path.isdir(sub):
                    try:
                        shutil.copytree(sub, os.path.join(ident, dst),
                                        dirs_exist_ok=True, ignore_dangling_symlinks=True)
                    except OSError as exc:
                        settings.log(f"  {dst}: {exc}")

        # 4) volúmenes seleccionados
        if cli is not None and cfg.get("volumes"):
            for vname in cfg["volumes"]:
                try:
                    v = cli.volumes.get(vname)
                    mp = v.attrs.get("Mountpoint", "")
                    if mp and os.path.isdir(mp):
                        settings.log(f"copiando volumen: {vname}")
                        shutil.copytree(mp, os.path.join(stage, "volumenes", vname),
                                        dirs_exist_ok=True, ignore_dangling_symlinks=True)
                except Exception as exc:
                    settings.log(f"  volumen {vname}: {exc}")

        # 5) bases de datos seleccionadas (dump)
        if cli is not None and cfg.get("databases"):
            for key in cfg["databases"]:
                _dump_database(cli, key, os.path.join(stage, "bases"))

        # 6) empaquetar
        settings.log("empaquetando...")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(stage, arcname=os.path.basename(stage))
        size_mb = round(os.path.getsize(archive) / (1024 * 1024), 1)
        result["size_mb"] = size_mb
        settings.log(f"paquete: {os.path.basename(archive)} ({size_mb} MB)")

        # 7) subir a cada destino + rotación
        dests = [d for d in cfg.get("destinations", []) if d.get("enabled", True)]
        if not dests:
            settings.log("AVISO: no hay destinos configurados; el paquete queda solo local en /data/work")
        retention = f"{int(cfg.get('schedule', {}).get('retention_days', 7))}d"
        for d in dests:
            target, folder = _destination_target(d, os.path.basename(archive))
            settings.log(f"subiendo a [{d.get('id', d['type'])}] {folder} ...")
            ok, msg = rclone.copy_file(archive, target)
            rot = rclone.delete_old(folder, retention) if ok else "(omitida)"
            result["destinos"].append({"destino": d.get("id", d["type"]), "ok": ok, "msg": msg[:200]})
            settings.log(f"  {'OK' if ok else 'ERROR'} {msg[:160]}")
            settings.log(f"  rotación {retention}: {rot[:120]}")

        result["ok"] = all(x["ok"] for x in result["destinos"]) if dests else True

    except Exception as exc:
        settings.log(f"ERROR general: {exc}")
        result["error"] = str(exc)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        dur = (datetime.now() - started).total_seconds()
        result["segundos"] = round(dur, 1)
        result["timestamp"] = datetime.now().isoformat(timespec="seconds")
        settings.add_history(result)
        settings.log(f"==== fin respaldo ({'OK' if result['ok'] else 'con errores'}, {dur:.0f}s) ====")
        _STATE["running"] = False
        _RUN_LOCK.release()
    return result
