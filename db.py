import pymysql
from flask import current_app, g


def connect(database=True):
    cfg = current_app.config
    return pymysql.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"] if database else None,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, args=(), one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Executa um comando e faz commit. Retorna o último id gerado."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            last_id = cur.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return last_id


def execute_many(sql, rows):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
