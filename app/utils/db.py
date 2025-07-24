import os, re, psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, List
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
            SELECT id, nome, telefone, email
            FROM clientes
            WHERE regexp_replace(telefone, '\\D', '', 'g') = %s
            LIMIT 1
        """, (num,))
        row = cur.fetchone()
        return row

def salvar_novo_cliente(telefone: str, nome: Optional[str] = None, email: Optional[str] = None):
    """Salva novo cliente apenas com telefone e nome (sem CPF)"""
    telefone_digits = _only_digits(telefone)
    nome = nome or ''

    try:
        with get_conn() as conn, conn.cursor() as cur:
            logging.info(f"Tentando inserir cliente: telefone={telefone_digits}, nome={nome}")
            cur.execute("""
                INSERT INTO clientes (telefone, nome, email)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (telefone_digits, nome, email))
            cliente_id = cur.fetchone()['id']
            conn.commit()
            logging.info(f"Cliente inserido com sucesso. ID: {cliente_id}")
            return cliente_id
    except Exception as e:
        logging.error(f"Erro ao inserir cliente no banco: {e}")
        raise

def buscar_cardapio_ativo() -> List[Dict]:
    """Busca todos os itens ativos do cardápio"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, nome, preco_centavos, ativo
            FROM cardapio
            WHERE ativo = true
            ORDER BY nome
        """)
        return cur.fetchall()

def buscar_produto_por_nome(nome_produto: str) -> Optional[Dict]:
    """Busca produto por nome (busca parcial)"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, nome, preco_centavos, ativo
            FROM cardapio
            WHERE ativo = true AND LOWER(nome) LIKE LOWER(%s)
            LIMIT 1
        """, (f"%{nome_produto}%",))
        return cur.fetchone()

def criar_carrinho(cliente_id: int) -> str:
    """Cria um novo carrinho para o cliente"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO carrinhos (usuario_id, status)
            VALUES (%s, 'aberto')
            RETURNING id
        """, (cliente_id,))
        carrinho_id = cur.fetchone()['id']
        conn.commit()
        return str(carrinho_id)

def buscar_carrinho_aberto(cliente_id: int) -> Optional[Dict]:
    """Busca carrinho aberto do cliente"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, usuario_id, status, criado_em
            FROM carrinhos
            WHERE usuario_id = %s AND status = 'aberto'
            ORDER BY criado_em DESC
            LIMIT 1
        """, (cliente_id,))
        return cur.fetchone()

def adicionar_item_carrinho(carrinho_id: str, produto_id: int, quantidade: int = 1):
    """Adiciona item ao carrinho ou atualiza quantidade"""
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica se item já existe no carrinho
        cur.execute("""
            SELECT quantidade FROM itens_carrinho
            WHERE carrinho_id = %s AND produto_id = %s
        """, (carrinho_id, produto_id))
        
        item_existente = cur.fetchone()
        
        if item_existente:
            # Atualiza quantidade
            nova_quantidade = item_existente['quantidade'] + quantidade
            cur.execute("""
                UPDATE itens_carrinho
                SET quantidade = %s
                WHERE carrinho_id = %s AND produto_id = %s
            """, (nova_quantidade, carrinho_id, produto_id))
        else:
            # Insere novo item
            cur.execute("""
                INSERT INTO itens_carrinho (carrinho_id, produto_id, quantidade)
                VALUES (%s, %s, %s)
            """, (carrinho_id, produto_id, quantidade))
        
        conn.commit()

def listar_itens_carrinho(carrinho_id: str) -> List[Dict]:
    """Lista itens do carrinho com detalhes dos produtos"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                ic.produto_id,
                ic.quantidade,
                c.nome,
                c.preco_centavos,
                (ic.quantidade * c.preco_centavos) as subtotal_centavos
            FROM itens_carrinho ic
            JOIN cardapio c ON ic.produto_id = c.id
            WHERE ic.carrinho_id = %s
            ORDER BY c.nome
        """, (carrinho_id,))
        return cur.fetchall()
