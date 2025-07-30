from fastapi import FastAPI, Request
import logging
import sys
from typing import Optional
import traceback

from app.config import DEBUG, logger
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

app = FastAPI(title="WhatsApp Bot Hamburgueria", version="1.0.0")

logger.info("🚀 Aplicação iniciada!")
logger.info(f"🔧 Debug mode: {DEBUG}")
logger.info(f"🖥️ Python version: {sys.version}")

def _only_digits(s: str) -> str:
    import re
    return re.sub(r"\D+", "", s or "")

def _extrair_telefone(raw_chat_id: Optional[str], raw_from: Optional[str]) -> Optional[str]:
    val = raw_chat_id or raw_from
    if not val:
        return None
    num = val.split("@")[0]
    return _only_digits(num)

def _detectar_nome(texto: str) -> Optional[str]:
    import re
    texto = texto.lower()
    match = re.search(r"(?:meu nome é|sou o|sou a|aqui é o|aqui é a|me chamo)\s+([a-zA-ZÀ-ÿ\s]{3,})", texto)
    if match:
        nome = match.group(1).strip().title()
        return nome
    return None

def _detectar_comando_cardapio(texto: str) -> bool:
    texto = texto.lower()
    palavras_cardapio = ['cardápio', 'cardapio', 'menu', 'produtos', 'hamburguer', 'lanche', 'o que tem']
    return any(palavra in texto for palavra in palavras_cardapio)

def _detectar_adicionar_carrinho(texto: str) -> Optional[str]:
    import re
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
            produto = re.sub(r"\s+(no carrinho|pra mim|por favor).*", "", produto)
            return produto
    return None

def _formatar_cardapio(cardapio: list) -> str:
    if not cardapio:
        return "Eita! Num tem nada no cardápio não, visse!"
    
    texto = "🍔 *CARDÁPIO DA CASA* 🍔\n\n"
    for item in cardapio:
        preco_reais = item['preco_centavos'] / 100
        texto += f"• *{item['nome']}* - R$ {preco_reais:.2f}\n"
    
    texto += "\n💬 Pra pedir, é só falar: *'Quero um [nome do produto]'*"
    return texto

def _formatar_carrinho(itens: list) -> str:
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

@app.get("/")
async def health_check():
    """Endpoint de saúde para verificar se a aplicação está rodando"""
    logger.info("✅ Health check chamado")
    return {
        "status": "ok", 
        "message": "Bot WhatsApp funcionando!",
        "debug": DEBUG
    }

@app.get("/test-db")
async def test_database():
    """Endpoint para testar conexão com banco"""
    try:
        cardapio = buscar_cardapio_ativo()
        logger.info(f"✅ Teste de DB: {len(cardapio)} itens no cardápio")
        return {"status": "ok", "cardapio_count": len(cardapio)}
    except Exception as e:
        logger.error(f"❌ Erro no teste de DB: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/")
async def webhook_ultramsg(req: Request):
    try:
        logger.info("📨 Webhook chamado!")
        
        body = await req.json()
        logger.info(f"📋 Payload recebido: {body}")

        if body.get("event_type") != "message_received":
            logger.info(f"⏭️  Ignorando evento: {body.get('event_type')}")
            return {"status": "ignorado", "motivo": "evento não é message_received"}

        data = body.get("data", {})
        tipo = data.get("type")

        if tipo != "chat":
            logger.info(f"⏭️  Ignorando tipo: {tipo}")
            return {"status": "ignorado", "motivo": f"evento {tipo}"}

        texto_cli = data.get("body", "").strip()
        chat_id   = data.get("chatId")
        from_id   = data.get("from")
        pushname  = data.get("pushname", "").strip()

        logger.info(f"💬 Mensagem recebida: '{texto_cli}' de {pushname}")

        telefone = _extrair_telefone(chat_id, from_id)
        if not telefone:
            logger.error("❌ Sem telefone no payload")
            return {"status": "erro", "detail": "sem telefone"}

        logger.info(f"📱 Telefone extraído: {telefone}")

        cliente = buscar_cliente_por_telefone(telefone)
        logger.info(f"👤 Cliente encontrado: {cliente is not None}")

        contexto = None

        if not cliente:
            logger.info("🆕 Cliente novo, verificando nome...")
            nome_detectado = _detectar_nome(texto_cli)
            nome_para_cadastro = nome_detectado or pushname
            
            if nome_para_cadastro:
                try:
                    logger.info(f"💾 Cadastrando cliente: {nome_para_cadastro}")
                    cliente_id = salvar_novo_cliente(telefone, nome_para_cadastro)
                    cliente = {"id": cliente_id, "nome": nome_para_cadastro, "telefone": telefone}
                    contexto = f"Oi {nome_para_cadastro}! Te cadastrei aqui rapidinho. Bem-vindo!"
                    logger.info(f"✅ Cliente cadastrado com ID: {cliente_id}")
                except Exception as e:
                    logger.exception(f"❌ Erro ao cadastrar cliente: {e}")
                    contexto = "Eita! Deu um problema aqui. Me diga seu nome pra eu te cadastrar direitinho."
            else:
                logger.info("❓ Nome não detectado, pedindo para cliente se identificar")
                contexto = "Oi, meu rei! Pra eu te atender melhor, me diga seu nome completo, por favor."

        if cliente:
            nome_cliente = cliente.get('nome', 'meu rei')
            logger.info(f"🎯 Processando comandos para cliente: {nome_cliente}")
            
            if _detectar_comando_cardapio(texto_cli):
                logger.info("📋 Comando: mostrar cardápio")
                cardapio = buscar_cardapio_ativo()
                resposta = _formatar_cardapio(cardapio)
                logger.info(f"📤 Enviando cardápio com {len(cardapio)} itens")
                
                try:
                    await enviar_mensagem(telefone, resposta)
                    logger.info("✅ Cardápio enviado com sucesso")
                    return {"status": "ok"}
                except Exception as e:
                    logger.exception(f"❌ Erro ao enviar cardápio: {e}")
                    return {"status": "erro_envio", "detail": str(e)}

            produto_desejado = _detectar_adicionar_carrinho(texto_cli)
            if produto_desejado:
                logger.info(f"🛒 Comando: adicionar produto '{produto_desejado}'")
                produto = buscar_produto_por_nome(produto_desejado)
                
                if produto:
                    logger.info(f"✅ Produto encontrado: {produto['nome']}")

                    carrinho = buscar_carrinho_aberto(cliente['id'])
                    if not carrinho:
                        carrinho_id = criar_carrinho(cliente['id'])
                        logger.info(f"🆕 Carrinho criado: {carrinho_id}")
                    else:
                        carrinho_id = str(carrinho['id'])
                        logger.info(f"📦 Usando carrinho existente: {carrinho_id}")
                    
                    try:
                        adicionar_item_carrinho(carrinho_id, produto['id'])
                        preco_reais = produto['preco_centavos'] / 100
                        resposta = f"Oxente! Coloquei *{produto['nome']}* (R$ {preco_reais:.2f}) no teu carrinho!"
                        
                        #aqui o carrinho atualizado
                        itens = listar_itens_carrinho(carrinho_id)
                        resposta += "\n\n" + _formatar_carrinho(itens)
                        logger.info("✅ Produto adicionado ao carrinho")
                        
                    except Exception as e:
                        logger.exception(f"❌ Erro ao adicionar no carrinho: {e}")
                        resposta = "Eita! Deu problema pra adicionar no carrinho. Tenta de novo, visse?"
                else:
                    logger.info(f"❌ Produto não encontrado: {produto_desejado}")
                    resposta = f"Oxente! Num achei '{produto_desejado}' no cardápio não. Quer ver o que tem disponível?"
                
                try:
                    await enviar_mensagem(telefone, resposta)
                    logger.info("✅ Resposta do carrinho enviada")
                    return {"status": "ok"}
                except Exception as e:
                    logger.exception(f"❌ Erro ao enviar resposta do carrinho: {e}")
                    return {"status": "erro_envio", "detail": str(e)}
            
            
            if any(palavra in texto_cli.lower() for palavra in ['carrinho', 'pedido', 'meu pedido']):
                logger.info("👀 Comando: ver carrinho")
                carrinho = buscar_carrinho_aberto(cliente['id'])
                if carrinho:
                    itens = listar_itens_carrinho(str(carrinho['id']))
                    resposta = _formatar_carrinho(itens)
                    logger.info(f"📦 Mostrando carrinho com {len(itens)} itens")
                else:
                    resposta = "Teu carrinho tá vazio ainda, meu rei! Quer dar uma olhada no cardápio?"
                    logger.info("📦 Carrinho vazio")
                
                try:
                    await enviar_mensagem(telefone, resposta)
                    logger.info("✅ Carrinho enviado")
                    return {"status": "ok"}
                except Exception as e:
                    logger.exception(f"❌ Erro ao enviar carrinho: {e}")
                    return {"status": "erro_envio", "detail": str(e)}
            
            
            contexto = f"Cliente: {nome_cliente}. Responda como atendente simpático de hamburgueria."

        logger.info("🤖 Gerando resposta via IA...")
        resposta = gerar_resposta_nordestina(texto_cli, contexto)
        logger.info(f"💭 Resposta gerada: {resposta}")

        try:
            await enviar_mensagem(telefone, resposta)
            logger.info("✅ Mensagem enviada com sucesso!")
        except Exception as e:
            logger.exception(f"❌ Falha ao enviar via UltraMsg: {e}")
            return {"status": "erro_envio", "detail": str(e)}

        return {"status": "ok"}

    except Exception as e:
        logger.exception(f"💥 Erro geral no webhook: {e}")
        logger.error(f"🔍 Traceback completo: {traceback.format_exc()}")
        return {"status": "erro", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Iniciando servidor na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
