import enum
import json
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


class Role(str, enum.Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    USER = "user"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.USER.value, index=True)
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Token da sessão atualmente válida para este usuário (login único por
    # conta). A cada novo login, um token novo é gerado e substitui este —
    # qualquer sessão antiga (com o token anterior) é encerrada automaticamente
    # na próxima requisição, mesmo sem interação do usuário na sessão antiga.
    current_session_token = db.Column(db.String(64), nullable=True)

    # Controle de geração de assinatura: após o usuário BAIXAR a assinatura
    # gerada, este campo vira False e ele não consegue gerar outra — somente o
    # administrador pode liberar novamente (botão em Admin → Usuários).
    can_generate_signature = db.Column(db.Boolean, nullable=False, default=True)

    signatures = db.relationship(
        "SignatureRecord",
        backref="user",
        lazy="select",
        cascade="all, delete-orphan",
        foreign_keys="SignatureRecord.user_id",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not raw_password:
            return False
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    @property
    def is_supervisor(self) -> bool:
        return self.role == Role.SUPERVISOR.value

    # Flask-Login usa este atributo para bloquear login de contas desativadas.
    @property
    def is_active(self):
        return self.is_active_flag

    def __repr__(self):
        return f"<User {self.username!r} role={self.role!r}>"


class SignatureTemplate(db.Model):
    """Modelo de assinatura definido pelo administrador (imagem de fundo + layout)."""

    __tablename__ = "signature_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    # Variante do padrão 2026: "sem_foto" | "com_foto". Existe (no máximo) um
    # modelo ativo POR variante; o usuário escolhe com/sem foto ao gerar.
    variant = db.Column(db.String(20), nullable=False, default="sem_foto", index=True)
    background_filename = db.Column(db.String(255), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    fields_json = db.Column(db.Text, nullable=False, default="{}")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_fields(self) -> dict:
        try:
            data = json.loads(self.fields_json) if self.fields_json else {}
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    def set_fields(self, data: dict) -> None:
        self.fields_json = json.dumps(data or {})

    def get_merged_fields(self) -> dict:
        """Como get_fields(), mas preenche com o padrão da variante qualquer
        campo ausente do JSON salvo — útil quando um campo novo é adicionado
        ao sistema depois que este modelo já foi salvo (ex.: "whatsapp" na
        v2.0.0). Usado nas pré-visualizações em JavaScript (preview.js /
        batch_preview.js), que não fazem esse merge sozinhas; o render final
        do servidor (render_signature) já faz esse merge por conta própria."""
        from .utils.template_fields import DEFAULTS_BY_VARIANT, normalize_variant

        variant = normalize_variant(self.variant)
        defaults = DEFAULTS_BY_VARIANT[variant]
        saved = self.get_fields()
        merged = {key: {**cfg, **(saved.get(key) or {})} for key, cfg in defaults["text"].items()}
        if defaults["photo"] is not None:
            merged["photo"] = {**defaults["photo"], **(saved.get("photo") or {})}
        return merged

    def __repr__(self):
        return f"<SignatureTemplate {self.name!r} active={self.is_active}>"


class SignatureRecord(db.Model):
    """Registro de auditoria: toda assinatura gerada fica registrada aqui."""

    __tablename__ = "signature_records"

    # Nº de downloads permitidos pelo portal público para assinaturas geradas
    # via importação de planilha (colaboradores tipicamente SEM conta de
    # usuário no sistema, ao contrário da geração individual). Depois do
    # último download permitido, o registro é apagado — ver
    # main.public_download.
    PUBLIC_BATCH_DOWNLOAD_LIMIT = 4

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("signature_templates.id"), nullable=True)

    full_name = db.Column(db.String(120), nullable=False)
    role_title = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(120), nullable=False, default="")  # Unidade/Gerência (padrão 2026)
    signature_email = db.Column(db.String(190), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    whatsapp = db.Column(db.String(40), nullable=True)  # segundo telefone (WhatsApp), opcional
    with_icons = db.Column(db.Boolean, nullable=False, default=False)  # ícones antes de e-mail/telefone/whatsapp

    # "individual" (gerada uma a uma — autoatendimento do usuário padrão, ou
    # Admin/Supervisor gerando para alguém específico) | "batch" (veio de uma
    # importação de planilha — tipicamente colaboradores SEM conta de usuário
    # cadastrada no sistema). Essa distinção define a regra de download pelo
    # portal público (ver `is_publicly_available`).
    source = db.Column(db.String(20), nullable=False, default="individual", index=True)

    photo_filename = db.Column(db.String(255), nullable=True)  # foto do colaborador (variante com_foto)
    # QR Code do WhatsApp (opcional) — só disponível na geração individual
    # ("Gerar assinatura"), nunca na importação de planilha (ver
    # user/routes.py `new_signature` e admin/routes.py `_run_batch_import_job`,
    # que nunca preenche este campo). Inserido em 32x32px na frente do número
    # de WhatsApp, no lugar do ícone procedural de WhatsApp quando presente.
    qrcode_filename = db.Column(db.String(255), nullable=True)
    output_filename = db.Column(db.String(255), nullable=False)
    output_format = db.Column(db.String(4), nullable=False)  # png | jpg
    status = db.Column(db.String(20), nullable=False, default="success", index=True)

    # Portal público (sem login) de autoatendimento — regra de disponibilidade
    # depende de `source` (ver `is_publicly_available`):
    # - "individual": pode baixar só UMA vez; depois disso `public_downloaded_at`
    #   fica preenchido e, para baixar de novo, é preciso pedir ao
    #   Supervisor/Administrador (que sempre podem, via Auditoria).
    # - "batch": pode baixar até PUBLIC_BATCH_DOWNLOAD_LIMIT vezes (contador em
    #   `public_download_count`); ao atingir o limite, o registro é apagado —
    #   não tem trava de "pedir para o Supervisor", só precisa reimportar a
    #   planilha quando for necessário de novo.
    # Independente de `can_generate_signature` (que é por USUÁRIO logado);
    # isto é por REGISTRO, então não interfere em nenhum fluxo existente.
    public_downloaded_at = db.Column(db.DateTime, nullable=True)
    public_download_count = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    template = db.relationship("SignatureTemplate")

    __table_args__ = (
        db.Index("ix_signature_records_user_created", "user_id", "created_at"),
    )

    @property
    def is_publicly_available(self) -> bool:
        """True se ainda pode ser baixada pelo portal público (sem login)."""
        if self.source == "batch":
            return self.public_download_count < self.PUBLIC_BATCH_DOWNLOAD_LIMIT
        return self.public_downloaded_at is None

    @property
    def public_downloads_remaining(self):
        """Quantos downloads públicos ainda restam — só faz sentido para
        `source == "batch"` (o "individual" é tudo ou nada); None nos outros
        casos, para o template não mostrar um número sem sentido."""
        if self.source != "batch":
            return None
        return max(0, self.PUBLIC_BATCH_DOWNLOAD_LIMIT - self.public_download_count)

    def __repr__(self):
        return f"<SignatureRecord user_id={self.user_id} format={self.output_format}>"


class PublicAccessLog(db.Model):
    """Auditoria do portal público (sem login): toda busca por nome e todo
    download feito por ali fica registrado aqui, com IP de origem. Não
    interfere na tabela de auditoria normal (SignatureRecord) — é um log
    complementar, só de leitura para o administrador."""

    __tablename__ = "public_access_logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(20), nullable=False, index=True)  # "search" | "download"
    searched_name = db.Column(db.String(160), nullable=True)
    record_id = db.Column(
        db.Integer, db.ForeignKey("signature_records.id", ondelete="SET NULL"), nullable=True
    )
    matches_found = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    record = db.relationship("SignatureRecord")

    def __repr__(self):
        return f"<PublicAccessLog action={self.action!r} name={self.searched_name!r}>"


class ImportJob(db.Model):
    """Job de importação em lote rodando em segundo plano (thread), para a
    barra de progresso da tela de Importar planilha. É persistido no BANCO
    (não em um dicionário em memória) porque a aplicação roda com múltiplos
    processos Gunicorn (ver entrypoint.sh, --workers): o processo que recebe
    a requisição de progresso (polling via JavaScript) pode não ser o mesmo
    processo que criou o job e está rodando a thread — um dicionário em
    memória só existiria dentro de UM processo."""

    __tablename__ = "import_jobs"

    id = db.Column(db.String(32), primary_key=True)  # secrets.token_hex(16)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="running", index=True)  # running|done|error
    total = db.Column(db.Integer, nullable=False, default=0)
    processed = db.Column(db.Integer, nullable=False, default=0)
    generated = db.Column(db.Integer, nullable=False, default=0)
    errors_json = db.Column(db.Text, nullable=False, default="[]")
    zip_name = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_errors(self) -> list:
        try:
            data = json.loads(self.errors_json) if self.errors_json else []
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    def set_errors(self, errors) -> None:
        self.errors_json = json.dumps(list(errors or []))

    def __repr__(self):
        return f"<ImportJob {self.id} status={self.status!r} {self.processed}/{self.total}>"
