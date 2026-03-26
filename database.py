"""Módulo de base de datos SQLite para listas del supermercado."""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "shopping.db"

# Nombre fijo de la única lista por usuario (visible en mensajes).
LISTA_UNICA_NOMBRE = "compras"


def get_connection():
    """Obtiene una conexión a la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa las tablas de la base de datos."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                timestamp_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_lista INTEGER NOT NULL,
                producto TEXT NOT NULL,
                precio REAL NOT NULL,
                seleccionado INTEGER DEFAULT 0,
                FOREIGN KEY (id_lista) REFERENCES listas(id)
            )
        """)
        # Migración: agregar columna seleccionado si no existe (DBs antiguas)
        try:
            conn.execute("ALTER TABLE productos ADD COLUMN seleccionado INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        conn.commit()
    finally:
        conn.close()


def consolidar_listas_usuario(user_id: int) -> None:
    """Si el usuario tiene varias listas (datos antiguos), deja una sola y mueve los productos."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM listas WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if len(ids) <= 1:
            return
        principal = ids[0]
        for lid in ids[1:]:
            conn.execute(
                "UPDATE productos SET id_lista = ? WHERE id_lista = ?",
                (principal, lid),
            )
            conn.execute("DELETE FROM listas WHERE id = ?", (lid,))
        conn.commit()
    finally:
        conn.close()


def obtener_o_crear_lista_unica(user_id: int) -> dict:
    """Devuelve la única lista del usuario; la crea vacía si no existe."""
    consolidar_listas_usuario(user_id)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre, timestamp_creacion FROM listas WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    nueva_id = crear_lista(LISTA_UNICA_NOMBRE, user_id)
    row = obtener_lista_por_id(nueva_id, user_id)
    assert row is not None
    return row


def vaciar_productos_lista_unica(user_id: int) -> int:
    """Elimina todos los productos de la lista única. Retorna cuántos se borraron."""
    lista = obtener_o_crear_lista_unica(user_id)
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM productos WHERE id_lista = ?", (lista["id"],))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def crear_lista(nombre: str, user_id: int) -> int:
    """Crea una nueva lista y retorna su ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO listas (nombre, user_id) VALUES (?, ?)",
            (nombre.strip().lower(), user_id)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def obtener_ultima_lista(user_id: int) -> dict | None:
    """Obtiene la última lista creada por el usuario."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre, timestamp_creacion FROM listas WHERE user_id = ? ORDER BY timestamp_creacion DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def obtener_lista_por_id(id_lista: int, user_id: int) -> dict | None:
    """Obtiene una lista por su ID si pertenece al usuario."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre, timestamp_creacion FROM listas WHERE id = ? AND user_id = ?",
            (id_lista, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def obtener_lista_por_nombre(nombre: str, user_id: int) -> dict | None:
    """Obtiene una lista por su nombre."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre, timestamp_creacion FROM listas WHERE nombre = ? AND user_id = ?",
            (nombre.strip().lower(), user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def agregar_producto(id_lista: int, producto: str, precio: float) -> int:
    """Agrega un producto a una lista."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO productos (id_lista, producto, precio) VALUES (?, ?, ?)",
            (id_lista, producto.strip().lower(), float(precio))
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def obtener_productos_de_lista(id_lista: int) -> list[dict]:
    """Obtiene todos los productos de una lista (incluye seleccionado)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, producto, precio, COALESCE(seleccionado, 0) as seleccionado FROM productos WHERE id_lista = ? ORDER BY id",
            (id_lista,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def obtener_producto_por_id(id_producto: int, user_id: int) -> dict | None:
    """Obtiene un producto por ID si pertenece a una lista del usuario."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT p.id, p.id_lista, p.producto, p.precio, COALESCE(p.seleccionado, 0) as seleccionado
               FROM productos p
               JOIN listas l ON p.id_lista = l.id
               WHERE p.id = ? AND l.user_id = ?""",
            (id_producto, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def toggle_producto(id_producto: int, user_id: int) -> bool | None:
    """Alterna el estado seleccionado de un producto. Retorna el nuevo estado (True/False) o None si no existe/no autorizado."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT p.id, p.seleccionado FROM productos p
               JOIN listas l ON p.id_lista = l.id
               WHERE p.id = ? AND l.user_id = ?""",
            (id_producto, user_id)
        ).fetchone()
        if not row:
            return None
        nuevo = 0 if row["seleccionado"] else 1
        conn.execute("UPDATE productos SET seleccionado = ? WHERE id = ?", (nuevo, id_producto))
        conn.commit()
        return bool(nuevo)
    finally:
        conn.close()


def calcular_total_lista(id_lista: int) -> tuple[list[dict], float]:
    """Retorna (productos, total) de una lista."""
    productos = obtener_productos_de_lista(id_lista)
    total = sum(p["precio"] for p in productos)
    return productos, total


def listar_listas_usuario(user_id: int) -> list[dict]:
    """Lista todas las listas del usuario."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, nombre, timestamp_creacion FROM listas WHERE user_id = ? ORDER BY timestamp_creacion DESC",
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def clonar_lista(id_lista_origen: int, nombre_nuevo: str, user_id: int) -> int | None:
    """Clona una lista con todos sus productos. Retorna el ID de la nueva lista o None si falla."""
    lista = obtener_lista_por_id(id_lista_origen, user_id)
    if not lista:
        return None
    productos = obtener_productos_de_lista(id_lista_origen)
    nueva_id = crear_lista(nombre_nuevo.strip().lower(), user_id)
    conn = get_connection()
    try:
        for p in productos:
            conn.execute(
                "INSERT INTO productos (id_lista, producto, precio, seleccionado) VALUES (?, ?, ?, 0)",
                (nueva_id, p["producto"], p["precio"])
            )
        conn.commit()
        return nueva_id
    finally:
        conn.close()


def actualizar_nombre_lista(id_lista: int, nombre_nuevo: str, user_id: int) -> bool:
    """Actualiza el nombre de una lista. Retorna True si se actualizó."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE listas SET nombre = ? WHERE id = ? AND user_id = ?",
            (nombre_nuevo.strip().lower(), id_lista, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def actualizar_producto(id_producto: int, producto: str | None, precio: float | None, user_id: int) -> bool:
    """Actualiza nombre y/o precio de un producto. Retorna True si se actualizó."""
    prod = obtener_producto_por_id(id_producto, user_id)
    if not prod:
        return False
    nuevo_producto = producto.strip().lower() if producto and producto.strip() else prod["producto"]
    nuevo_precio = float(precio) if precio is not None and precio >= 0 else prod["precio"]
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE productos SET producto = ?, precio = ? WHERE id = ?",
            (nuevo_producto, nuevo_precio, id_producto)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def eliminar_lista(id_lista: int, user_id: int) -> bool:
    """Elimina una lista y sus productos. Retorna True si se eliminó."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM listas WHERE id = ? AND user_id = ?",
            (id_lista, user_id)
        )
        if cursor.rowcount > 0:
            conn.execute("DELETE FROM productos WHERE id_lista = ?", (id_lista,))
            conn.commit()
            return True
        return False
    finally:
        conn.close()
