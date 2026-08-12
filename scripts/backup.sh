#!/bin/sh
# ==============================================================================
# Backup do volume de dados (banco SQLite + fotos + assinaturas geradas).
#
# Uso manual:
#   ./scripts/backup.sh
#
# Uso automático (recomendado): agende no cron da VPS, por exemplo todo dia
# às 3h da manhã. Na VPS, rode "crontab -e" e adicione uma linha como:
#   0 3 * * * cd /caminho/do/projeto && ./scripts/backup.sh >> /var/log/backup-assinaturas.log 2>&1
#
# Os backups ficam em ./backups/, um arquivo .tar.gz por dia. Este script não
# apaga backups antigos sozinho — apague manualmente ou ajuste o "find" no
# final se quiser limpeza automática (ex.: manter só os últimos 30 dias).
# ==============================================================================
set -e

cd "$(dirname "$0")/.."

VOLUME_NAME="email_signature_system_signature_instance"
BACKUP_DIR="./backups"
DATA_HOJE="$(date +%F)"

mkdir -p "$BACKUP_DIR"

docker run --rm \
    -v "${VOLUME_NAME}:/data:ro" \
    -v "$(pwd)/${BACKUP_DIR}:/backup" \
    alpine \
    tar czf "/backup/instance-${DATA_HOJE}.tar.gz" -C /data .

echo "Backup salvo em ${BACKUP_DIR}/instance-${DATA_HOJE}.tar.gz"

# Descomente para manter só os últimos 30 dias de backup automaticamente:
# find "$BACKUP_DIR" -name "instance-*.tar.gz" -mtime +30 -delete
