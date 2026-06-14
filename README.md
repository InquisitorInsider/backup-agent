# backup-agent

Módulo de respaldo con **panel web** para tu servidor OMV. Se levanta en Docker
(igual que el print-agent), detecta solo lo que hay que respaldar, te deja elegir
con casillas, configurar destinos (OneDrive/rclone o carpeta local) y programar
el respaldo diario. Todo desde una interfaz, sin tocar scripts.

## Qué hace
- **Autoescaneo**: detecta el `config.xml` de OMV, los volúmenes Docker, las bases
  de datos en contenedores (con sus credenciales leídas del entorno) y los stacks
  de compose. Pre-marca lo recomendado y descarta lo pesado (medios, anónimos).
- **Selección**: activas/desactivas qué entra en el respaldo.
- **Destinos**: uno o varios. Remote de rclone (reusa `onedrive_restaurante`) o
  carpeta local / disco. Las bases se guardan por **dump lógico** (pg_dump /
  mysqldump), no copiando archivos en caliente.
- **Programación**: hora diaria + retención (rotación de N días). El reloj va
  dentro del servicio.
- **Control**: botón "Respaldar ahora", historial y registro visibles.

> v1 hace respaldo. La **restauración desde el panel** llegará en v2.

## Arquitectura
FastAPI + uvicorn sirviendo un panel de una sola página. rclone va incluido en la
imagen. Habla con Docker por el socket para escanear y volcar bases. Imagen
multi-arquitectura (amd64 + arm64), funciona en Raspberry Pi.

## Probar en local
```bash
docker compose up --build -d
# panel en http://localhost:8090  (usuario/clave del compose)
```

## Desplegar en OMV
Ver **DESPLIEGUE-OMV.md**. Resumen: GitHub construye la imagen y la publica en
GHCR; en OMV pegas `docker-compose.omv.yml` y pulsas Up.

## Permisos
El contenedor monta el **socket de Docker** (para autoescaneo y dumps) y los
discos de datos en **solo lectura**. Es lo necesario para que sea automático; en
un servidor propio y autoalojado es lo habitual.

## Variables
Ver `.env.example`. Lo esencial: `ADMIN_USER`, `ADMIN_PASSWORD`, `TZ`.
