import os

ULTRAMSG_INSTANCE_ID = os.getenv("ULTRAMSG_INSTANCE_ID", "instance134752").strip()
ULTRAMSG_TOKEN       = os.getenv("ULTRAMSG_TOKEN", "").strip()
ULTRAMSG_BASE_URL    = os.getenv("ULTRAMSG_BASE_URL", "https://api.ultramsg.com").rstrip("/")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL           = os.getenv("GROQ_MODEL", "llama3-8b-8192")
DATABASE_URL         = os.getenv("DATABASE_URL", "").strip()
DEBUG                = os.getenv("DEBUG", "false").lower() in ("1","true","yes","y")
