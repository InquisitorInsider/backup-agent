"""backup-agent — panel web y API para respaldar tu servidor OMV.

Autoescaneo de lo que hay (config OMV, volúmenes, bases, stacks de compose),
selección por casillas, destinos (OneDrive/rclone o carpeta local), programación
diaria, respaldo manual e historial.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from . import backup, config, rclone, scan, scheduler, settings, ui

app = FastAPI(title="backup-agent", version=config.VERSION, docs_url="/docs")
_basic = HTTPBasic(auto_error=False)


def require_admin(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not config.ADMIN_PASSWORD:
        return
    ok = (
        creds is not None
        and secrets.compare_digest(creds.username, config.ADMIN_USER)
        and secrets.compare_digest(creds.password, config.ADMIN_PASSWORD)
    )
    if not ok:
        raise HTTPException(
            status_code=401, detail="No autorizado",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.on_event("startup")
def _startup() -> None:
    scheduler.start()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": config.VERSION,
        "rclone": rclone.available(),
        "running": backup.is_running(),
    }


@app.get("/", response_class=HTMLResponse)
def index(_: None = Depends(require_admin)) -> str:
    return ui.PAGE


@app.get("/api/scan")
def api_scan(_: None = Depends(require_admin)) -> dict[str, Any]:
    return scan.scan()


@app.get("/api/settings")
def api_get_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    return settings.load()


class SettingsIn(BaseModel):
    include_omv_config: bool | None = None
    include_manifest: bool | None = None
    volumes: list[str] | None = None
    compose_roots: list[str] | None = None
    databases: list[str] | None = None
    destinations: list[dict[str, Any]] | None = None
    schedule: dict[str, Any] | None = None


@app.post("/api/settings")
def api_save_settings(body: SettingsIn, _: None = Depends(require_admin)) -> dict[str, Any]:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    return settings.save(data)


@app.get("/api/remotes")
def api_remotes(_: None = Depends(require_admin)) -> dict[str, Any]:
    return {"remotes": rclone.list_remotes(), "rclone": rclone.available()}


class RemoteIn(BaseModel):
    name: str
    type: str                       # ej: onedrive, drive, s3
    params: dict[str, str] = {}


@app.post("/api/remotes")
def api_create_remote(body: RemoteIn, _: None = Depends(require_admin)) -> dict[str, Any]:
    ok, msg = rclone.create_remote(body.name, body.type, body.params)
    return {"ok": ok, "msg": msg}


@app.post("/api/backup/run")
def api_run(_: None = Depends(require_admin)) -> dict[str, Any]:
    if backup.is_running():
        return {"ok": False, "error": "Ya hay un respaldo en curso"}
    import threading
    threading.Thread(target=backup.run_backup, kwargs={"trigger": "manual"}, daemon=True).start()
    return {"ok": True, "started": True}


@app.get("/api/status")
def api_status(_: None = Depends(require_admin)) -> dict[str, Any]:
    return {
        "running": backup.is_running(),
        "next_run": scheduler.next_run(),
    }


@app.get("/api/history")
def api_history(_: None = Depends(require_admin)) -> list[dict[str, Any]]:
    return settings.history()


@app.get("/api/logs", response_class=PlainTextResponse)
def api_logs(_: None = Depends(require_admin)) -> str:
    return settings.read_log(300)
