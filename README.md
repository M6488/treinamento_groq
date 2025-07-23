# LLM WhatsApp Bot (Groq + UltraMsg + PostgreSQL + Nordestinês)

Este projeto cria um atendente de restaurante com sotaque nordestino, que atende no WhatsApp via **UltraMsg**, gera respostas usando **Groq (LLaMA3)** e identifica clientes pelo **telefone do WhatsApp** ou pelo **CPF** consultando um banco PostgreSQL.

---

## 🚀 Recursos
- Recebe mensagens do WhatsApp (UltraMsg Webhook).
- Busca cliente no banco pelo número.
- Pede CPF se não encontrar cadastro.
- Chama Groq LLM remoto (sem peso local).
- Aplica sotaque nordestino controlado.
- Retorna mensagem ao cliente via UltraMsg.

---

## 📦 Instalação

```bash
git clone <SEU_REPO>
cd llm-whatsapp-bot
pip install -r requirements.txt
```

---

## ⚙️ Configuração de ambiente

Crie `.env` (ou configure variáveis no Render) usando o modelo:

```env
ULTRAMSG_BASE_URL=https://api.ultramsg.com
ULTRAMSG_INSTANCE_ID=SEU_INSTANCE_ID
ULTRAMSG_TOKEN=SEU_TOKEN

GROQ_API_KEY=SEU_GROQ_API_KEY
GROQ_MODEL=llama3-8b-8192

DATABASE_URL=postgresql://usuario:senha@host:5432/seubanco

DEBUG=true
```

---

## 🗄️ Estrutura de tabela esperada

```sql
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf  VARCHAR(14) UNIQUE,       -- pode armazenar com máscara
    telefone VARCHAR(20) UNIQUE    -- armazene com +55... ou só dígitos
);
```

> Se já tem tabela com nomes diferentes, ajuste `db.py`.

---

## 🧪 Teste local

1. Rode:
   ```bash
   bash start.sh
   ```
2. Envie um POST simulando UltraMsg:
   ```bash
   curl -X POST http://localhost:10000/      -H "Content-Type: application/json"      -d '{"type":"chat","chatId":"558199999999@c.us","body":"Oi, quero ver o cardápio"}'
   ```

---

## 🌐 Deploy no Render

- Novo **Web Service**.
- Build command:
  ```bash
  pip install -r requirements.txt
  ```
- Start command:
  ```bash
  bash start.sh
  ```
- Configure variáveis de ambiente no painel do Render (não suba `.env` real).

---

## 🔁 Configurar Webhook no UltraMsg

Defina a URL:
```
https://SEU-SERVICO.onrender.com/
```

---

## 🤝 Contribuições
Sugira novas gírias nordestinas ou fluxos de identificação de cliente!

---
