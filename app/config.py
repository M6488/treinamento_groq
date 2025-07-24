import os
import logging


ULTRAMSG_INSTANCE_ID = os.getenv("ULTRAMSG_INSTANCE_ID", "instance134752").strip()
ULTRAMSG_TOKEN       = os.getenv("ULTRAMSG_TOKEN", "").strip()
ULTRAMSG_BASE_URL    = os.getenv("ULTRAMSG_BASE_URL", "https://api.ultramsg.com").rstrip("/")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL           = os.getenv("GROQ_MODEL", "llama3-8b-8192")
DATABASE_URL         = os.getenv("DATABASE_URL", "").strip()
DEBUG                = os.getenv("DEBUG", "false").lower() in ("1","true","yes","y")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
RENDER_ENV = os.getenv("RENDER", False)  # Render define essa variável automaticamente

# Configuração específica para Render
if RENDER_ENV:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Força saída para stdout
        ]
    )
else:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)