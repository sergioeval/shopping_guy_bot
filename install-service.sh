#!/bin/bash
# Script para instalar y ejecutar el bot Shopping Guy como servicio systemd en Ubuntu

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="shopping-guy-bot"
SERVICE_FILE="$SCRIPT_DIR/shopping-guy-bot.service"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# Verificar que se ejecuta como root
if [[ $EUID -ne 0 ]]; then
   echo "Este script debe ejecutarse como root (usa: sudo ./install-service.sh)"
   exit 1
fi

# Verificar que existen los archivos necesarios
if [[ ! -f "$SCRIPT_DIR/bot.py" ]]; then
   echo "Error: No se encuentra bot.py en $SCRIPT_DIR"
   exit 1
fi

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
   echo "Advertencia: No existe .env. Asegúrate de crear uno con TELEGRAM_BOT_TOKEN antes de iniciar el bot."
fi

if [[ ! -d "$SCRIPT_DIR/.venv" ]]; then
   echo "Creando entorno virtual..."
   python3 -m venv "$SCRIPT_DIR/.venv"
fi

echo "Instalando dependencias..."
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

# Actualizar rutas en el archivo de servicio si el directorio es diferente
# El .service usa rutas absolutas basadas en /home/sev/projects/shopping_guy
# Si el proyecto está en otra ubicación, hay que ajustar el .service
CURRENT_USER=$(stat -c '%U' "$SCRIPT_DIR")
CURRENT_GROUP=$(stat -c '%G' "$SCRIPT_DIR")

# Crear archivo de servicio temporal con las rutas correctas
TEMP_SERVICE=$(mktemp)
sed -e "s|/home/sev/projects/shopping_guy|$SCRIPT_DIR|g" \
    -e "s|User=sev|User=$CURRENT_USER|g" \
    -e "s|Group=sev|Group=$CURRENT_GROUP|g" \
    "$SERVICE_FILE" > "$TEMP_SERVICE"

echo "Instalando servicio systemd..."
cp "$TEMP_SERVICE" "$SYSTEMD_PATH"
rm "$TEMP_SERVICE"

echo "Recargando systemd..."
systemctl daemon-reload

echo "Habilitando servicio (inicio automático al arrancar)..."
systemctl enable "$SERVICE_NAME"

echo "Iniciando servicio..."
systemctl start "$SERVICE_NAME"

echo ""
echo "✅ Servicio instalado y en ejecución."
echo ""
echo "Comandos útiles:"
echo "  sudo systemctl status $SERVICE_NAME   # Ver estado"
echo "  sudo systemctl stop $SERVICE_NAME     # Detener"
echo "  sudo systemctl start $SERVICE_NAME    # Iniciar"
echo "  sudo journalctl -u $SERVICE_NAME -f   # Ver logs en tiempo real"
echo ""
