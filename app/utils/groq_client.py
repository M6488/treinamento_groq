import os
import requests
from typing import Optional
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.utils.nordeste import nordestinizar

_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

GROQ_MODELS_VALIDOS = [
    "llama3-8b-8192",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it"
]

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
    
    if GROQ_MODEL not in GROQ_MODELS_VALIDOS:
        return f"Modelo configurado inválido: {GROQ_MODEL}. Escolha entre: {', '.join(GROQ_MODELS_VALIDOS)}"
    
    user_prompt = mensagem if contexto is None else f"{contexto}\n\nMensagem do cliente: {mensagem}"
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 200,
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(_GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
       
        print(f"[DEBUG Groq] Status: {resp.status_code}, Response: {resp.text}")
        
        resp.raise_for_status()
        data = resp.json()
        resposta = data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as http_err:
        resposta = f"Eita! Erro HTTP na IA ({resp.status_code}): {resp.text}"
    except requests.exceptions.RequestException as req_err:
        resposta = f"Eita! Não consegui conectar com a IA ({req_err})"
    except KeyError:
        resposta = f"Eita! Resposta inesperada da IA: {resp.text}"
    
    resposta = nordestinizar(resposta, add_tail=True)
    return resposta
