"""Provisionamento inicial: conta de administrador e modelos padrão FIEG 2026.

Executado no start do container (entrypoint.sh). É seguro rodar múltiplas
vezes: só cria o que ainda não existe no banco.
"""
import logging
import os
import shutil

from .extensions import db
from .models import User, Role, SignatureTemplate
from .utils.template_fields import VARIANTS, validate_fields_json
from .utils.validators import generate_safe_filename

logger = logging.getLogger(__name__)


def seed_admin(app) -> None:
    username = app.config.get("ADMIN_SEED_USERNAME")
    password = app.config.get("ADMIN_SEED_PASSWORD")
    name = app.config.get("ADMIN_SEED_NAME") or "Administrador"

    existing_admin = User.query.filter_by(role=Role.ADMIN.value).first()
    if existing_admin:
        logger.info("Administrador já existe (%s). Seed ignorado.", existing_admin.username)
        return

    if not username or not password:
        logger.warning(
            "Nenhum administrador encontrado e ADMIN_SEED_USERNAME/ADMIN_SEED_PASSWORD "
            "não foram definidos. Configure-os no .env e reinicie o container."
        )
        return

    if len(password) < 8:
        logger.error("ADMIN_SEED_PASSWORD muito curta (mínimo 8 caracteres). Seed abortado.")
        return

    username = username.lower().strip()
    if User.query.filter_by(username=username).first():
        logger.warning("Usuário de seed já cadastrado para outra conta. Seed ignorado.")
        return

    admin = User(
        name=name.strip(),
        username=username,
        role=Role.ADMIN.value,
        is_active_flag=True,
        must_change_password=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    logger.info("Administrador inicial criado: %s", admin.username)


def seed_templates(app) -> None:
    """Cria automaticamente os dois modelos do padrão FIEG 2026 (sem foto e
    com foto) a partir dos fundos em modelos_prontos/fieg_2026/, caso ainda
    não exista modelo daquela variante no banco. O administrador não precisa
    configurar nada — os padrões oficiais já ficam ativos no primeiro start."""
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    src_dir = os.path.join(basedir, "modelos_prontos", "fieg_2026")
    names = {"sem_foto": "FIEG 2026 — Sem foto", "com_foto": "FIEG 2026 — Com foto"}

    from PIL import Image

    for variant in VARIANTS:
        if SignatureTemplate.query.filter_by(variant=variant).first():
            continue

        src = os.path.join(src_dir, f"fundo_{variant}.png")
        if not os.path.isfile(src):
            logger.warning("Fundo padrão não encontrado (%s); modelo '%s' não foi criado.", src, variant)
            continue

        filename = generate_safe_filename("png")
        dest = os.path.join(app.config["TEMPLATES_UPLOAD_DIR"], filename)
        shutil.copyfile(src, dest)
        with Image.open(dest) as img:
            width, height = img.width, img.height

        template = SignatureTemplate(
            name=names[variant],
            variant=variant,
            background_filename=filename,
            width=width,
            height=height,
            is_active=True,
        )
        template.set_fields(validate_fields_json("", variant))
        db.session.add(template)
        db.session.commit()
        logger.info("Modelo padrão criado e ativado: %s", names[variant])
