from fastapi import FastAPI, Request
import logging, re
from typing import Optional

from app.config import DEBUG
from app.utils.db import buscar_cliente_por_telefone, buscar_cliente_por_cpf
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
        if not cliente:
            contexto = (
                "O cliente ainda não foi identificado no banco. "
                "Peça de forma simpática o CPF para localizar o cadastro. "
                "Se ele não quiser, diga que pode continuar sem cadastro."
            )

    resposta = gerar_resposta_nordestina(texto_cli, contexto)

    try:
        await enviar_mensagem(telefone, resposta)
    except Exception as e:
        logging.exception("Falha ao enviar via UltraMsg: %s", e)
        return {"status": "erro_envio", "detail": str(e)}

    return {"status": "ok"}
