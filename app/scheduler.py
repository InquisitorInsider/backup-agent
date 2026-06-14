"""Programador interno: dispara el respaldo a la hora configurada (diario)."""
from __future__ import annotations

import threading
import time
from datetime import datetime

from . import backup, settings

_THREAD: threading.Thread | None = None
_LAST_RUN_DATE: str | None = None


def _loop() -> None:
    global _LAST_RUN_DATE
    settings.log("programador iniciado")
    while True:
        try:
            cfg = settings.load().get("schedule", {})
            if cfg.get("enabled"):
                now = datetime.now()
                hhmm = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")
                if hhmm == cfg.get("time", "03:30") and _LAST_RUN_DATE != today:
                    _LAST_RUN_DATE = today
                    if not backup.is_running():
                        settings.log(f"disparo programado {hhmm}")
                        backup.run_backup(trigger="programado")
        except Exception as exc:  # nunca matar el hilo
            settings.log(f"programador: error {exc}")
        time.sleep(30)


def start() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(target=_loop, daemon=True, name="scheduler")
    _THREAD.start()


def next_run() -> str | None:
    cfg = settings.load().get("schedule", {})
    if not cfg.get("enabled"):
        return None
    return cfg.get("time", "03:30")
