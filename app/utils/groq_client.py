"""Cliente Groq para gerar respostas com sotaque nordestino."""
import os
import requests
from typing import Optional
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.utils.nordeste import nordestinizar

_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "Você é um atendente virtual simpático de uma hamburgueria/restaurante chamado Brasas. "
    "Responda em português, com carinho, simplicidade e algumas expressões regionais, "
    "mas mantendo clareza e profissionalismo. Não exagere na gíria a ponto de dificultar entendimento. "
    "Você pode ajudar com: cardápio, pedidos, carrinho, dúvidas sobre produtos. "
    "Seja prestativo e alegre, como um bom nordestino!"
)

def gerar_resposta_nordestina(mensagem: str, contexto: Optional[str] = None) -> str:
    if not GROQ_API_KEY:
        return "Configuração de LLM ausente. Fale com o suporte, visse?"
    
    user_prompt = mensagem if contexto is None else f"{contexto}\n\nMensagem do cliente: {mensagem}"
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 120,  # Aumentei um pouco o limite
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(_GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        resposta = data["choices"][0]["message"]["content"]
    except Exception as e:
        resposta = f"Eita! Num consegui falar com a inteligência agora não ({e}). Tenta de novo daqui a pouco."
    
    resposta = nordestinizar(resposta, add_tail=True)
    return resposta
