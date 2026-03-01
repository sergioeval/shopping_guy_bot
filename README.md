# 🛒 Shopping Guy Bot

Bot de Telegram para crear listas del supermercado con precios y calcular el costo total. Cada usuario puede tener múltiples listas y agregar productos con sus precios para llevar un control de gastos.

## Cómo crear tu propio bot en BotFather

1. **Abre Telegram** y busca [@BotFather](https://t.me/BotFather).

2. **Inicia una conversación** con BotFather y envía el comando:
   ```
   /newbot
   ```

3. **Sigue las instrucciones:**
   - **Nombre del bot**: El nombre que verán los usuarios (ej: "Shopping Guy").
   - **Username del bot**: Debe terminar en `bot` (ej: `shopping_guy_bot`).

4. **Recibirás un token** similar a:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   ⚠️ **Guarda este token en un lugar seguro.** Es la clave para controlar tu bot.

5. **Configura el token** en tu proyecto creando un archivo `.env`:
   ```bash
   cp .env.example .env
   ```
   Edita `.env` y reemplaza `tu_token_aqui` con tu token real.

---

## Instalación

### Requisitos

- Python 3.10 o superior
- Cuenta de Telegram

### Pasos

1. **Clonar el repositorio:**
   ```bash
   git clone git@github.com:sergioeval/shopping_guy_bot.git
   cd shopping_guy_bot
   ```

2. **Crear entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # En Windows: .venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar el token:**
   ```bash
   cp .env.example .env
   # Edita .env y agrega tu TELEGRAM_BOT_TOKEN
   ```

5. **Ejecutar el bot:**
   ```bash
   python bot.py
   ```

---

## Uso del bot

Una vez en marcha, abre tu bot en Telegram y usa estos comandos:

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar el bot y ver comandos disponibles |
| `/nueva_lista` | Crear una nueva lista (te pedirá el nombre) |
| `/agregar_producto` | Agregar un producto (nombre, precio y lista) |
| `/total` | Ver total y detalle de una lista |
| `/eliminar_lista` | Eliminar una lista |
| `/listas` | Ver todas tus listas |
| `/cancel` | Cancelar la operación actual |

### Detalles

- **"null"**: En `/agregar_producto` y `/total`, si respondes `null` (o nulo, última) al preguntar la lista, se usará la última lista creada.
- **Texto en minúsculas**: Los nombres de listas y productos se guardan siempre en minúsculas.

---

## Ejecutar como servicio (Ubuntu/Linux)

Para que el bot se ejecute en segundo plano y se inicie automáticamente al reiniciar el servidor:

```bash
sudo ./install-service.sh
```

Comandos útiles:

```bash
sudo systemctl status shopping-guy-bot   # Ver estado
sudo systemctl stop shopping-guy-bot    # Detener
sudo systemctl start shopping-guy-bot   # Iniciar
sudo journalctl -u shopping-guy-bot -f  # Ver logs en tiempo real
```

---

## Estructura del proyecto

```
shopping_guy_bot/
├── bot.py              # Bot principal
├── database.py         # Módulo SQLite
├── requirements.txt
├── .env.example        # Plantilla para variables de entorno
├── shopping-guy-bot.service
├── install-service.sh
└── README.md
```

---

## Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).
