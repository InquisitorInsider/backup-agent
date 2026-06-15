"""Autoescaneo del servidor: volúmenes Docker, contenedores, bases de datos,
stacks de compose y configuración de OMV.

Devuelve un inventario y una 'selección recomendada' para pre-marcar el panel.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

from . import config

try:
    import docker  # type: ignore
except Exception:  # pragma: no cover
    docker = None


# Imágenes que delatan una base de datos y cómo volcarla.
_DB_HINTS = {
    "postgres": "postgres",
    "mariadb": "mysql",
    "mysql": "mysql",
}

# Volúmenes que normalmente son DATOS PESADOS (no recomendados por defecto).
_HEAVY_HINTS = ("media", "movies", "tv", "downloads", "jellyfin", "plex", "nextcloud_data")


def _client():
    if docker is None:
        raise RuntimeError("La librería docker no está disponible")
    return docker.from_env()


def _dir_size(path: str, timeout: int = 8) -> str:
    """Tamaño rápido de una carpeta con du; si tarda, devuelve '?'."""
    try:
        out = subprocess.run(
            ["du", "-sh", path], capture_output=True, text=True, timeout=timeout
        )
        if out.returncode == 0:
            return out.stdout.split("\t")[0].strip()
    except Exception:
        pass
    return "?"


def _db_from_env(env: list[str], kind: str) -> dict[str, str]:
    """Extrae usuario/clave/base de las variables de entorno del contenedor."""
    e = {}
    for item in env or []:
        if "=" in item:
            k, v = item.split("=", 1)
            e[k] = v
    if kind == "postgres":
        return {
            "engine": "postgres",
            "user": e.get("POSTGRES_USER", "postgres"),
            "password": e.get("POSTGRES_PASSWORD", ""),
            "database": e.get("POSTGRES_DB", e.get("POSTGRES_USER", "postgres")),
        }
    # mysql / mariadb
    return {
        "engine": "mysql",
        "user": e.get("MYSQL_USER", "root"),
        "password": e.get("MYSQL_PASSWORD", e.get("MYSQL_ROOT_PASSWORD", "")),
        "database": e.get("MYSQL_DATABASE", ""),
    }


def scan() -> dict[str, Any]:
    inv: dict[str, Any] = {
        "omv": {"available": False},
        "system_identities": {"available": False},
        "volumes": [],
        "databases": [],
        "compose_roots": [],
        "stacks": [],
        "containers": [],
        "errors": [],
    }

    # --- OMV config ---
    cfg = os.path.join(config.OMV_CONFIG_DIR, "config.xml")
    if os.path.exists(cfg):
        try:
            size = os.path.getsize(cfg)
        except OSError:
            size = 0
        inv["omv"] = {"available": True, "path": cfg, "size_kb": round(size / 1024, 1)}

    # --- Docker: contenedores, volúmenes, bases ---
    try:
        cli = _client()
    except Exception as exc:
        inv["errors"].append(f"Docker no accesible: {exc}")
        cli = None

    db_volume_names: set[str] = set()
    if cli is not None:
        # Contenedores + detección de bases
        for c in cli.containers.list(all=True):
            image = (c.image.tags[0] if c.image.tags else c.attrs.get("Config", {}).get("Image", "")) or ""
            status = c.status
            inv["containers"].append({"name": c.name, "image": image, "status": status})
            kind = None
            for hint, k in _DB_HINTS.items():
                if hint in image.lower():
                    kind = k
                    break
            if kind and status == "running":
                env = c.attrs.get("Config", {}).get("Env", [])
                creds = _db_from_env(env, kind)
                # localizar el volumen de datos de la base (para no duplicarlo en bruto)
                for m in c.attrs.get("Mounts", []):
                    if m.get("Type") == "volume" and m.get("Name"):
                        db_volume_names.add(m["Name"])
                inv["databases"].append({
                    "key": f"{c.name}/{creds['database'] or kind}",
                    "container": c.name,
                    "engine": creds["engine"],
                    "user": creds["user"],
                    "database": creds["database"],
                    "has_password": bool(creds["password"]),
                    "recommended": True,
                })

        # Volúmenes
        for v in cli.volumes.list():
            name = v.name
            mp = v.attrs.get("Mountpoint", "")
            size = _dir_size(mp) if mp and os.path.isdir(mp) else "?"
            low = name.lower()
            heavy = any(h in low for h in _HEAVY_HINTS)
            anon = len(name) >= 60 and all(ch in "0123456789abcdef" for ch in name)
            is_db = name in db_volume_names
            # Recomendado: volúmenes con nombre, no pesados. Las bases con nombre van
            # por dump, así que su volumen NO se recomienda en bruto.
            recommended = (not heavy) and (not anon) and (not is_db)
            inv["volumes"].append({
                "name": name,
                "size": size,
                "mountpoint": mp,
                "anonymous": anon,
                "is_database": is_db,
                "heavy": heavy,
                "recommended": recommended,
            })

    # --- Stacks de compose (listados uno por uno) ---
    running = {c.name for c in (cli.containers.list() if cli is not None else [])} \
        if cli is not None else set()
    for root in config.COMPOSE_ROOTS:
        if not os.path.isdir(root):
            continue
        names = []
        try:
            for entry in sorted(os.listdir(root)):
                d = os.path.join(root, entry)
                if not os.path.isdir(d):
                    continue
                if any(f.endswith((".yml", ".yaml")) for f in os.listdir(d)):
                    names.append(entry)
                    inv["stacks"].append({
                        "name": entry,
                        "path": d,
                        "root": root,
                        "recommended": True,
                    })
        except OSError as exc:
            inv["errors"].append(f"No se pudo leer {root}: {exc}")
        inv["compose_roots"].append({
            "path": root, "stacks": names, "recommended": True,
        })

    # --- Identidades del sistema (usuarios/contraseñas/Samba) ---
    files = []
    for f in ("passwd", "shadow", "group", "gshadow"):
        if os.path.exists(os.path.join(config.SYS_ETC_DIR, f)):
            files.append("/etc/" + f)
    if os.path.isdir(os.path.join(config.SYS_ETC_DIR, "samba")):
        files.append("/etc/samba")
    if os.path.isdir(config.SAMBA_DIR):
        files.append("/var/lib/samba")
    inv["system_identities"] = {"available": bool(files), "items": files}

    return inv
