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

# Armazenar o estado do usuário em memória por telefone
estados_usuarios = {}

@app.post("/")
async def webhook_ultramsg(req: Request):
    body = await req.json()
    logging.info(f"Body recebido: {body}")

    if body.get("type") != "message":
        return {"status": "ignorado"}

    telefone = body.get("from")
    mensagem = body.get("body", "").strip()
    estado = estados_usuarios.get(telefone)

    cliente = await buscar_cliente_por_telefone(telefone)

    if cliente:
        resposta = await gerar_resposta_nordestina(mensagem, cliente)
    else:
        if not estado:
            resposta = "Ôxente! Qual o seu nome pra eu lhe cadastrar, meu rei?"
            estados_usuarios[telefone] = {"fase": "nome"}
        elif estado["fase"] == "nome":
            estados_usuarios[telefone]["nome"] = mensagem
            estados_usuarios[telefone]["fase"] = "cpf"
            resposta = "Beleza! Agora me diga seu CPF, só os números."
        elif estado["fase"] == "cpf":
            cpf_limpo = _digits_re.sub("", mensagem)
            if len(cpf_limpo) != 11:
                resposta = "Eita! Esse CPF tá estranho... Manda de novo, por favor, só com os números."
            else:
                nome = estado["nome"]
                await salvar_novo_cliente(nome=nome, telefone=telefone, cpf=cpf_limpo)
                resposta = f"Pronto, {nome}! Cadastro feito com sucesso. Pode falar o que quiser agora! 😄"
                estados_usuarios.pop(telefone, None)

    if DEBUG:
        print("Resposta:", resposta)
    else:
        await enviar_mensagem(telefone, resposta)

    return {"status": "ok"}
