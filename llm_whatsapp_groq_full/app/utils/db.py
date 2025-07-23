import os, re, psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict

from app.config import DATABASE_URL

_phone_digits_re = re.compile(r"\D+")

def _only_digits(s: str) -> str:
    return _phone_digits_re.sub("", s or "")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def buscar_cliente_por_telefone(telefone: str) -> Optional[Dict]:
    """Telefone pode vir em formato +55... ou 55... ou @c.us. Extraímos só dígitos."""
    num = _only_digits(telefone)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, nome, cpf, telefone
            FROM clientes
            WHERE regexp_replace(telefone, '\\D', '', 'g') = %s
            LIMIT 1
        """, (num,))
        row = cur.fetchone()
        return row

def buscar_cliente_por_cpf(cpf: str) -> Optional[Dict]:
    num = _only_digits(cpf)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, nome, cpf, telefone
            FROM clientes
            WHERE regexp_replace(cpf, '\\D', '', 'g') = %s
            LIMIT 1
        """, (num,))
        row = cur.fetchone()
        return row
