"""Configuração e validação do posicionamento dos campos dos modelos de
assinatura (padrões FIEG 2026: "sem_foto" e "com_foto").

Os valores padrão abaixo foram extraídos diretamente do XML do PowerPoint
oficial "Assinatura de e-mail 2026.pptx" (via python-pptx, lendo `shape.left`/
`shape.top` de cada caixa de texto e convertendo para percentual do slide:
x_pct = left/slide_width, y_pct = top/slide_height). Tamanhos de fonte em
pontos, valor exato do atributo "sz" do PowerPoint — mantidos com casa
decimal para bater exatamente com o original:

- Nome: fonte Neo Sans Bold, 37,8pt, azul #008BD2
- Função / E-mail / Telefone: fonte Neo Sans, 29,4pt, branco (#FFFFFF)
- Unidade/Gerência: fonte Neo Sans Bold, 29,4pt, branco
- Foto (variante com_foto): caixa x=5,11% y=25,18% w=15,63% h=51,06%

Nota sobre a extração de posição: o `<a:bodyPr>` de cada caixa de texto no
arquivo define `lIns="0"` `tIns="0"` (sem margem interna) e `anchor="t"`
(texto ancorado no topo) — ou seja, o canto superior esquerdo do TEXTO
coincide exatamente com o canto superior esquerdo da CAIXA, sem precisar
somar nenhum recuo. (Uma extração anterior havia somado por engano o recuo
padrão do PowerPoint — 0,1in/0,05in — que não se aplica aqui por estar
zerado explicitamente no arquivo; por isso os valores abaixo mudaram
ligeiramente numa revisão feita a partir do arquivo original.)

A validação NUNCA levanta erro por o JSON estar vazio — se o JavaScript do
editor não rodar no navegador, o layout padrão da variante é aplicado
integralmente no servidor.
"""
import json

TEXT_FIELD_KEYS = ("full_name", "role_title", "unit", "signature_email", "phone")
VARIANTS = ("sem_foto", "com_foto")
VARIANT_LABELS = {"sem_foto": "Sem foto", "com_foto": "Com foto"}

_AZUL_FIEG = "#008BD2"
_BRANCO = "#FFFFFF"

# --------------------------------------------------------------------------
# Padrão 2026 SEM FOTO (slide 1 do PPTX): texto começa à esquerda (x=5,14%)
# --------------------------------------------------------------------------
_SEM_FOTO_TEXT = {
    "full_name":       {"x_pct": 0.0514, "y_pct": 0.2116, "font_size": 37.8, "bold": True,  "align": "left", "color": _AZUL_FIEG, "max_chars": 40, "box_width_pct": 0.42},
    "role_title":      {"x_pct": 0.0514, "y_pct": 0.3208, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 45, "box_width_pct": 0.42},
    "unit":            {"x_pct": 0.0514, "y_pct": 0.5004, "font_size": 29.4, "bold": True,  "align": "left", "color": _BRANCO,   "max_chars": 45, "box_width_pct": 0.42},
    "signature_email": {"x_pct": 0.0514, "y_pct": 0.5815, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 50, "box_width_pct": 0.42},
    "phone":           {"x_pct": 0.0514, "y_pct": 0.6609, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 30, "box_width_pct": 0.42},
}

# --------------------------------------------------------------------------
# Padrão 2026 COM FOTO (slide 2): foto à esquerda, texto deslocado (x=22,84%)
# --------------------------------------------------------------------------
_COM_FOTO_TEXT = {
    # full_name: y=22,48% no arquivo original — a caixa do Nome nesta variante
    # é mais alta (para caber acima do resto) e começa um pouco mais abaixo
    # que na variante sem foto (21,16%), ficando com o topo bem próximo do
    # topo da foto (25,18%, ver _COM_FOTO_PHOTO). É o valor exato do slide 2
    # do PPTX, não um ajuste visual estimado.
    "full_name":       {"x_pct": 0.2284, "y_pct": 0.2248, "font_size": 37.8, "bold": True,  "align": "left", "color": _AZUL_FIEG, "max_chars": 40, "box_width_pct": 0.28},
    "role_title":      {"x_pct": 0.2284, "y_pct": 0.3208, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 45, "box_width_pct": 0.28},
    "unit":            {"x_pct": 0.2284, "y_pct": 0.5004, "font_size": 29.4, "bold": True,  "align": "left", "color": _BRANCO,   "max_chars": 45, "box_width_pct": 0.28},
    "signature_email": {"x_pct": 0.2284, "y_pct": 0.5815, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 50, "box_width_pct": 0.28},
    "phone":           {"x_pct": 0.2284, "y_pct": 0.6609, "font_size": 29.4, "bold": False, "align": "left", "color": _BRANCO,   "max_chars": 30, "box_width_pct": 0.28},
}

_COM_FOTO_PHOTO = {
    "x_pct": 0.0511, "y_pct": 0.2518, "width_pct": 0.1563, "height_pct": 0.5106,
    # Sem moldura por padrão (border_px=0) — muitos colaboradores usam logos
    # ou fotos que já têm seu próprio contorno/fundo, e a borda azul ficava
    # sobrando visualmente. Continua configurável no editor visual se algum
    # modelo específico quiser reativá-la.
    "border_color": _AZUL_FIEG, "border_px": 0,
}

DEFAULTS_BY_VARIANT = {
    "sem_foto": {"text": _SEM_FOTO_TEXT, "photo": None},
    "com_foto": {"text": _COM_FOTO_TEXT, "photo": _COM_FOTO_PHOTO},
}

_HEX_COLOR_RE = None


def _is_hex_color(value: str) -> bool:
    global _HEX_COLOR_RE
    if _HEX_COLOR_RE is None:
        import re

        _HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
    return bool(_HEX_COLOR_RE.match(value or ""))


def _clamp(value, low, high, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, v))


class TemplateFieldsError(ValueError):
    pass


def normalize_variant(variant: str) -> str:
    variant = (variant or "").strip().lower()
    return variant if variant in VARIANTS else "sem_foto"


def validate_fields_json(raw: str, variant: str = "sem_foto") -> dict:
    """Converte e sanitiza o JSON do editor visual, preenchendo qualquer campo
    ausente com o padrão da variante. Só levanta TemplateFieldsError para JSON
    genuinamente malformado."""
    variant = normalize_variant(variant)
    defaults = DEFAULTS_BY_VARIANT[variant]

    data = {}
    if raw and raw.strip():
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            raise TemplateFieldsError("Configuração de campos em formato inválido (JSON malformado).")
        if not isinstance(data, dict):
            raise TemplateFieldsError("Configuração de campos em formato inválido.")

    clean = {}
    for key in TEXT_FIELD_KEYS:
        default = defaults["text"][key]
        cfg = data.get(key) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        clean[key] = {
            "x_pct": _clamp(cfg.get("x_pct"), 0.0, 1.0, default["x_pct"]),
            "y_pct": _clamp(cfg.get("y_pct"), 0.0, 1.0, default["y_pct"]),
            # Mantém casa decimal (ex.: 37.8, 29.4) — valor exato do PowerPoint.
            "font_size": round(_clamp(cfg.get("font_size"), 8, 72, default["font_size"]), 1),
            "bold": bool(cfg.get("bold", default["bold"])),
            "align": cfg.get("align") if cfg.get("align") in ("left", "center", "right") else default["align"],
            "color": cfg.get("color") if _is_hex_color(cfg.get("color")) else default["color"],
            "max_chars": int(_clamp(cfg.get("max_chars"), 5, 120, default["max_chars"])),
            "box_width_pct": _clamp(cfg.get("box_width_pct"), 0.05, 1.0, default["box_width_pct"]),
        }

    if defaults["photo"] is not None:
        dp = defaults["photo"]
        p_cfg = data.get("photo") or {}
        if not isinstance(p_cfg, dict):
            p_cfg = {}
        clean["photo"] = {
            "x_pct": _clamp(p_cfg.get("x_pct"), 0.0, 1.0, dp["x_pct"]),
            "y_pct": _clamp(p_cfg.get("y_pct"), 0.0, 1.0, dp["y_pct"]),
            "width_pct": _clamp(p_cfg.get("width_pct"), 0.03, 0.6, dp["width_pct"]),
            "height_pct": _clamp(p_cfg.get("height_pct"), 0.03, 1.0, dp["height_pct"]),
            "border_color": p_cfg.get("border_color") if _is_hex_color(p_cfg.get("border_color")) else dp["border_color"],
            "border_px": int(_clamp(p_cfg.get("border_px"), 0, 20, dp["border_px"])),
        }

    return clean
