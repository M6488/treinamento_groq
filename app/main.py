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

_digits_re = re.compile(r"\D")
_nome_re = re.compile(r"(?i)\b(meu nome é|sou|me chamo)\s+([a-zà-ú\s]+)")


@app.post("/")
async def webhook(request: Request):
    body = await request.json()
    logging.info("Corpo recebido: %s", body)

    tipo = body.get("type")
    if tipo != "message":
        return {"status": "ignorado"}

    mensagem = body.get("body", "")
    telefone = body.get("from")
    pushname = body.get("pushName")

    # Remover caracteres não numéricos
    mensagem_digitos = _digits_re.sub("", mensagem)
    cpf = mensagem_digitos if len(mensagem_digitos) == 11 else None

    cliente = buscar_cliente_por_telefone(telefone)
    nome_detectado = None

    # Tentativa de extrair o nome caso a mensagem contenha isso
    nome_match = _nome_re.search(mensagem)
    if nome_match:
        nome_detectado = nome_match.group(2).strip().title()

    if cliente:
        contexto = f"Cliente identificado: nome={cliente['nome']} CPF={cliente['cpf']}."
    elif cpf:
        c2 = buscar_cliente_por_cpf(cpf)
        if c2:
            cliente = c2
            contexto = f"Cliente identificado por CPF: nome={c2['nome']} CPF={c2['cpf']}."
        elif nome_detectado:
            try:
                salvar_novo_cliente(telefone, cpf, nome=nome_detectado)
                cliente = {"nome": nome_detectado, "cpf": cpf}
                contexto = f"Novo cliente cadastrado com sucesso: nome={nome_detectado}, CPF={cpf}."
            except Exception as e:
                logging.exception("Erro ao cadastrar novo cliente com nome e CPF: %s", e)
                contexto = (
                    "Tentei cadastrar, mas houve um erro. Por favor, informe novamente seu nome e CPF."
                )
        else:
            contexto = (
                "Recebi seu CPF, mas falta o nome. Me diga seu nome completo pra continuar, visse?"
            )
    elif nome_detectado:
        contexto = (
            f"Beleza, {nome_detectado}! Agora me diga seu CPF pra eu te cadastrar direitinho."
        )
    else:
        contexto = (
            "Oxente, me diga seu nome e CPF pra eu poder lhe atender direitinho, tá certo?"
        )

    resposta = await gerar_resposta_nordestina(mensagem, contexto=contexto, cliente=cliente)

    if DEBUG:
        print("Resposta gerada:", resposta)
    else:
        await enviar_mensagem(telefone, resposta)

    return {"status": "ok"}
