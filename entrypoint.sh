#!/bin/sh
set -e

echo "[entrypoint] Verificando estrutura do banco de dados..."
python -c "
from app import create_app
from app.extensions import db
from app.seed import seed_admin, seed_templates

app = create_app()
with app.app_context():
    db.create_all()
    seed_admin(app)
    seed_templates(app)
print('[entrypoint] Banco de dados pronto.')
"

PORT="${PORT:-5002}"
WORKERS="${GUNICORN_WORKERS:-2}"

echo "[entrypoint] Iniciando Gunicorn na porta ${PORT}..."
# --worker-tmp-dir /dev/shm: boa prática para Gunicorn em Docker — o arquivo de
# heartbeat dos workers fica em memória, evitando travas/timeouts espúrios
# quando o /tmp do container é lento (overlayfs).
exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --threads 4 \
    --timeout 60 \
    --graceful-timeout 30 \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
