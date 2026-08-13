import os
from datetime import timedelta


class Config:
    """Configuração base. Todos os valores sensíveis vêm de variáveis de ambiente
    — nada de segredos hardcoded no código-fonte (item de segurança)."""

    SECRET_KEY = os.environ.get("SECRET_KEY")

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    INSTANCE_DIR = os.environ.get("INSTANCE_DIR", os.path.join(basedir, "instance"))

    _default_db = f"sqlite:///{os.path.join(INSTANCE_DIR, 'app.db')}"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _default_db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
    TEMPLATES_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "templates")
    PHOTOS_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "photos")
    GENERATED_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "generated")

    # Limite rígido de tamanho de requisição (defesa contra upload abusivo/DoS)
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 6 MB por requisição

    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB por arquivo de imagem
    MAX_IMAGE_DIMENSION = 4000  # px — proteção contra "decompression bomb"

    # Sessão / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_TIME_LIMIT = None  # token válido durante toda a sessão (evita expirar em formulários longos)

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Só ativa quando o sistema estiver atrás de um proxy reverso confiável
    # (ex.: Caddy/nginx fazendo o HTTPS, ver GUIA_DEPLOY.md) — nesse caso o
    # Flask passa a confiar nos cabeçalhos X-Forwarded-For/Proto/Host que o
    # proxy define, e enxerga o IP e o "https" reais do visitante (sem isso,
    # o rate limiting por IP e a auditoria do portal público veriam sempre o
    # IP do proxy, não o do visitante). NUNCA ativar se a aplicação estiver
    # diretamente exposta à internet sem um proxy na frente — qualquer
    # visitante poderia forjar esses cabeçalhos e enganar o rate limiting.
    TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"

    # Seed do administrador inicial (usado apenas se não existir nenhum admin)
    ADMIN_SEED_NAME = os.environ.get("ADMIN_SEED_NAME", "Administrador")
    ADMIN_SEED_USERNAME = os.environ.get("ADMIN_SEED_USERNAME")
    ADMIN_SEED_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD")

    # Geração de imagem final
    OUTPUT_MAX_WIDTH = int(os.environ.get("OUTPUT_MAX_WIDTH", 1300))
    JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", 88))

    APP_VERSION = "2.5.1"


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("APP_ENV", "production").lower()
    return config_map.get(env, ProductionConfig)
