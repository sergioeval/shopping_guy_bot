"""Bot de Telegram para listas del supermercado con precios."""

import logging
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
NOMBRE_LISTA, NOMBRE_PRODUCTO, PRECIO_PRODUCTO, LISTA_PRODUCTO, LISTA_TOTAL, LISTA_ELIMINAR, LISTA_MARCAR, NUMERO_PRODUCTO, LISTA_CLONAR_ORIGEN, NOMBRE_CLON = range(10)

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


def formatear_lista_con_checks(lista: dict, productos: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    """Retorna (texto formateado, teclado inline) para mostrar una lista con checkboxes.
    El total solo suma los productos marcados como seleccionados."""
    total = sum(p["precio"] for p in productos if p.get("seleccionado"))
    lineas = [f"📋 *{lista['nombre']}*\n"]
    keyboard = []
    for p in productos:
        icono = "✅" if p.get("seleccionado") else "⬜"
        lineas.append(f"  {icono} {p['producto']}: ${p['precio']:.2f}")
        keyboard.append([
            InlineKeyboardButton(
                f"{'✓' if p.get('seleccionado') else '○'} {p['producto']}",
                callback_data=f"toggle:{p['id']}"
            )
        ])
    lineas.append(f"\n💰 *Total (seleccionados): ${total:.2f}*")
    return "\n".join(lineas), InlineKeyboardMarkup(keyboard)


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
        "/marcar_producto - Marcar/desmarcar producto como seleccionado\n"
        "/clonar_lista - Clonar una lista con nombre nuevo\n"
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

    productos, _ = db.calcular_total_lista(lista["id"])

    if not productos:
        await update.message.reply_text(f"📋 Lista «{lista['nombre']}» está vacía.\nTotal: $0.00")
        return ConversationHandler.END

    texto, teclado = formatear_lista_con_checks(lista, productos)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado)
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


async def toggle_producto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja el clic en un botón de toggle de producto."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("toggle:"):
        return

    try:
        id_producto = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        return

    user_id = update.effective_user.id
    producto = db.obtener_producto_por_id(id_producto, user_id)
    if not producto:
        await query.edit_message_text("❌ Producto no encontrado o sin permisos.")
        return

    db.toggle_producto(id_producto, user_id)
    lista = db.obtener_lista_por_id(producto["id_lista"], user_id)
    if not lista:
        return

    productos, _ = db.calcular_total_lista(lista["id"])
    texto, teclado = formatear_lista_con_checks(lista, productos)
    await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=teclado)


# --- /marcar_producto ---
async def marcar_producto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de marcar/desmarcar producto."""
    await update.message.reply_text(
        "📋 ¿De qué lista? (responde null para la última lista)"
    )
    return LISTA_MARCAR


async def marcar_producto_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra los productos numerados y pide el número a marcar/desmarcar."""
    user_id = update.effective_user.id
    nombre_lista_input = update.message.text

    if is_null(nombre_lista_input):
        lista = db.obtener_ultima_lista(user_id)
    else:
        lista = db.obtener_lista_por_nombre(nombre_lista_input.strip(), user_id)

    if not lista:
        await update.message.reply_text("❌ Lista no encontrada.")
        return ConversationHandler.END

    productos, _ = db.calcular_total_lista(lista["id"])
    if not productos:
        await update.message.reply_text(f"📋 La lista «{lista['nombre']}» está vacía.")
        return ConversationHandler.END

    context.user_data["marcar_lista_id"] = lista["id"]
    context.user_data["marcar_productos"] = productos

    lineas = [f"📋 *{lista['nombre']}* — Marca el número a marcar/desmarcar:\n"]
    for i, p in enumerate(productos, 1):
        icono = "✅" if p.get("seleccionado") else "⬜"
        lineas.append(f"  {i}. {icono} {p['producto']} — ${p['precio']:.2f}")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")
    await update.message.reply_text("Escribe el número del producto (1, 2, 3...) o /cancel para salir:")
    return NUMERO_PRODUCTO


async def marcar_producto_numero(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Alterna el estado del producto indicado."""
    try:
        num = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Escribe un número válido (ej: 1, 2, 3):")
        return NUMERO_PRODUCTO

    productos = context.user_data.get("marcar_productos", [])
    if num < 1 or num > len(productos):
        await update.message.reply_text(f"❌ Número inválido. Elige entre 1 y {len(productos)}:")
        return NUMERO_PRODUCTO

    producto = productos[num - 1]
    user_id = update.effective_user.id
    nuevo_estado = db.toggle_producto(producto["id"], user_id)

    if nuevo_estado is not None:
        estado = "marcado ✓" if nuevo_estado else "desmarcado ○"
        await update.message.reply_text(f"✅ {producto['producto']} {estado}")
    else:
        await update.message.reply_text("❌ No se pudo actualizar.")

    context.user_data.pop("marcar_lista_id", None)
    context.user_data.pop("marcar_productos", None)
    return ConversationHandler.END


# --- /clonar_lista ---
async def clonar_lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de clonar lista."""
    await update.message.reply_text(
        "📋 ¿Qué lista quieres clonar? (responde null para la última lista)"
    )
    return LISTA_CLONAR_ORIGEN


async def clonar_lista_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la lista origen y pide el nombre para la nueva."""
    user_id = update.effective_user.id
    nombre_lista_input = update.message.text

    if is_null(nombre_lista_input):
        lista = db.obtener_ultima_lista(user_id)
    else:
        lista = db.obtener_lista_por_nombre(nombre_lista_input.strip(), user_id)

    if not lista:
        await update.message.reply_text("❌ Lista no encontrada.")
        return ConversationHandler.END

    context.user_data["clonar_lista_id"] = lista["id"]
    await update.message.reply_text(f"📝 ¿Qué nombre quieres para la nueva lista? (clonando «{lista['nombre']}»)")
    return NOMBRE_CLON


async def clonar_lista_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Crea la lista clonada con el nombre indicado."""
    nombre_nuevo = update.message.text.strip()
    if not nombre_nuevo:
        await update.message.reply_text("❌ El nombre no puede estar vacío. Intenta de nuevo:")
        return NOMBRE_CLON

    user_id = update.effective_user.id
    id_lista_origen = context.user_data.get("clonar_lista_id")
    if not id_lista_origen:
        await update.message.reply_text("❌ Error. Intenta de nuevo con /clonar_lista")
        return ConversationHandler.END

    nueva_id = db.clonar_lista(id_lista_origen, nombre_nuevo, user_id)
    if nueva_id:
        productos, _ = db.calcular_total_lista(id_lista_origen)
        await update.message.reply_text(
            f"✅ Lista clonada como «{nombre_nuevo.strip().lower()}» con {len(productos)} productos."
        )
    else:
        await update.message.reply_text("❌ No se pudo clonar la lista.")

    context.user_data.pop("clonar_lista_id", None)
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
        seleccionados = sum(1 for p in productos if p.get("seleccionado"))
        lineas.append(f"  • {l['nombre']} ({seleccionados}/{len(productos)} ✓, ${total:.2f})")

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
        ("marcar_producto", "Marcar/desmarcar producto como seleccionado"),
        ("clonar_lista", "Clonar una lista con nombre nuevo"),
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

    # Handler para /marcar_producto
    conv_marcar = ConversationHandler(
        entry_points=[CommandHandler("marcar_producto", marcar_producto_start)],
        states={
            LISTA_MARCAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, marcar_producto_lista)],
            NUMERO_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, marcar_producto_numero)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /clonar_lista
    conv_clonar = ConversationHandler(
        entry_points=[CommandHandler("clonar_lista", clonar_lista_start)],
        states={
            LISTA_CLONAR_ORIGEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, clonar_lista_origen)],
            NOMBRE_CLON: [MessageHandler(filters.TEXT & ~filters.COMMAND, clonar_lista_nombre)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CallbackQueryHandler(toggle_producto_callback, pattern="^toggle:"))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_nueva_lista)
    application.add_handler(conv_agregar)
    application.add_handler(conv_total)
    application.add_handler(conv_eliminar)
    application.add_handler(conv_marcar)
    application.add_handler(conv_clonar)
    application.add_handler(CommandHandler("listas", listas_command))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
