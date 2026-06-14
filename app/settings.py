"""Persistencia de la configuración del usuario (selección, destinos, horario).

Se guarda en DATA_DIR/settings.json. También maneja historial y logs simples.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any

from . import config

_LOCK = threading.Lock()

SETTINGS_PATH = os.path.join(config.DATA_DIR, "settings.json")
HISTORY_PATH = os.path.join(config.DATA_DIR, "history.json")
LOG_PATH = os.path.join(config.DATA_DIR, "backup.log")

DEFAULTS: dict[str, Any] = {
    # Qué respaldar
    "include_omv_config": True,
    "include_manifest": True,
    "volumes": [],          # nombres de volúmenes Docker seleccionados
    "compose_roots": [],     # raíces de compose seleccionadas (de config.COMPOSE_ROOTS)
    "databases": [],         # claves "contenedor/base" seleccionadas
    # A dónde respaldar: lista de destinos
    # cada uno: {"id":..., "type":"rclone"|"local", "remote":"onedrive_restaurante",
    #            "path":"Respaldos/omv", "enabled":true}
    "destinations": [],
    # Programación
    "schedule": {"enabled": False, "time": "03:30", "retention_days": 7},
}


def _ensure_dir() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)


def load() -> dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(SETTINGS_PATH):
        return json.loads(json.dumps(DEFAULTS))
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULTS))
    # completar claves faltantes
    merged = json.loads(json.dumps(DEFAULTS))
    merged.update(data)
    return merged


def save(data: dict[str, Any]) -> dict[str, Any]:
    _ensure_dir()
    with _LOCK:
        current = load()
        current.update(data)
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(current, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_PATH)
    return current


# ---------------- Historial ----------------
def history() -> list[dict[str, Any]]:
    _ensure_dir()
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []


def add_history(entry: dict[str, Any]) -> None:
    _ensure_dir()
    with _LOCK:
        items = history()
        items.insert(0, entry)
        items = items[:50]  # conservar los últimos 50
        tmp = HISTORY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_PATH)


# ---------------- Log simple ----------------
def log(msg: str) -> None:
    _ensure_dir()
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    with _LOCK:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        # recortar el log si crece mucho
        try:
            if os.path.getsize(LOG_PATH) > 512 * 1024:
                with open(LOG_PATH, encoding="utf-8") as fh:
                    tail = fh.readlines()[-1000:]
                with open(LOG_PATH, "w", encoding="utf-8") as fh:
                    fh.writelines(tail)
        except OSError:
            pass
    print(line, flush=True)


def read_log(lines: int = 200) -> str:
    if not os.path.exists(LOG_PATH):
        return ""
    try:
        with open(LOG_PATH, encoding="utf-8") as fh:
            return "".join(fh.readlines()[-lines:])
    except OSError:
        return ""
