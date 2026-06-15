"""Configuración por variables de entorno del backup-agent."""
from __future__ import annotations

import os

# --- Acceso al panel ---
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # vacío = sin login (no recomendado)

# --- Rutas dentro del contenedor ---
DATA_DIR = os.environ.get("DATA_DIR", "/data")            # settings, historial, logs, temporales
RCLONE_CONF = os.environ.get(
    "RCLONE_CONF", "/config/rclone/rclone.conf"
)                                                         # config de rclone (compartida)

# Carpeta del config de OMV montada (solo lectura) para respaldarla.
OMV_CONFIG_DIR = os.environ.get("OMV_CONFIG_DIR", "/host/etc-openmediavault")

# Raíces de host (montadas solo lectura) donde buscar stacks de compose.
# Lista separada por ':'  (ej: "/srv/dev-disk-by-uuid-AAA:/srv/dev-disk-by-uuid-BBB")
COMPOSE_ROOTS = [
    p for p in os.environ.get(
        "COMPOSE_ROOTS",
        "/srv/dev-disk-by-uuid-18d0f5c7-6a18-42e3-a170-b5d57fa8e252/compose:"
        "/srv/dev-disk-by-uuid-7469580d-0da7-4fef-bbed-250bdc899d08/compose",
    ).split(":") if p
]

# Carpeta local opcional para destino "local" (montada RW en el contenedor).
LOCAL_DEST_DIR = os.environ.get("LOCAL_DEST_DIR", "/destino-local")

# Identidades del sistema (usuarios, contraseñas, Samba) — montadas solo lectura.
SYS_ETC_DIR = os.environ.get("SYS_ETC_DIR", "/host/etc")     # /etc del host
SAMBA_DIR = os.environ.get("SAMBA_DIR", "/host/samba")       # /var/lib/samba del host

# Saltar archivos individuales mayores a esto al copiar definiciones de compose.
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "50"))

# Zona horaria (informativa; el contenedor usa TZ del entorno).
TZ = os.environ.get("TZ", "America/Lima")

VERSION = "1.1.0"
