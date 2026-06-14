# Desplegar backup-agent en OMV

Mismo patrón que el print-agent: GitHub construye la imagen y la publica en GHCR;
en OMV solo pegas un compose y pulsas Up.

## 1. GitHub construye la imagen
Repo **público**: `InquisitorInsider/backup-agent`. Al hacer push a `main`, el
workflow `.github/workflows/docker-publish.yml` construye y publica
`ghcr.io/inquisitorinsider/backup-agent` (amd64 + arm64).

## 2. Poner el paquete en público (una sola vez)
Tras el primer build, el paquete en GHCR nace privado. Hazlo público una vez:
GitHub → tu perfil → **Packages** → `backup-agent` → **Package settings** →
**Change visibility** → **Public**. Después la Pi lo baja **sin** `docker login`.

## 3. Desplegar en OMV
1. OMV → **Compose → Files → Add (+)**, nómbralo `backup-agent`.
2. Pega `docker-compose.omv.yml`. **Cambia `ADMIN_PASSWORD`.**
3. Revisa que las rutas de los discos (`/srv/dev-disk-by-uuid-...`) y la del
   `rclone_config` coincidan con tu servidor.
4. Guarda y pulsa **Up**.

## 4. Usar el panel
Abre `http://IP-DEL-SERVIDOR:8090` (usuario/clave del compose).
1. El panel **autoescanea** y pre-marca lo recomendado. Ajusta las casillas.
2. En **A dónde respaldar**, añade un destino:
   - *Remote rclone* → elige `onedrive_restaurante` y una subcarpeta (ej.
     `Respaldos/omv`).
   - *Carpeta local* → se guarda en el disco montado en `/destino-local`.
3. En **Programación**, activa, pon la hora y los días de retención.
4. Pulsa **Guardar configuración**.
5. Prueba con **Respaldar ahora** y mira el historial y el registro.

## Notas
- Las credenciales de las bases se leen en caliente del entorno de cada
  contenedor; no se guardan en disco.
- El paquete es liviano (no incluye medios ni datos de usuario de Nextcloud).
- ¿Errores de auth de OneDrive? El token de rclone se comparte con Nextcloud; si
  da problemas, crea un remote aparte y selecciónalo como destino.
- La restauración guiada llegará en v2; por ahora descargas el `.tar.gz` y
  restauras a mano (te puedo dar el procedimiento cuando lo necesites).
