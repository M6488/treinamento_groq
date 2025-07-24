from fastapi import FastAPI, Request
import logging, re
from typing import Optional

from app.config import DEBUG
from app.utils.db import (
    buscar_cliente_por_telefone,
    salvar_novo_cliente,
    buscar_cardapio_ativo,
    buscar_produto_por_nome,
    criar_carrinho,
    buscar_carrinho_aberto,
    adicionar_item_carrinho,
    listar_itens_carrinho
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
    """Detecta nome presumido se tiver estrutura típica."""
    texto = texto.lower()
    match = re.search(r"(?:meu nome é|sou o|sou a|aqui é o|aqui é a|me chamo)\s+([a-zA-ZÀ-ÿ\s]{3,})", texto)
    if match:
        nome = match.group(1).strip().title()
        return nome
    return None

def _detectar_comando_cardapio(texto: str) -> bool:
    """Detecta se usuário quer ver o cardápio"""
    texto = texto.lower()
    palavras_cardapio = ['cardápio', 'cardapio', 'menu', 'produtos', 'hamburguer', 'lanche', 'o que tem']
    return any(palavra in texto for palavra in palavras_cardapio)

def _detectar_adicionar_carrinho(texto: str) -> Optional[str]:
    """Detecta tentativa de adicionar produto ao carrinho"""
    texto = texto.lower()
    patterns = [
        r"quero (?:o |um |uma )?(.+)",
        r"adiciona (?:o |um |uma )?(.+)",
        r"coloca (?:o |um |uma )?(.+)(?:\s+no carrinho)?",
        r"vou querer (?:o |um |uma )?(.+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, texto)
        if match:
            produto = match.group(1).strip()
            # Remove palavras como "no carrinho", "pra mim", etc
            produto = re.sub(r"\s+(no carrinho|pra mim|por favor).*", "", produto)
            return produto
    return None

def _formatar_cardapio(cardapio: list) -> str:
    """Formata cardápio para exibição"""
    if not cardapio:
        return "Eita! Num tem nada no cardápio não, visse!"
    
    texto = "🍔 *CARDÁPIO DA CASA* 🍔\n\n"
    for item in cardapio:
        preco_reais = item['preco_centavos'] / 100
        texto += f"• *{item['nome']}* - R$ {preco_reais:.2f}\n"
    
    texto += "\n💬 Pra pedir, é só falar: *'Quero um [nome do produto]'*"
    return texto

def _formatar_carrinho(itens: list) -> str:
    """Formata itens do carrinho para exibição"""
    if not itens:
        return "Teu carrinho tá vazio ainda, meu rei!"
    
    texto = "🛒 *SEU CARRINHO* 🛒\n\n"
    total_centavos = 0
    
    for item in itens:
        preco_reais = item['preco_centavos'] / 100
        subtotal_reais = item['subtotal_centavos'] / 100
        texto += f"• {item['quantidade']}x *{item['nome']}* - R$ {subtotal_reais:.2f}\n"
        total_centavos += item['subtotal_centavos']
    
    total_reais = total_centavos / 100
    texto += f"\n💰 *Total: R$ {total_reais:.2f}*"
    return texto

@app.post("/")
async def webhook_ultramsg(req: Request):
    body = await req.json()
    if DEBUG:
        logging.info(f"Payload recebido: {body}")

    if body.get("event_type") != "message_received":
        return {"status": "ignorado", "motivo": "evento não é message_received"}

    data = body.get("data", {})
    tipo = data.get("type")

    if tipo != "chat":
        return {"status": "ignorado", "motivo": f"evento {tipo}"}

    texto_cli = data.get("body", "").strip()
    chat_id   = data.get("chatId")
    from_id   = data.get("from")
    pushname  = data.get("pushname", "").strip()

    telefone  = _extrair_telefone(chat_id, from_id)
    if not telefone:
        logging.error("Sem telefone no payload.")
        return {"status": "erro", "detail": "sem telefone"}

    # Busca cliente existente
    cliente = buscar_cliente_por_telefone(telefone)
    contexto = None

    # Se cliente não existe, verifica se forneceu nome
    if not cliente:
        nome_detectado = _detectar_nome(texto_cli)
        nome_para_cadastro = nome_detectado or pushname
        
        if nome_para_cadastro:
            try:
                cliente_id = salvar_novo_cliente(telefone, nome_para_cadastro)
                cliente = {"id": cliente_id, "nome": nome_para_cadastro, "telefone": telefone}
                contexto = f"Oi {nome_para_cadastro}! Te cadastrei aqui rapidinho. Bem-vindo!"
                logging.info(f"Novo cliente cadastrado: {nome_para_cadastro}")
            except Exception as e:
                logging.exception("Erro ao cadastrar cliente: %s", e)
                contexto = "Eita! Deu um problema aqui. Me diga seu nome pra eu te cadastrar direitinho."
        else:
            contexto = "Oi, meu rei! Pra eu te atender melhor, me diga seu nome completo, por favor."

    # Cliente identificado - processar comandos
    if cliente:
        nome_cliente = cliente.get('nome', 'meu rei')
        
        # Comando: Ver cardápio
        if _detectar_comando_cardapio(texto_cli):
            cardapio = buscar_cardapio_ativo()
            resposta = _formatar_cardapio(cardapio)
            try:
                await enviar_mensagem(telefone, resposta)
                return {"status": "ok"}
            except Exception as e:
                logging.exception("Erro ao enviar cardápio: %s", e)
                return {"status": "erro_envio", "detail": str(e)}
        
        # Comando: Adicionar ao carrinho
        produto_desejado = _detectar_adicionar_carrinho(texto_cli)
        if produto_desejado:
            produto = buscar_produto_por_nome(produto_desejado)
            if produto:
                # Busca ou cria carrinho
                carrinho = buscar_carrinho_aberto(cliente['id'])
                if not carrinho:
                    carrinho_id = criar_carrinho(cliente['id'])
                else:
                    carrinho_id = str(carrinho['id'])
                
                # Adiciona produto
                try:
                    adicionar_item_carrinho(carrinho_id, produto['id'])
                    preco_reais = produto['preco_centavos'] / 100
                    resposta = f"Oxente! Coloquei *{produto['nome']}* (R$ {preco_reais:.2f}) no teu carrinho!"
                    
                    # Mostra carrinho atualizado
                    itens = listar_itens_carrinho(carrinho_id)
                    resposta += "\n\n" + _formatar_carrinho(itens)
                    
                except Exception as e:
                    logging.exception("Erro ao adicionar no carrinho: %s", e)
                    resposta = "Eita! Deu problema pra adicionar no carrinho. Tenta de novo, visse?"
            else:
                resposta = f"Oxente! Num achei '{produto_desejado}' no cardápio não. Quer ver o que tem disponível?"
            
            try:
                await enviar_mensagem(telefone, resposta)
                return {"status": "ok"}
            except Exception as e:
                logging.exception("Erro ao enviar resposta do carrinho: %s", e)
                return {"status": "erro_envio", "detail": str(e)}
        
        # Comando: Ver carrinho
        if any(palavra in texto_cli.lower() for palavra in ['carrinho', 'pedido', 'meu pedido']):
            carrinho = buscar_carrinho_aberto(cliente['id'])
            if carrinho:
                itens = listar_itens_carrinho(str(carrinho['id']))
                resposta = _formatar_carrinho(itens)
            else:
                resposta = "Teu carrinho tá vazio ainda, meu rei! Quer dar uma olhada no cardápio?"
            
            try:
                await enviar_mensagem(telefone, resposta)
                return {"status": "ok"}
            except Exception as e:
                logging.exception("Erro ao enviar carrinho: %s", e)
                return {"status": "erro_envio", "detail": str(e)}
        
        # Contexto para IA
        contexto = f"Cliente: {nome_cliente}. Responda como atendente simpático de hamburgueria."

    # Gera resposta via IA
    resposta = gerar_resposta_nordestina(texto_cli, contexto)
    logging.info(f"Resposta gerada pela LLM: {resposta}")

    try:
        await enviar_mensagem(telefone, resposta)
    except Exception as e:
        logging.exception("Falha ao enviar via UltraMsg: %s", e)
        return {"status": "erro_envio", "detail": str(e)}

    return {"status": "ok"}
