"""Helpers de arquivos em disco ligados a registros do banco.

Centraliza a remoção física dos arquivos de uma assinatura (imagem gerada e
QR Code enviado) para que TODOS os fluxos que apagam registros — cancelamento
pelo usuário, limpeza de pendentes abandonados e exclusão de usuário pelo
admin — removam também os arquivos, sem deixar lixo órfão acumulando no disco.
"""
import os

from flask import current_app


def delete_record_files(record) -> None:
    """Remove do disco os arquivos (imagem final e QR Code) de um SignatureRecord.

    Nunca levanta exceção por falha de I/O — apenas loga um aviso; a exclusão
    do registro no banco não deve ser bloqueada por um arquivo já ausente.
    """
    for folder_key, filename in (
        ("GENERATED_UPLOAD_DIR", record.output_filename),
        ("PHOTOS_UPLOAD_DIR", record.photo_filename),
    ):
        if not filename:
            continue
        path = os.path.join(current_app.config[folder_key], filename)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            current_app.logger.warning("Falha ao remover arquivo %s", path)
