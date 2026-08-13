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


# ---------------------------------------------------------------------------
# Ícones (e-mail / telefone / WhatsApp) — desenhados proceduralmente com PIL,
# não com glifos Unicode: a fonte Neo Sans embutida no PPTX oficial não tem
# cobertura de símbolos (envelope, telefone etc.), então usar caracteres como
# "✉" ou "☎" resultaria em um quadrado vazio ("tofu") na imagem final. Cada
# ícone é desenhado numa tela em resolução 4x (supersampling) e depois
# reduzido com LANCZOS — isso deixa os traços suaves, sem serrilhado.
# ---------------------------------------------------------------------------
_ICON_SUPERSAMPLE = 4


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    hex_color = (hex_color or "#FFFFFF").lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16), alpha)


def _new_icon_canvas(size_px: int):
    ss = max(4, size_px * _ICON_SUPERSAMPLE)
    return Image.new("RGBA", (ss, ss), (0, 0, 0, 0)), ss


def _draw_envelope_icon(size_px: int, color: str) -> "Image.Image":
    """E-mail: corpo com cantos arredondados + vinco em "V" — mesmas
    proporções do envelope do favicon (app/static/img/favicon.ico), só que em
    traço (contorno) em vez de preenchido, para não pesar ao lado do texto
    fino da assinatura."""
    canvas, ss = _new_icon_canvas(size_px)
    d = ImageDraw.Draw(canvas)
    rgba = _hex_to_rgba(color)
    line_w = max(2, int(ss * 0.045))
    pad_x = int(ss * 0.06)
    top = int(ss * 0.22)
    bottom = ss - top
    left, right = pad_x, ss - pad_x
    corner_radius = int((right - left) * 0.09)
    d.rounded_rectangle([left, top, right, bottom], radius=corner_radius, outline=rgba, width=line_w)
    flap_bottom = top + (bottom - top) * 0.56
    d.line([(left, top), (ss / 2, flap_bottom), (right, top)], fill=rgba, width=line_w, joint="curve")
    return canvas.resize((size_px, size_px), Image.LANCZOS)


def _draw_phone_icon(size_px: int, color: str) -> "Image.Image":
    """Telefone: silhueta de aparelho (retângulo vertical arredondado, com
    "alto-falante" no topo e botão na base) — reconhecível de imediato como
    "telefone", ao contrário de um ícone abstrato de linha/cápsula."""
    canvas, ss = _new_icon_canvas(size_px)
    d = ImageDraw.Draw(canvas)
    rgba = _hex_to_rgba(color)
    line_w = max(2, int(ss * 0.05))
    w = ss * 0.46
    h = ss * 0.86
    left = (ss - w) / 2
    top = (ss - h) / 2
    right = left + w
    bottom = top + h
    radius = w * 0.22
    d.rounded_rectangle([left, top, right, bottom], radius=radius, outline=rgba, width=line_w)

    speaker_w = w * 0.34
    speaker_y = top + h * 0.14
    d.line(
        [(ss / 2 - speaker_w / 2, speaker_y), (ss / 2 + speaker_w / 2, speaker_y)],
        fill=rgba, width=line_w, joint="curve",
    )

    btn_r = w * 0.10
    btn_y = bottom - h * 0.11
    d.ellipse([ss / 2 - btn_r, btn_y - btn_r, ss / 2 + btn_r, btn_y + btn_r], outline=rgba, width=line_w)
    return canvas.resize((size_px, size_px), Image.LANCZOS)


def _draw_whatsapp_icon(size_px: int, color: str) -> "Image.Image":
    """WhatsApp: balão de conversa (retângulo arredondado + "rabinho")."""
    canvas, ss = _new_icon_canvas(size_px)
    d = ImageDraw.Draw(canvas)
    rgba = _hex_to_rgba(color)
    line_w = max(2, int(ss * 0.09))
    pad = int(ss * 0.10)
    left, top, right, bottom = pad, pad, ss - pad, int(ss * 0.72)
    radius = int((bottom - top) * 0.32)
    d.rounded_rectangle([left, top, right, bottom], radius=radius, outline=rgba, width=line_w)
    tail_w = (right - left) * 0.22
    tail = [
        (left + (right - left) * 0.20, bottom - line_w * 0.5),
        (left + (right - left) * 0.10, ss - pad * 0.3),
        (left + (right - left) * 0.20 + tail_w, bottom - line_w * 0.5),
    ]
    d.polygon(tail, fill=rgba)
    return canvas.resize((size_px, size_px), Image.LANCZOS)


# Só os campos "de contato" recebem ícone — Nome/Função/Unidade nunca têm um.
_ICON_DRAWERS = {
    "signature_email": _draw_envelope_icon,
    "phone": _draw_phone_icon,
    "whatsapp": _draw_whatsapp_icon,
}

# QR Code do WhatsApp (opcional, só na geração individual — "Gerar
# assinatura"; nunca disponível na importação de planilha): dimensão fixa
# pedida explicitamente (32x32px, "vertical-align: middle"), ao contrário dos
# ícones procedurais acima, cujo tamanho acompanha o tamanho da fonte.
WHATSAPP_QR_SIZE = 32


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
    with_icons: bool = False,
    qrcode_path: Optional[str] = None,
) -> None:
    """Gera a imagem final da assinatura e salva em output_path.

    - background_path: caminho absoluto da imagem de fundo do modelo ativo
    - fields_config: dict retornado por SignatureTemplate.get_fields()
    - values: dict com full_name/role_title/unit/signature_email/phone/whatsapp
    - photo_path: caminho absoluto da foto do colaborador (variante com_foto), ou None
    - output_format: "png" ou "jpg"
    - variant: "sem_foto" | "com_foto" (define os padrões de posição/cor)
    - with_icons: se True, desenha um ícone antes de e-mail/telefone/whatsapp
      (só quando o campo estiver alinhado à esquerda — os únicos casos usados
      hoje pelos padrões FIEG 2026)
    - qrcode_path: caminho absoluto de um QR Code (imagem enviada pelo próprio
      usuário) a inserir em 32x32px na frente do número de WhatsApp — quando
      presente, substitui o ícone de WhatsApp procedural só nesse campo
      (e-mail/telefone continuam com o ícone normal, se with_icons também
      estiver marcado). Só usado pela geração individual.
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

        align = cfg.get("align", "left")
        color = cfg.get("color") or "#1f2937"

        # QR Code do WhatsApp (opcional, 32x32 fixo): quando enviado, substitui
        # o ícone procedural só no campo "whatsapp" — e-mail/telefone
        # continuam com o ícone normal (ver with_icons abaixo).
        use_qr = (
            field_key == "whatsapp"
            and qrcode_path
            and os.path.isfile(qrcode_path)
            and align == "left"
        )

        # Ícone (opcional): só para e-mail/telefone/whatsapp alinhados à
        # esquerda — reserva espaço à esquerda do texto para o ícone caber
        # sem sobrepor, encolhendo a largura disponível para o texto.
        icon_drawer = None if use_qr else (_ICON_DRAWERS.get(field_key) if (with_icons and align == "left") else None)
        icon_reserved = 0
        icon_size = 0
        if use_qr:
            icon_size = WHATSAPP_QR_SIZE
            icon_reserved = icon_size + max(4, int(icon_size * 0.4))
            max_box_width = max(20, max_box_width - icon_reserved)
        elif icon_drawer:
            icon_size = max(10, int(float(cfg.get("font_size", 18)) * 0.82))
            icon_reserved = icon_size + max(4, int(icon_size * 0.4))
            max_box_width = max(20, max_box_width - icon_reserved)

        font, fitted_text = _fit_text(
            draw, text_value, bool(cfg.get("bold")), max_box_width, float(cfg.get("font_size", 18))
        )

        text_x = x
        if align in ("center", "right"):
            text_w = draw.textlength(fitted_text, font=font)
            if align == "center":
                text_x = int(x - text_w / 2)
            else:
                text_x = int(x - text_w)
        elif icon_drawer or use_qr:
            text_x = x + icon_reserved

        if use_qr:
            try:
                qr_img = Image.open(qrcode_path).convert("RGBA")
                qr_img = ImageOps.fit(qr_img, (icon_size, icon_size), Image.LANCZOS, centering=(0.5, 0.5))
                qr_y = y + int(icon_size * 0.18)  # mesma referência vertical usada pelos ícones ("vertical-align: middle" com o texto)
                base.alpha_composite(qr_img, dest=(max(0, x), max(0, qr_y)))
            except Exception:  # noqa: BLE001 — QR Code corrompido/ilegível nunca deve derrubar a geração da assinatura
                pass
        elif icon_drawer:
            icon_img = icon_drawer(icon_size, color)
            icon_y = y + int(icon_size * 0.18)  # aproxima o centro do ícone da altura-x do texto
            base.alpha_composite(icon_img, dest=(max(0, x), max(0, icon_y)))

        draw.text((max(0, text_x), max(0, y)), fitted_text, font=font, fill=color)

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
