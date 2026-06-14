"""Envoltura sencilla del binario rclone (incluido en la imagen)."""
from __future__ import annotations

import subprocess
from typing import Any

from . import config


def _base() -> list[str]:
    return ["rclone", "--config", config.RCLONE_CONF]


def available() -> bool:
    try:
        subprocess.run(["rclone", "version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def list_remotes() -> list[str]:
    try:
        out = subprocess.run(
            _base() + ["listremotes"], capture_output=True, text=True, timeout=15
        )
        return [r.strip().rstrip(":") for r in out.stdout.splitlines() if r.strip()]
    except Exception:
        return []


def create_remote(name: str, rtype: str, params: dict[str, str]) -> tuple[bool, str]:
    """Crea un remote nuevo (no interactivo). Para OAuth (OneDrive/Drive) hace falta
    un token ya obtenido; se pasa en params como 'token'."""
    cmd = _base() + ["config", "create", name, rtype]
    for k, v in params.items():
        cmd += [k, v]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ok = out.returncode == 0
        return ok, (out.stdout + out.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def copy_file(src: str, dest: str) -> tuple[bool, str]:
    """Sube un archivo a 'dest' (remote:ruta o ruta local)."""
    cmd = _base() + ["copyto", src, dest, "--stats-one-line"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        return out.returncode == 0, (out.stdout + out.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def delete_old(dest_dir: str, min_age: str) -> str:
    """Borra del destino lo más viejo que 'min_age' (ej '7d'). Rotación."""
    try:
        out = subprocess.run(
            _base() + ["delete", dest_dir, "--min-age", min_age],
            capture_output=True, text=True, timeout=600,
        )
        subprocess.run(
            _base() + ["rmdirs", dest_dir, "--leave-root"],
            capture_output=True, text=True, timeout=120,
        )
        return (out.stdout + out.stderr).strip()
    except Exception as exc:
        return str(exc)


def list_files(dest_dir: str) -> list[dict[str, Any]]:
    import json
    try:
        out = subprocess.run(
            _base() + ["lsjson", dest_dir], capture_output=True, text=True, timeout=60
        )
        if out.returncode == 0:
            return json.loads(out.stdout)
    except Exception:
        pass
    return []
