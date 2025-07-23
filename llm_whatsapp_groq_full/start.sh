#!/bin/bash
set -e
# Carrega .env se existir
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
