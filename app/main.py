from fastapi import FastAPI, Request
import logging, re
from typing import Optional

from app.config import DEBUG
from app.utils.db import (
    buscar_cliente_por_telefone,
    buscar_cliente_por_cpf,
    salvar_novo_cliente,
)
from app.utils.groq_client import gerar_resposta_nordestina
from app.utils.ultramsg_client import enviar_mensagem

app = FastAPI()
logging.basicConfig(level=logging.INFO)

_digits_re = re.compile(r"\D+")

def _only_digits(s: str) -> str:
    return _digits_re.sub("", s or "")

def _extrair_telefone(raw_chat_id: Optional[str], raw_from: Optional[str]) -> Optional[str]:
    """Extrai o número do formato UltraMsg (ex: '558199999999@c.us')."""
    val = raw_chat_id or raw_from
    if not val:
        return None
    num = val.split("@")[0]
    return _only_digits(num)

def _detectar_nome(texto: str) -> Optional[str]:
    """Detecta nome presumido se tiver estrutura típica (ex: 'meu nome é João Silva')."""
    texto = texto.lower()
    match = re.search(r"(?:meu nome é|sou o|sou a|aqui é o|aqui é a)\s+([a-zA-ZÀ-ÿ\s]{3,})", texto)
    if match:
        nome = match.group(1).strip().title()
        return nome
    return None

def _detectar_cpf(texto: str) -> Optional[str]:
    if not texto:
        return None
    m = re.search(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto)
    if m:
        return m.group(1)
    return None

@app.post("/")
async def webhook_ultramsg(req: Request):
    body = await req.json()
    if DEBUG:
        logging.info(f"Payload recebido: {body}")

    tipo = body.get("type")
    if tipo != "chat":
        return {"status": "ignorado", "motivo": f"evento {tipo}"}

    texto_cli = body.get("body", "")
    chat_id   = body.get("chatId")
    from_id   = body.get("from")
    pushname  = body.get("pushname", "")  # Nome do WhatsApp

    telefone  = _extrair_telefone(chat_id, from_id)
    if not telefone:
        logging.error("Sem telefone no payload.")
        return {"status": "erro", "detail": "sem telefone"}

    cliente = buscar_cliente_por_telefone(telefone)

    contexto = None
    if cliente:
        contexto = f"Cliente identificado: nome={cliente['nome']} CPF={cliente['cpf']}."
    else:
        cpf = _detectar_cpf(texto_cli)
        if cpf:
            c2 = buscar_cliente_por_cpf(cpf)
            if c2:
                cliente = c2
                contexto = f"Cliente identificado por CPF: nome={c2['nome']} CPF={c2['cpf']}."
                try:
                    
                    salvar_novo_cliente(telefone, cpf, nome=pushname)
                    logging.info("Cliente salvo no banco com nome do WhatsApp.")
                except Exception as e:
                    logging.exception("Erro ao salvar cliente novo: %s", e)
        if not cliente:
            cpf = _detectar_cpf(texto_cli)
            nome_detectado = _detectar_nome(texto_cli)

            if cpf and nome_detectado:
                try:
                    salvar_novo_cliente(telefone, cpf, nome=nome_detectado)
                    contexto = f"Novo cliente cadastrado com sucesso: nome={nome_detectado}, CPF={cpf}."
                    cliente = {"nome": nome_detectado, "cpf": cpf}
                except Exception as e:
                    logging.exception("Erro ao cadastrar novo cliente com nome e CPF: %s", e)
                    contexto = (
                        "Tentei cadastrar, mas houve um erro. Por favor, informe novamente seu nome e CPF."
                    )
            else:
                contexto = (
                    "Ainda não encontrei seu cadastro. Por favor, me informe seu nome completo e CPF "
                    "para eu fazer seu cadastro rapidinho."
                )

    resposta = gerar_resposta_nordestina(texto_cli, contexto)

    try:
        await enviar_mensagem(telefone, resposta)
    except Exception as e:
        logging.exception("Falha ao enviar via UltraMsg: %s", e)
        return {"status": "erro_envio", "detail": str(e)}

    return {"status": "ok"}

    
