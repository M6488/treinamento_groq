import os, re, psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict
import logging
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

def salvar_novo_cliente(telefone: str, cpf: str, nome: Optional[str] = None):
    telefone_digits = _only_digits(telefone)
    cpf_digits = _only_digits(cpf)
    nome = nome or ''

    try:
        with get_conn() as conn, conn.cursor() as cur:
            logging.info(f"Tentando inserir cliente: telefone={telefone_digits}, cpf={cpf_digits}, nome={nome}")
            cur.execute("""
                INSERT INTO clientes (telefone, cpf, nome)
                VALUES (%s, %s, %s)
            """, (telefone_digits, cpf_digits, nome))
            conn.commit()
            logging.info("Cliente inserido com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao inserir cliente no banco: {e}")
        raise