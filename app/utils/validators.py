"""Validação server-side de arquivos de imagem enviados pelo usuário.

Nunca confia apenas na extensão do arquivo ou no Content-Type enviado pelo
navegador: o conteúdo é aberto e verificado com Pillow antes de ser aceito.
"""
import os
import unicodedata
import uuid

from PIL import Image, UnidentifiedImageError


def normalize_search_text(value: str) -> str:
    """Remove acentos e caixa para comparação de nomes tolerante a variação
    de digitação (ex.: "joao" encontra "João"). Usado pela busca pública de
    assinaturas (sem login) e por outros pontos que já faziam isso de forma
    duplicada (importação em lote)."""
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


class ImageValidationError(Exception):
    """Erro de validação com mensagem segura para exibir ao usuário final."""


def validate_and_open_image(file_storage, max_bytes: int, max_dimension: int) -> Image.Image:
    """Valida um FileStorage do Flask e devolve um objeto PIL.Image já carregado
    em memória (pronto para uso, sem depender do stream original).

    Levanta ImageValidationError com mensagem amigável em qualquer falha —
    nunca deixa uma exceção de baixo nível (Pillow/OS) vazar para o usuário.
    """
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise ImageValidationError("Nenhum arquivo enviado.")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size == 0:
        raise ImageValidationError("O arquivo enviado está vazio.")
    if size > max_bytes:
        raise ImageValidationError(
            f"O arquivo excede o tamanho máximo permitido ({max_bytes // (1024 * 1024)}MB)."
        )

    # 1ª leitura: apenas valida integridade (img.verify() invalida o objeto para uso posterior)
    try:
        probe = Image.open(file_storage.stream)
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageValidationError("O arquivo enviado não é uma imagem válida (PNG ou JPG).")

    # 2ª leitura: reabre o stream (já reposicionado) e carrega de fato os pixels
    file_storage.stream.seek(0)
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageValidationError("Não foi possível processar a imagem enviada.")

    if img.format not in ("PNG", "JPEG"):
        raise ImageValidationError("Formato de imagem não suportado. Envie PNG ou JPG.")

    if img.width > max_dimension or img.height > max_dimension:
        raise ImageValidationError(
            f"A imagem excede a dimensão máxima permitida ({max_dimension}px)."
        )
    if img.width < 10 or img.height < 10:
        raise ImageValidationError("A imagem enviada é inválida ou está corrompida.")

    return img


def generate_safe_filename(extension: str) -> str:
    """Gera um nome de arquivo aleatório e seguro (evita path traversal e
    colisão/sobrescrita de arquivos de outros usuários)."""
    ext = (extension or "png").lower().lstrip(".")
    if ext not in ("png", "jpg", "jpeg"):
        ext = "png"
    return f"{uuid.uuid4().hex}.{ext}"


def is_valid_cpf(digits: str) -> bool:
    """Valida um CPF (só dígitos, 11 caracteres) pelos dígitos verificadores
    oficiais (mod 11) — usada onde o CPF vira login/senha (Novo Usuário e
    Importar CPFs), para recusar CPFs com formato certo mas inválidos (ex.:
    digitados errado) e sequências óbvias como "00000000000"/"11111111111".

    Recebe só os dígitos (sem pontuação) e não levanta exceção: retorna
    False para qualquer entrada que não seja um CPF válido.
    """
    digits = "".join(ch for ch in str(digits or "") if ch.isdigit())
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    def _check_digit(cpf_partial: str) -> int:
        weight = len(cpf_partial) + 1
        total = sum(int(d) * (weight - i) for i, d in enumerate(cpf_partial))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first = _check_digit(digits[:9])
    if first != int(digits[9]):
        return False
    second = _check_digit(digits[:10])
    if second != int(digits[10]):
        return False
    return True


PHONE_ALLOWED_CHARS = set("0123456789()+- ")


def sanitize_plain_text(value: str, max_len: int) -> str:
    """Remove caracteres de controle e limita o tamanho de um campo de texto
    livre antes de persistir/renderizar (defesa em profundidade)."""
    if not value:
        return ""
    cleaned = "".join(ch for ch in value if ch == "\t" or ord(ch) >= 32)
    return cleaned.strip()[:max_len]
