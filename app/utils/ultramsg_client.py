"""Cliente UltraMsg simples para enviar mensagens."""
import httpx
from app.config import ULTRAMSG_BASE_URL, ULTRAMSG_INSTANCE_ID, ULTRAMSG_TOKEN

def ultramsg_url(path: str) -> str:
    return f"{ULTRAMSG_BASE_URL}/{ULTRAMSG_INSTANCE_ID}{path}"

async def enviar_mensagem(telefone: str, texto: str):
    # UltraMsg exige 'to' sem @c.us; aceita +55.. ou só dígitos.
    async with httpx.AsyncClient() as cli:
        resp = await cli.post(
        ultramsg_url(f"/messages/chat?token={ULTRAMSG_TOKEN}"),
        data={
              "to": telefone,
             "body": texto,
    },
    timeout=60,
)
