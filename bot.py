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
(
    NOMBRE_PRODUCTO,
    PRECIO_PRODUCTO,
    RESET_CONFIRMAR,
    NUMERO_PRODUCTO,
    PRODUCTO_EDITAR_SELECCION,
    PRODUCTO_EDITAR_CAMPO,
    PRODUCTO_EDITAR_VALOR,
) = range(7)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def formatear_lista_con_checks(lista: dict, productos: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    """Retorna (texto formateado, teclado inline) para mostrar una lista con checkboxes.
    El total solo suma los productos marcados como seleccionados."""
    total = sum(p["precio"] for p in productos if p.get("seleccionado"))
    lineas = ["📋 *Tu lista*\n"]
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
        "Tienes una sola lista; todos los productos van ahí.\n\n"
        "Comandos disponibles:\n"
        "/agregar_producto — Agregar producto con precio\n"
        "/total — Ver lista, marcar con los botones y ver total de seleccionados\n"
        "/marcar_producto — Marcar o desmarcar por número\n"
        "/editar_producto — Cambiar nombre o precio de un producto\n"
        "/resetear_lista — Vaciar la lista (pedirá confirmación)\n"
        "/lista — Resumen de tu lista"
    )


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
    """Guarda el precio y agrega el producto a la lista única."""
    precio = parse_precio(update.message.text)
    if precio is None or precio < 0:
        await update.message.reply_text("❌ Precio inválido. Escribe un número (ej: 15.50):")
        return PRECIO_PRODUCTO

    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)
    producto = context.user_data.get("producto_nombre", "")
    db.agregar_producto(lista["id"], producto, precio)

    await update.message.reply_text(f"✅ Agregado: {producto} — ${precio:.2f}")
    context.user_data.pop("producto_nombre", None)
    return ConversationHandler.END


# --- /total ---
async def total_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el detalle y total de la lista única."""
    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)
    productos, _ = db.calcular_total_lista(lista["id"])

    if not productos:
        await update.message.reply_text("📋 Tu lista está vacía.\nTotal: $0.00")
        return

    texto, teclado = formatear_lista_con_checks(lista, productos)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado)


# --- /resetear_lista ---
async def resetear_lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide confirmación antes de vaciar la lista."""
    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)
    productos, _ = db.calcular_total_lista(lista["id"])
    if not productos:
        await update.message.reply_text("📋 Tu lista ya está vacía.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🗑 Se borrarán *todos* los productos de tu lista. "
        "Para confirmar escribe *si* (o /cancel para salir).",
        parse_mode="Markdown",
    )
    return RESET_CONFIRMAR


async def resetear_lista_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vaciar la lista si el usuario confirma."""
    texto = update.message.text.strip().lower()
    if texto not in ("si", "sí", "yes"):
        await update.message.reply_text("Operación cancelada; la lista no se modificó.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    n = db.vaciar_productos_lista_unica(user_id)
    await update.message.reply_text(f"✅ Lista vaciada ({n} producto(s) eliminados).")
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
    """Muestra los productos numerados y pide el número a marcar/desmarcar."""
    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)

    productos, _ = db.calcular_total_lista(lista["id"])
    if not productos:
        await update.message.reply_text("📋 Tu lista está vacía.")
        return ConversationHandler.END

    context.user_data["marcar_productos"] = productos

    lineas = ["📋 *Tu lista* — escribe el número a marcar o desmarcar:\n"]
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

    context.user_data.pop("marcar_productos", None)
    return ConversationHandler.END


# --- /editar_producto ---
async def editar_producto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra productos numerados y pide el número a editar."""
    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)

    productos, _ = db.calcular_total_lista(lista["id"])
    if not productos:
        await update.message.reply_text("📋 Tu lista está vacía.")
        return ConversationHandler.END

    context.user_data["editar_productos"] = productos

    lineas = ["📋 *Tu lista* — elige el número del producto a editar:\n"]
    for i, p in enumerate(productos, 1):
        icono = "✅" if p.get("seleccionado") else "⬜"
        lineas.append(f"  {i}. {icono} {p['producto']} — ${p['precio']:.2f}")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")
    await update.message.reply_text("Escribe el número del producto (1, 2, 3...) o /cancel para salir:")
    return PRODUCTO_EDITAR_SELECCION


async def editar_producto_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el número y pregunta qué campo editar."""
    try:
        num = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Escribe un número válido (ej: 1, 2, 3):")
        return PRODUCTO_EDITAR_SELECCION

    productos = context.user_data.get("editar_productos", [])
    if num < 1 or num > len(productos):
        await update.message.reply_text(f"❌ Número inválido. Elige entre 1 y {len(productos)}:")
        return PRODUCTO_EDITAR_SELECCION

    producto = productos[num - 1]
    context.user_data["editar_producto_id"] = producto["id"]
    await update.message.reply_text(
        f"✏️ Producto: *{producto['producto']}* — ${producto['precio']:.2f}\n\n"
        "¿Qué quieres cambiar? Responde:\n"
        "  • *nombre* — para cambiar el nombre\n"
        "  • *precio* o *monto* — para cambiar el precio",
        parse_mode="Markdown"
    )
    return PRODUCTO_EDITAR_CAMPO


async def editar_producto_campo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nombre/precio y pide el nuevo valor."""
    texto = update.message.text.strip().lower()
    if texto in ("nombre", "producto"):
        context.user_data["editar_producto_campo"] = "nombre"
        await update.message.reply_text("✏️ Escribe el nuevo nombre del producto:")
    elif texto in ("precio", "monto"):
        context.user_data["editar_producto_campo"] = "precio"
        await update.message.reply_text("✏️ Escribe el nuevo precio (ej: 15.50):")
    else:
        await update.message.reply_text("❌ Responde «nombre» o «precio»:")
        return PRODUCTO_EDITAR_CAMPO
    return PRODUCTO_EDITAR_VALOR


async def editar_producto_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el nuevo valor y actualiza el producto."""
    user_id = update.effective_user.id
    id_producto = context.user_data.get("editar_producto_id")
    campo = context.user_data.get("editar_producto_campo")

    if not id_producto or not campo:
        await update.message.reply_text("❌ Error. Intenta de nuevo con /editar_producto")
        return ConversationHandler.END

    producto_nuevo = None
    precio_nuevo = None
    if campo == "nombre":
        nombre = update.message.text.strip()
        if not nombre:
            await update.message.reply_text("❌ El nombre no puede estar vacío. Intenta de nuevo:")
            return PRODUCTO_EDITAR_VALOR
        producto_nuevo = nombre
        precio_nuevo = None  # mantener precio actual
    else:
        precio = parse_precio(update.message.text)
        if precio is None or precio < 0:
            await update.message.reply_text("❌ Precio inválido. Escribe un número (ej: 15.50):")
            return PRODUCTO_EDITAR_VALOR
        precio_nuevo = precio
        producto_nuevo = None  # mantener nombre actual

    if db.actualizar_producto(id_producto, producto_nuevo, precio_nuevo, user_id):
        prod = db.obtener_producto_por_id(id_producto, user_id)
        await update.message.reply_text(
            f"✅ Actualizado: {prod['producto']} — ${prod['precio']:.2f}"
        )
    else:
        await update.message.reply_text("❌ No se pudo actualizar el producto.")

    context.user_data.pop("editar_productos", None)
    context.user_data.pop("editar_producto_id", None)
    context.user_data.pop("editar_producto_campo", None)
    return ConversationHandler.END


async def lista_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumen de la lista única del usuario."""
    user_id = update.effective_user.id
    lista = db.obtener_o_crear_lista_unica(user_id)
    productos, total_todos = db.calcular_total_lista(lista["id"])
    seleccionados = sum(1 for p in productos if p.get("seleccionado"))
    total_marcados = sum(p["precio"] for p in productos if p.get("seleccionado"))

    if not productos:
        await update.message.reply_text("📋 Tu lista está vacía. Usa /agregar_producto.")
        return

    lineas = [
        "📋 *Tu lista*\n",
        f"  • Productos: {len(productos)}",
        f"  • Marcados: {seleccionados}",
        f"  • Total (todos los ítems): ${total_todos:.2f}",
        f"  • Total (solo marcados): ${total_marcados:.2f}",
    ]
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación actual."""
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


async def post_init(application: Application) -> None:
    """Configura el menú de comandos que aparece al escribir / en Telegram."""
    await application.bot.set_my_commands([
        ("start", "Iniciar el bot"),
        ("agregar_producto", "Agregar producto con precio"),
        ("total", "Ver lista y total de seleccionados"),
        ("marcar_producto", "Marcar o desmarcar por número"),
        ("editar_producto", "Cambiar nombre o precio de un producto"),
        ("resetear_lista", "Vaciar toda la lista"),
        ("lista", "Resumen de tu lista"),
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

    # Handler para /agregar_producto
    conv_agregar = ConversationHandler(
        entry_points=[CommandHandler("agregar_producto", agregar_producto_start)],
        states={
            NOMBRE_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_producto_nombre)],
            PRECIO_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_producto_precio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /resetear_lista
    conv_resetear = ConversationHandler(
        entry_points=[CommandHandler("resetear_lista", resetear_lista_start)],
        states={
            RESET_CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, resetear_lista_confirmar)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /marcar_producto
    conv_marcar = ConversationHandler(
        entry_points=[CommandHandler("marcar_producto", marcar_producto_start)],
        states={
            NUMERO_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, marcar_producto_numero)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handler para /editar_producto
    conv_editar_producto = ConversationHandler(
        entry_points=[CommandHandler("editar_producto", editar_producto_start)],
        states={
            PRODUCTO_EDITAR_SELECCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_producto_seleccion)],
            PRODUCTO_EDITAR_CAMPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_producto_campo)],
            PRODUCTO_EDITAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_producto_valor)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CallbackQueryHandler(toggle_producto_callback, pattern="^toggle:"))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("total", total_command))
    application.add_handler(conv_agregar)
    application.add_handler(conv_resetear)
    application.add_handler(conv_marcar)
    application.add_handler(conv_editar_producto)
    application.add_handler(CommandHandler("lista", lista_command))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
