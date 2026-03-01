"""Bot de Telegram para listas del supermercado con precios."""

import logging
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db

# Cargar variables de entorno
load_dotenv(Path(__file__).parent / ".env")

# Estados para ConversationHandler
NOMBRE_LISTA, NOMBRE_PRODUCTO, PRECIO_PRODUCTO, LISTA_PRODUCTO, LISTA_TOTAL, LISTA_ELIMINAR = range(6)

# Valores que el usuario puede enviar para "null"
NULL_VALUES = ("null", "nulo", "ninguna", "ultima", "última", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_null(text: str | None) -> bool:
    """Verifica si el usuario indicó null/última lista."""
    if not text or not str(text).strip():
        return True
    return str(text).strip().lower() in NULL_VALUES


def parse_precio(text: str) -> float | None:
    """Intenta extraer un número de precio del texto."""
    text = text.strip().replace(",", ".")
    match = re.search(r"[\d.]+", text)
    return float(match.group()) if match else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start."""
    await update.message.reply_text(
        "🛒 ¡Hola! Soy tu bot de listas del super.\n\n"
        "Comandos disponibles:\n"
        "/nueva_lista - Crear una nueva lista\n"
        "/agregar_producto - Agregar producto a una lista\n"
        "/total - Ver total y detalle de una lista\n"
        "/eliminar_lista - Eliminar una lista\n"
        "/listas - Ver todas tus listas"
    )


# --- /nueva_lista ---
async def nueva_lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de crear lista."""
    await update.message.reply_text("📝 ¿Cómo quieres llamar a la nueva lista?")
    return NOMBRE_LISTA


async def nueva_lista_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el nombre y crea la lista."""
    nombre = update.message.text.strip()
    if not nombre:
        await update.message.reply_text("❌ El nombre no puede estar vacío. Intenta de nuevo:")
        return NOMBRE_LISTA

    user_id = update.effective_user.id
    lista_id = db.crear_lista(nombre, user_id)
    await update.message.reply_text(f"✅ Lista «{nombre}» creada correctamente (ID: {lista_id})")
    return ConversationHandler.END


# --- /agregar_producto ---
async def agregar_producto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de agregar producto."""
    await update.message.reply_text("📦 ¿Nombre del producto?")
    return NOMBRE_PRODUCTO


async def agregar_producto_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nombre del producto y pide el precio."""
    context.user_data["producto_nombre"] = update.message.text.strip()
    await update.message.reply_text("💰 ¿Cuál es el precio? (ej: 15.50)")
    return PRECIO_PRODUCTO


async def agregar_producto_precio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio y pide la lista."""
    precio = parse_precio(update.message.text)
    if precio is None or precio < 0:
        await update.message.reply_text("❌ Precio inválido. Escribe un número (ej: 15.50):")
        return PRECIO_PRODUCTO

    context.user_data["producto_precio"] = precio
    await update.message.reply_text(
        "📋 ¿En qué lista guardarlo? (responde null para usar la última lista)"
    )
    return LISTA_PRODUCTO


async def agregar_producto_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Determina la lista y agrega el producto."""
    user_id = update.effective_user.id
    nombre_lista_input = update.message.text

    if is_null(nombre_lista_input):
        lista = db.obtener_ultima_lista(user_id)
        if not lista:
            await update.message.reply_text(
                "❌ No tienes ninguna lista. Crea una primero con /nueva_lista"
            )
            return ConversationHandler.END
    else:
        lista = db.obtener_lista_por_nombre(nombre_lista_input.strip(), user_id)
        if not lista:
            await update.message.reply_text(f"❌ No existe una lista llamada «{nombre_lista_input.strip()}»")
            return ConversationHandler.END

    producto = context.user_data.get("producto_nombre", "")
    precio = context.user_data.get("producto_precio", 0)
    db.agregar_producto(lista["id"], producto, precio)

    await update.message.reply_text(
        f"✅ Agregado: {producto} - ${precio:.2f} → lista «{lista['nombre']}»"
    )
    context.user_data.pop("producto_nombre", None)
    context.user_data.pop("producto_precio", None)
    return ConversationHandler.END


# --- /total ---
async def total_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de ver total."""
    await update.message.reply_text(
        "📊 ¿De qué lista quieres ver el total? (responde null para la última lista)"
    )
    return LISTA_TOTAL


async def total_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el detalle y total de la lista."""
    user_id = update.effective_user.id
    nombre_lista_input = update.message.text

    if is_null(nombre_lista_input):
        lista = db.obtener_ultima_lista(user_id)
        if not lista:
            await update.message.reply_text(
                "❌ No tienes ninguna lista. Crea una primero con /nueva_lista"
            )
            return ConversationHandler.END
    else:
        lista = db.obtener_lista_por_nombre(nombre_lista_input.strip(), user_id)
        if not lista:
            await update.message.reply_text(f"❌ No existe una lista llamada «{nombre_lista_input.strip()}»")
            return ConversationHandler.END

    productos, total = db.calcular_total_lista(lista["id"])

    if not productos:
        await update.message.reply_text(f"📋 Lista «{lista['nombre']}» está vacía.\nTotal: $0.00")
        return ConversationHandler.END

    lineas = [f"📋 *{lista['nombre']}*\n"]
    for p in productos:
        lineas.append(f"  • {p['producto']}: ${p['precio']:.2f}")
    lineas.append(f"\n💰 *Total: ${total:.2f}*")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")
    return ConversationHandler.END


# --- /eliminar_lista ---
async def eliminar_lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de eliminar lista."""
    await update.message.reply_text(
        "🗑 ¿Qué lista quieres eliminar? (responde null para eliminar la última lista)"
    )
    return LISTA_ELIMINAR


async def eliminar_lista_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Elimina la lista indicada."""
    user_id = update.effective_user.id
    nombre_lista_input = update.message.text

    if is_null(nombre_lista_input):
        lista = db.obtener_ultima_lista(user_id)
        if not lista:
            await update.message.reply_text(
                "❌ No tienes ninguna lista para eliminar."
            )
            return ConversationHandler.END
    else:
        lista = db.obtener_lista_por_nombre(nombre_lista_input.strip(), user_id)
        if not lista:
            await update.message.reply_text(f"❌ No existe una lista llamada «{nombre_lista_input.strip()}»")
            return ConversationHandler.END

    eliminada = db.eliminar_lista(lista["id"], user_id)
    if eliminada:
        await update.message.reply_text(f"✅ Lista «{lista['nombre']}» eliminada correctamente.")
    else:
        await update.message.reply_text("❌ No se pudo eliminar la lista.")
    return ConversationHandler.END


async def listas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todas las listas del usuario."""
    user_id = update.effective_user.id
    listas = db.listar_listas_usuario(user_id)

    if not listas:
        await update.message.reply_text("No tienes ninguna lista. Crea una con /nueva_lista")
        return

    lineas = ["📋 *Tus listas:*\n"]
    for l in listas:
        productos, total = db.calcular_total_lista(l["id"])
        lineas.append(f"  • {l['nombre']} ({len(productos)} productos, ${total:.2f})")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación actual."""
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


async def post_init(application: Application) -> None:
    """Configura el menú de comandos que aparece al escribir / en Telegram."""
    await application.bot.set_my_commands([
        ("start", "Iniciar el bot"),
        ("nueva_lista", "Crear una nueva lista"),
        ("agregar_producto", "Agregar producto a una lista"),
        ("total", "Ver total y detalle de una lista"),
        ("eliminar_lista", "Eliminar una lista"),
        ("listas", "Ver todas tus listas"),
    ])


def main() -> None:
    """Ejecuta el bot."""
    import os
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN no está definido en .env")

    db.init_db()

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # Handler para /nueva_lista
    conv_nueva_lista = ConversationHandler(
        entry_points=[CommandHandler("nueva_lista", nueva_lista_start)],
        states={
            NOMBRE_LISTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nueva_lista_nombre)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /agregar_producto
    conv_agregar = ConversationHandler(
        entry_points=[CommandHandler("agregar_producto", agregar_producto_start)],
        states={
            NOMBRE_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_producto_nombre)],
            PRECIO_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_producto_precio)],
            LISTA_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_producto_lista)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /total
    conv_total = ConversationHandler(
        entry_points=[CommandHandler("total", total_start)],
        states={
            LISTA_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, total_lista)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /eliminar_lista
    conv_eliminar = ConversationHandler(
        entry_points=[CommandHandler("eliminar_lista", eliminar_lista_start)],
        states={
            LISTA_ELIMINAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, eliminar_lista_confirmar)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_nueva_lista)
    application.add_handler(conv_agregar)
    application.add_handler(conv_total)
    application.add_handler(conv_eliminar)
    application.add_handler(CommandHandler("listas", listas_command))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
