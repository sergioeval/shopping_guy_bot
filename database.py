"""Módulo de base de datos SQLite para listas del supermercado."""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "shopping.db"


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
                FOREIGN KEY (id_lista) REFERENCES listas(id)
            )
        """)
        conn.commit()
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
    """Obtiene todos los productos de una lista."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, producto, precio FROM productos WHERE id_lista = ? ORDER BY id",
            (id_lista,)
        ).fetchall()
        return [dict(row) for row in rows]
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
