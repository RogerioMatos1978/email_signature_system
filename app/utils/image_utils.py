"""Composição server-side da imagem final da assinatura.

Combina: imagem de fundo (definida pelo admin) + campos de texto do usuário +
QR Code do WhatsApp (opcional), gerando um único PNG/JPG pronto para ser
usado como assinatura no Outlook.
"""
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .template_fields import DEFAULTS_BY_VARIANT, TEXT_FIELD_KEYS, normalize_variant

_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts")
# Neo Sans / Neo Sans Bold: extraídas do PowerPoint oficial "Assinatura de
# e-mail 2026.pptx" (fontes embutidas em ppt/fonts/*.fntdata, formato EOT sem
# compressão MTX nem criptografia — extração direta e legítima da fonte já
# licenciada e embutida pela própria organização no seu modelo oficial).
# DejaVuSans continua como fallback caso os arquivos não estejam presentes.
_FONT_REGULAR = os.path.join(_FONTS_DIR, "NeoSans-Regular.otf")
_FONT_BOLD = os.path.join(_FONTS_DIR, "NeoSans-Bold.otf")
_FONT_REGULAR_FALLBACK = os.path.join(_FONTS_DIR, "DejaVuSans.ttf")
_FONT_BOLD_FALLBACK = os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")

_font_cache: dict = {}


class SignatureRenderError(Exception):
    """Erro amigável para qualquer falha na composição da imagem."""


def _load_font(bold: bool, size) -> ImageFont.FreeTypeFont:
    # Tamanhos podem ter casas decimais (ex.: 37.8, 29.4 — valores exatos do
    # PowerPoint oficial). Freetype/Pillow suportam tamanho fracionário.
    size = max(6.0, min(float(size), 200.0))  # limites sãos, evita fontes absurdas
    cache_key = (bold, round(size, 1))
    cached = _font_cache.get(cache_key)
    if cached is not None:
        return cached

    primary = _FONT_BOLD if bold else _FONT_REGULAR
    fallback = _FONT_BOLD_FALLBACK if bold else _FONT_REGULAR_FALLBACK
    try:
        font = ImageFont.truetype(primary, size=size)
    except OSError:
        try:
            font = ImageFont.truetype(fallback, size=size)
        except OSError:
            font = ImageFont.load_default()
    _font_cache[cache_key] = font
    return font


def _fit_text(draw: "ImageDraw.ImageDraw", text: str, bold: bool, max_width: int, start_size, min_size: float = 10.0):
    """Reduz progressivamente o tamanho da fonte até o texto caber em
    max_width; se ainda assim não couber no tamanho mínimo, trunca com "…".
    Evita o bug clássico de texto vazando para fora da caixa/assinatura."""
    if max_width <= 0:
        max_width = 50

    size = max(float(start_size), min_size)
    font = _load_font(bold, size)
    while size > min_size:
        font = _load_font(bold, size)
        if draw.textlength(text, font=font) <= max_width:
            return font, text
        size -= 1

    font = _load_font(bold, min_size)
    truncated = text
    while truncated and draw.textlength(truncated + "…", font=font) > max_width:
        truncated = truncated[:-1]
    return font, (truncated + "…") if truncated and truncated != text else (truncated or text[:1])


def render_signature(
    background_path: str,
    fields_config: dict,
    values: dict,
    photo_path: Optional[str],
    output_path: str,
    output_format: str = "png",
    max_width: int = 1300,
    jpeg_quality: int = 88,
    variant: str = "sem_foto",
) -> None:
    """Gera a imagem final da assinatura e salva em output_path.

    - background_path: caminho absoluto da imagem de fundo do modelo ativo
    - fields_config: dict retornado por SignatureTemplate.get_fields()
    - values: dict com full_name/role_title/unit/signature_email/phone validados
    - photo_path: caminho absoluto da foto do colaborador (variante com_foto), ou None
    - output_format: "png" ou "jpg"
    - variant: "sem_foto" | "com_foto" (define os padrões de posição/cor)
    """
    variant = normalize_variant(variant)
    defaults = DEFAULTS_BY_VARIANT[variant]
    if not background_path or not os.path.isfile(background_path):
        raise SignatureRenderError("Imagem de modelo não encontrada. Contate o administrador.")

    try:
        base = Image.open(background_path).convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha do Pillow aqui
        raise SignatureRenderError("Não foi possível abrir a imagem de modelo.") from exc

    # Limita a resolução final (bom equilíbrio nitidez/tamanho de arquivo para e-mail)
    if base.width > max_width:
        ratio = max_width / base.width
        new_size = (max_width, max(1, int(base.height * ratio)))
        base = base.resize(new_size, Image.LANCZOS)

    canvas_w, canvas_h = base.size
    draw = ImageDraw.Draw(base)

    for field_key in TEXT_FIELD_KEYS:
        text_value = (values.get(field_key) or "").strip()
        if not text_value:
            continue

        cfg = {**defaults["text"][field_key], **(fields_config.get(field_key) or {})}
        text_value = text_value[: int(cfg.get("max_chars", 60))]

        x = int(float(cfg.get("x_pct", 0.05)) * canvas_w)
        y = int(float(cfg.get("y_pct", 0.5)) * canvas_h)
        max_box_width = max(20, int(float(cfg.get("box_width_pct", 0.6)) * canvas_w))

        font, fitted_text = _fit_text(
            draw, text_value, bool(cfg.get("bold")), max_box_width, float(cfg.get("font_size", 18))
        )

        align = cfg.get("align", "left")
        if align in ("center", "right"):
            text_w = draw.textlength(fitted_text, font=font)
            if align == "center":
                x = int(x - text_w / 2)
            else:
                x = int(x - text_w)

        color = cfg.get("color") or "#1f2937"
        draw.text((max(0, x), max(0, y)), fitted_text, font=font, fill=color)

    if photo_path and os.path.isfile(photo_path) and defaults["photo"] is not None:
        try:
            p_cfg = {**defaults["photo"], **(fields_config.get("photo") or {})}
            photo = Image.open(photo_path).convert("RGBA")
            photo = ImageOps.exif_transpose(photo)

            box_w = max(20, int(float(p_cfg["width_pct"]) * canvas_w))
            box_h = max(20, int(float(p_cfg["height_pct"]) * canvas_h))

            # Corte "cover": preenche a caixa inteira mantendo a proporção da
            # foto (recorta o excesso centralizado) — nunca distorce o rosto.
            photo = ImageOps.fit(photo, (box_w, box_h), Image.LANCZOS, centering=(0.5, 0.5))

            px = int(float(p_cfg["x_pct"]) * canvas_w)
            py = int(float(p_cfg["y_pct"]) * canvas_h)
            px = max(0, min(px, canvas_w - box_w))
            py = max(0, min(py, canvas_h - box_h))

            base.alpha_composite(photo, dest=(px, py))

            border_px = int(p_cfg.get("border_px", 3))
            if border_px > 0:
                border_color = p_cfg.get("border_color") or "#008BD2"
                for i in range(border_px):
                    draw.rectangle(
                        (px + i, py + i, px + box_w - 1 - i, py + box_h - 1 - i),
                        outline=border_color,
                    )
        except Exception as exc:  # noqa: BLE001
            raise SignatureRenderError("Não foi possível compor a foto na assinatura.") from exc

    output_format = (output_format or "png").lower()
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        if output_format == "jpg":
            flat = Image.new("RGB", base.size, (255, 255, 255))
            flat.paste(base, mask=base.split()[3])
            flat.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
        else:
            base.save(output_path, "PNG", optimize=True)
    except Exception as exc:  # noqa: BLE001
        raise SignatureRenderError("Falha ao salvar a imagem final da assinatura.") from exc


def get_image_dimensions(path: str) -> tuple:
    with Image.open(path) as img:
        return img.width, img.height
