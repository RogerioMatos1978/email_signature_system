import csv
import io
import json
import os
import re
import secrets
import string
import threading
import unicodedata
import zipfile
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from PIL import ImageOps

from ...extensions import db
from ...decorators import admin_required, roles_required
from ...forms import TemplateForm, UserCreateForm, UserEditForm, BatchImportForm
from ...models import User, Role, SignatureTemplate, SignatureRecord, PublicAccessLog, ImportJob
from ...utils.validators import validate_and_open_image, generate_safe_filename, ImageValidationError, sanitize_plain_text
from ...utils.template_fields import validate_fields_json, TemplateFieldsError, DEFAULT_UNIT
from ...utils.image_utils import render_signature, SignatureRenderError
from ...utils.security import safe_send_file
from ...utils.flashing import flash_form_errors
from ...utils.files import delete_record_files

admin_bp = Blueprint("admin", __name__)

# Papéis que podem acessar a importação em lote (Supervisor + Admin) — as
# demais rotas deste blueprint (modelos, usuários, auditoria) continuam
# restritas a Admin via @admin_required em cada view, aplicado individualmente
# em vez de um guard único, já que o Supervisor só pode acessar uma fração
# deste blueprint (a importação de planilha).
_SUPERVISOR_ROLES = (Role.ADMIN.value, Role.SUPERVISOR.value)
supervisor_or_admin_required = roles_required(*_SUPERVISOR_ROLES)


@admin_bp.before_request
@login_required
def _guard():
    """Garante apenas que o usuário esteja autenticado — a permissão fina por
    papel (admin vs. supervisor) é aplicada rota a rota, com @admin_required
    ou @supervisor_or_admin_required."""
    return None


def _generate_temp_password() -> str:
    """Gera uma senha temporária forte e aleatória (letras + dígitos + símbolo)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(12))
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/")
@admin_required
def dashboard():
    users_by_role = dict(
        db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    total_signatures = db.session.query(func.count(SignatureRecord.id)).filter(
        SignatureRecord.status == "success"
    ).scalar()
    active_template = SignatureTemplate.query.filter_by(is_active=True).first()
    recent_records = (
        SignatureRecord.query.filter_by(status="success")
        .order_by(SignatureRecord.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        admins_count=users_by_role.get(Role.ADMIN.value, 0),
        supervisors_count=users_by_role.get(Role.SUPERVISOR.value, 0),
        users_count=users_by_role.get(Role.USER.value, 0),
        total_signatures=total_signatures or 0,
        active_template=active_template,
        recent_records=recent_records,
    )


# ---------------------------------------------------------------------------
# Modelos de assinatura (imagem de fundo padrão)
# ---------------------------------------------------------------------------

@admin_bp.route("/modelos")
@admin_required
def templates_list():
    templates = SignatureTemplate.query.order_by(SignatureTemplate.created_at.desc()).all()
    return render_template("admin/templates_list.html", templates=templates)


@admin_bp.route("/modelos/novo", methods=["GET", "POST"])
@admin_required
def template_new():
    form = TemplateForm()
    if form.validate_on_submit():
        if not form.background_image.data or not form.background_image.data.filename:
            flash("Envie a imagem de fundo do modelo.", "error")
            return render_template("admin/template_form.html", form=form, template=None)

        try:
            img = validate_and_open_image(
                form.background_image.data,
                current_app.config["MAX_IMAGE_UPLOAD_BYTES"],
                current_app.config["MAX_IMAGE_DIMENSION"],
            )
            fields = validate_fields_json(form.fields_json.data, form.variant.data)
        except (ImageValidationError, TemplateFieldsError) as exc:
            flash(str(exc), "error")
            return render_template("admin/template_form.html", form=form, template=None)

        img = ImageOps.exif_transpose(img)  # corrige rotação e remove dependência de EXIF
        filename = generate_safe_filename("png")
        dest_path = os.path.join(current_app.config["TEMPLATES_UPLOAD_DIR"], filename)
        img.convert("RGBA").save(dest_path, "PNG", optimize=True)

        variant = form.variant.data if form.variant.data in ("sem_foto", "com_foto") else "sem_foto"
        # Apenas um modelo ativo POR VARIANTE — o novo desativa o anterior da mesma variante.
        SignatureTemplate.query.filter_by(is_active=True, variant=variant).update({"is_active": False})

        template = SignatureTemplate(
            name=form.name.data.strip(),
            variant=variant,
            background_filename=filename,
            width=img.width,
            height=img.height,
            is_active=True,
            created_by_id=current_user.id,
        )
        template.set_fields(fields)
        db.session.add(template)
        db.session.commit()

        flash("Modelo criado e ativado com sucesso.", "success")
        return redirect(url_for("admin.templates_list"))

    if form.is_submitted():
        flash_form_errors(form)
    return render_template("admin/template_form.html", form=form, template=None)


@admin_bp.route("/modelos/<int:template_id>/editar", methods=["GET", "POST"])
@admin_required
def template_edit(template_id):
    template = SignatureTemplate.query.get_or_404(template_id)
    form = TemplateForm(obj=None)

    if request.method == "GET":
        form.name.data = template.name
        form.variant.data = template.variant
        form.fields_json.data = json.dumps(template.get_fields())

    if form.validate_on_submit():
        try:
            fields = validate_fields_json(form.fields_json.data, form.variant.data)
        except TemplateFieldsError as exc:
            flash(str(exc), "error")
            return render_template("admin/template_form.html", form=form, template=template)

        old_filename = None
        if form.background_image.data and form.background_image.data.filename:
            try:
                img = validate_and_open_image(
                    form.background_image.data,
                    current_app.config["MAX_IMAGE_UPLOAD_BYTES"],
                    current_app.config["MAX_IMAGE_DIMENSION"],
                )
            except ImageValidationError as exc:
                flash(str(exc), "error")
                return render_template("admin/template_form.html", form=form, template=template)

            img = ImageOps.exif_transpose(img)
            filename = generate_safe_filename("png")
            dest_path = os.path.join(current_app.config["TEMPLATES_UPLOAD_DIR"], filename)
            img.convert("RGBA").save(dest_path, "PNG", optimize=True)

            old_filename = template.background_filename
            template.background_filename = filename
            template.width = img.width
            template.height = img.height

        new_variant = form.variant.data if form.variant.data in ("sem_foto", "com_foto") else template.variant
        if new_variant != template.variant and template.is_active:
            # Mudou de variante: garante no máximo um ativo por variante.
            SignatureTemplate.query.filter_by(is_active=True, variant=new_variant).update({"is_active": False})
        template.variant = new_variant
        template.name = form.name.data.strip()
        template.set_fields(fields)
        db.session.commit()

        if old_filename:
            old_path = os.path.join(current_app.config["TEMPLATES_UPLOAD_DIR"], old_filename)
            try:
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except OSError:
                current_app.logger.warning("Não foi possível remover imagem antiga do modelo %s", template.id)

        flash("Modelo atualizado com sucesso.", "success")
        return redirect(url_for("admin.templates_list"))

    if form.is_submitted():
        flash_form_errors(form)
    return render_template("admin/template_form.html", form=form, template=template)


@admin_bp.route("/modelos/<int:template_id>/restaurar-padrao", methods=["POST"])
@admin_required
def template_restore_default(template_id):
    """Reaplica o layout padrão da organização (SESI/SENAI) ao modelo salvo.

    100% server-side: não depende do JavaScript do editor visual rodar no
    navegador do administrador. Útil quando o modelo foi salvo com valores
    antigos (ex.: fonte do telefone) e as edições pelo editor não persistem.
    """
    template = SignatureTemplate.query.get_or_404(template_id)
    template.set_fields(validate_fields_json("", template.variant))  # vazio => padrão completo da variante
    db.session.commit()
    flash(f'Layout do modelo "{template.name}" restaurado para o padrão da organização.', "success")
    return redirect(url_for("admin.templates_list"))


@admin_bp.route("/modelos/<int:template_id>/ativar", methods=["POST"])
@admin_required
def template_activate(template_id):
    template = SignatureTemplate.query.get_or_404(template_id)
    SignatureTemplate.query.filter_by(is_active=True, variant=template.variant).update({"is_active": False})
    template.is_active = True
    db.session.commit()
    flash(f'Modelo "{template.name}" ativado.', "success")
    return redirect(url_for("admin.templates_list"))


@admin_bp.route("/modelos/<int:template_id>/excluir", methods=["POST"])
@admin_required
def template_delete(template_id):
    template = SignatureTemplate.query.get_or_404(template_id)

    # Preserva o histórico de auditoria: desvincula em vez de apagar registros.
    SignatureRecord.query.filter_by(template_id=template.id).update({"template_id": None})

    path = os.path.join(current_app.config["TEMPLATES_UPLOAD_DIR"], template.background_filename)
    db.session.delete(template)
    db.session.commit()

    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        current_app.logger.warning("Não foi possível remover arquivo de imagem do modelo excluído.")

    flash("Modelo excluído.", "info")
    return redirect(url_for("admin.templates_list"))


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

@admin_bp.route("/usuarios")
@admin_required
def users_list():
    page = request.args.get("page", 1, type=int) or 1
    pagination = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/users_list.html", pagination=pagination)


@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def user_new():
    form = UserCreateForm()
    temp_password = None

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        if User.query.filter_by(username=username).first():
            flash("Já existe um usuário cadastrado com este nome de usuário.", "error")
            return render_template("admin/user_form.html", form=form, user=None, temp_password=None)

        temp_password = _generate_temp_password()
        user = User(
            name=form.name.data.strip(),
            username=username,
            role=form.role.data,
            is_active_flag=True,
            must_change_password=True,
        )
        user.set_password(temp_password)
        db.session.add(user)
        db.session.commit()

        flash("Usuário criado com sucesso. Copie a senha temporária abaixo — ela não será exibida novamente.", "success")
        return render_template("admin/user_form.html", form=UserCreateForm(formdata=None), user=user, temp_password=temp_password)

    if form.is_submitted():
        flash_form_errors(form)
    return render_template("admin/user_form.html", form=form, user=None, temp_password=None)


@admin_bp.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm()

    if request.method == "GET":
        form.name.data = user.name
        form.role.data = user.role
        form.is_active.data = "1" if user.is_active_flag else "0"

    if form.validate_on_submit():
        is_last_admin = (
            user.is_admin
            and db.session.query(func.count(User.id)).filter(User.role == Role.ADMIN.value).scalar() <= 1
        )
        demoting = form.role.data != Role.ADMIN.value
        deactivating = form.is_active.data == "0"

        if is_last_admin and (demoting or deactivating):
            flash("Não é possível remover o último administrador do sistema.", "error")
            return render_template("admin/user_form.html", form=form, user=user, temp_password=None)

        user.name = form.name.data.strip()
        user.role = form.role.data
        user.is_active_flag = form.is_active.data == "1"
        if not user.is_active_flag:
            # Encerra imediatamente qualquer sessão já aberta desta conta.
            user.current_session_token = None
        db.session.commit()

        flash("Usuário atualizado com sucesso.", "success")
        return redirect(url_for("admin.users_list"))

    if form.is_submitted():
        flash_form_errors(form)
    return render_template("admin/user_form.html", form=form, user=user, temp_password=None)


@admin_bp.route("/usuarios/<int:user_id>/resetar-senha", methods=["POST"])
@admin_required
def user_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    temp_password = _generate_temp_password()
    user.set_password(temp_password)
    user.must_change_password = True
    # Encerra qualquer sessão já aberta com a senha antiga.
    user.current_session_token = None
    db.session.commit()
    flash(f"Senha de {user.name} redefinida. Nova senha temporária: {temp_password}", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/usuarios/liberar-assinaturas")
@supervisor_or_admin_required
def blocked_users():
    """Tela enxuta (Admin ou Supervisor) para liberar usuários padrão que já
    geraram e baixaram a própria assinatura — sem dar ao Supervisor acesso ao
    cadastro completo de usuários (criar/editar/excluir/resetar senha
    continuam exclusivos do Admin, em Admin → Usuários)."""
    blocked = (
        User.query.filter_by(role=Role.USER.value, can_generate_signature=False, is_active_flag=True)
        .order_by(User.name.asc())
        .all()
    )
    return render_template("admin/blocked_users.html", blocked=blocked)


@admin_bp.route("/usuarios/<int:user_id>/liberar-assinatura", methods=["POST"])
@supervisor_or_admin_required
def user_allow_signature(user_id):
    """Libera o usuário para gerar uma nova assinatura (após ele já ter
    baixado a anterior, o que bloqueia automaticamente novas gerações).
    Acessível também ao Supervisor — não só ao Administrador."""
    user = User.query.get_or_404(user_id)
    if user.can_generate_signature:
        flash(f"{user.name} já está liberado para gerar assinatura.", "info")
    else:
        user.can_generate_signature = True
        db.session.commit()
        flash(f"{user.name} liberado para gerar uma nova assinatura.", "success")

    if current_user.is_admin:
        return redirect(url_for("admin.users_list", page=request.args.get("page", 1)))
    return redirect(url_for("admin.blocked_users"))


@admin_bp.route("/usuarios/<int:user_id>/excluir", methods=["POST"])
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Você não pode excluir a própria conta.", "error")
        return redirect(url_for("admin.users_list"))

    if user.is_admin and db.session.query(func.count(User.id)).filter(User.role == Role.ADMIN.value).scalar() <= 1:
        flash("Não é possível excluir o último administrador do sistema.", "error")
        return redirect(url_for("admin.users_list"))

    # Remove também os arquivos em disco das assinaturas deste usuário — sem
    # isto, as linhas de auditoria são apagadas em cascata mas os PNG/JPG/QR
    # ficariam órfãos no volume para sempre (vazamento de disco e de dados).
    for record in user.signatures:
        delete_record_files(record)

    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído.", "info")
    return redirect(url_for("admin.users_list"))


# ---------------------------------------------------------------------------
# Importação em lote (planilha) — assinaturas SEM FOTO
# ---------------------------------------------------------------------------

# Cabeçalhos aceitos (comparação sem acentos/maiúsculas): coluna → campo interno
# Observação: "unidade"/"gerencia" continuam reconhecidas por compatibilidade
# com planilhas antigas, mas a partir da v2.0.0 o valor da coluna é IGNORADO —
# a Unidade / Gerência é sempre fixada em DEFAULT_UNIT (ver loop de geração).
_SPREADSHEET_COLUMNS = {
    "nome": "full_name",
    "nome completo": "full_name",
    "funcao": "role_title",
    "cargo": "role_title",
    "unidade": "unit",
    "gerencia": "unit",
    "gerencia ou unidade": "unit",
    "unidade ou gerencia": "unit",
    "email": "signature_email",
    "e-mail": "signature_email",
    "telefone": "phone",
    "fone": "phone",
    "celular": "phone",
    "whatsapp": "whatsapp",
    "zap": "whatsapp",
    "celular whatsapp": "whatsapp",
    "segundo telefone": "whatsapp",
}
# "unit" não é mais obrigatório na planilha (é sempre substituído por
# DEFAULT_UNIT); "whatsapp" sempre foi opcional.
_REQUIRED_FIELDS = ("full_name", "role_title", "signature_email", "phone")
_FIELD_LABELS = {
    "full_name": "Nome", "role_title": "Função", "unit": "Unidade",
    "signature_email": "E-mail", "phone": "Telefone", "whatsapp": "WhatsApp",
}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[0-9()+\-\s]{8,20}$")


def _normalize_header(value) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Ordem importa: "whatsapp"/"zap" é verificado ANTES de "telefone"/"celular",
# porque cabeçalhos como "Telefone WhatsApp" ou "Celular WhatsApp" contêm as
# duas palavras — sem essa ordem, cairiam em "phone" em vez de "whatsapp".
_HEADER_CONTAINS_RULES = (
    ("whatsapp", "whatsapp"),
    ("zap", "whatsapp"),
    ("e-mail", "signature_email"),
    ("email", "signature_email"),
    ("telefone", "phone"),
    ("fone", "phone"),
    ("celular", "phone"),
    ("funcao", "role_title"),
    ("cargo", "role_title"),
    ("nome", "full_name"),
    ("unidade", "unit"),
    ("gerencia", "unit"),
)


def _match_field(normalized_header: str):
    """Casa um cabeçalho de coluna já normalizado (sem acento/maiúsculas) a
    um campo interno. Primeiro tenta a lista de nomes exatos conhecidos
    (_SPREADSHEET_COLUMNS); se não achar, tenta por "contém" (ex.: "Nº
    WhatsApp", "WhatsApp Comercial", "Telefone WhatsApp" — variações de
    cabeçalho que a lista exata não previa)."""
    field = _SPREADSHEET_COLUMNS.get(normalized_header)
    if field:
        return field
    for needle, mapped_field in _HEADER_CONTAINS_RULES:
        if needle in normalized_header:
            return mapped_field
    return None


def _slugify_filename(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text or "colaborador"


def _read_spreadsheet_rows(file_storage):
    """Lê .xlsx (openpyxl) ou .csv e devolve (headers, linhas). Levanta
    ValueError com mensagem amigável para qualquer problema de formato."""
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError("A planilha enviada está vazia.")

    if filename.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
            wb.close()
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Não foi possível ler o arquivo .xlsx. Verifique se é uma planilha válida.") from exc
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        delimiter = ";" if text.count(";") >= text.count(",") else ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))

    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("A planilha precisa ter um cabeçalho e ao menos uma linha de dados.")
    return rows[0], rows[1:]


def _map_columns(header_row):
    """Mapeia índice de coluna → campo interno a partir do cabeçalho."""
    mapping = {}
    for idx, cell in enumerate(header_row):
        field = _match_field(_normalize_header(cell))
        if field and field not in mapping.values():
            mapping[idx] = field
    missing = [f for f in _REQUIRED_FIELDS if f not in mapping.values()]
    if missing:
        raise ValueError(
            "Colunas obrigatórias não encontradas na planilha: "
            + ", ".join(_FIELD_LABELS[f] for f in missing)
            + ". Use o cabeçalho: Nome; Função; E-mail; Telefone "
            + "(Unidade é preenchida automaticamente; WhatsApp é opcional)."
        )
    return mapping


def _save_positions_if_changed(template, fields_config) -> bool:
    """Persiste `fields_config` como o novo padrão do modelo, se diferente do
    que já está salvo. Usado tanto pelo fluxo de importação quanto pelo botão
    "salvar só o posicionamento" — o reposicionamento feito por Admin ou
    Supervisor na pré-visualização passa a ser o layout padrão de TODAS as
    assinaturas dessa variante (lote e individuais), não só do lote atual.
    Retorna True se algo foi de fato alterado (evita commits/timestamps
    desnecessários quando o usuário só reabriu a tela sem mexer em nada)."""
    if fields_config == template.get_fields():
        return False
    template.set_fields(fields_config)
    db.session.commit()
    return True


@admin_bp.route("/importar/salvar-posicionamento", methods=["POST"])
@supervisor_or_admin_required
def batch_import_save_positions():
    """Salva o posicionamento ajustado na pré-visualização como o padrão do
    modelo ativo (variante sem_foto) — sem exigir upload de planilha. Passa a
    valer também para a geração individual de assinatura dos usuários padrão."""
    template = SignatureTemplate.query.filter_by(is_active=True, variant="sem_foto").first()
    if not template:
        flash("Nenhum modelo ativo da variante SEM FOTO. Ative um em Admin → Modelos antes de salvar o posicionamento.", "error")
        return redirect(url_for("admin.batch_import"))

    raw = request.form.get("fields_json", "")
    try:
        fields_config = validate_fields_json(raw, "sem_foto")
    except TemplateFieldsError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.batch_import"))

    if _save_positions_if_changed(template, fields_config):
        flash(
            f'Posicionamento salvo como padrão do modelo "{template.name}" — vale para todas as assinaturas, '
            "geradas em lote ou individualmente pelos usuários padrão.",
            "success",
        )
    else:
        flash("Nenhuma alteração de posição para salvar.", "info")
    return redirect(url_for("admin.batch_import"))


def _cleanup_stale_import_jobs() -> None:
    """Remove jobs de importação com mais de 24h (concluídos ou não) — só
    guardam contadores e mensagens de erro, sem valor depois que a tela de
    progresso já foi vista, então não há razão para acumular para sempre."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    ImportJob.query.filter(ImportJob.created_at < cutoff).delete(synchronize_session=False)
    db.session.commit()


def _run_batch_import_job(app, job_id, user_id, data_rows, mapping, output_format, with_icons, fields_config, background_path, template_id):
    """Gera as assinaturas do lote em segundo plano (chamado numa thread à
    parte, fora do ciclo de requisição HTTP) — atualiza o ImportJob no banco
    a cada linha processada, para a barra de progresso (tela de importação)
    poder consultar via polling em /admin/importar/progresso/<job_id>."""
    with app.app_context():
        job = ImportJob.query.get(job_id)
        if not job:
            return
        try:
            zip_buffer = io.BytesIO()
            generated = 0
            errors = []
            used_names = set()
            total = len(data_rows)

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, (line_no, row) in enumerate(enumerate(data_rows, start=2), start=1):  # linha 1 = cabeçalho
                    values = {field: sanitize_plain_text(str(row[idx] if idx < len(row) and row[idx] is not None else ""), 190)
                              for idx, field in mapping.items()}
                    # Unidade / Gerência sempre fixa (v2.0.0) — o que estiver
                    # na planilha (se houver essa coluna) é descartado.
                    values["unit"] = DEFAULT_UNIT
                    values.setdefault("whatsapp", "")
                    # O número de WhatsApp da planilha só é usado quando
                    # "Incluir ícones" está marcado (aplica ao lote inteiro).
                    if not with_icons:
                        values["whatsapp"] = ""

                    row_errors = [
                        _FIELD_LABELS[f] for f in _REQUIRED_FIELDS if not (values.get(f) or "").strip()
                    ]
                    if row_errors:
                        errors.append(f"Linha {line_no}: campo(s) vazio(s): {', '.join(row_errors)}.")
                    elif not _EMAIL_RE.match(values["signature_email"]):
                        errors.append(f"Linha {line_no}: e-mail inválido ({values['signature_email']}).")
                    elif not _PHONE_RE.match(values["phone"]):
                        errors.append(f"Linha {line_no}: telefone inválido ({values['phone']}).")
                    elif values["whatsapp"].strip() and not _PHONE_RE.match(values["whatsapp"]):
                        errors.append(f"Linha {line_no}: WhatsApp inválido ({values['whatsapp']}).")
                    else:
                        output_filename = generate_safe_filename(output_format)
                        output_path = os.path.join(app.config["GENERATED_UPLOAD_DIR"], output_filename)
                        try:
                            render_signature(
                                background_path=background_path,
                                fields_config=fields_config,
                                values=values,
                                photo_path=None,
                                output_path=output_path,
                                output_format=output_format,
                                max_width=app.config["OUTPUT_MAX_WIDTH"],
                                jpeg_quality=app.config["JPEG_QUALITY"],
                                variant="sem_foto",
                                with_icons=with_icons,
                            )
                        except SignatureRenderError as exc:
                            errors.append(f"Linha {line_no}: {exc}")
                        else:
                            record = SignatureRecord(
                                user_id=user_id,
                                template_id=template_id,
                                full_name=values["full_name"][:120],
                                role_title=values["role_title"][:120],
                                unit=values["unit"][:120],
                                signature_email=values["signature_email"][:190],
                                phone=values["phone"][:40],
                                whatsapp=(values["whatsapp"][:40] or None),
                                with_icons=with_icons,
                                output_filename=output_filename,
                                output_format=output_format,
                                status="success",
                            )
                            db.session.add(record)

                            arc = f"assinatura-{_slugify_filename(values['full_name'])}"
                            n, base_arc = 2, arc
                            while arc in used_names:
                                arc = f"{base_arc}-{n}"
                                n += 1
                            used_names.add(arc)
                            zf.write(output_path, f"{arc}.{output_format}")
                            generated += 1

                    # Grava o progresso a cada 5 linhas (e sempre na última) —
                    # atualizar a cada linha geraria escritas demais no
                    # SQLite; a cada 5 já dá uma barra fluida o suficiente.
                    job.processed = i
                    job.generated = generated
                    job.set_errors(errors)
                    if i % 5 == 0 or i == total:
                        db.session.commit()

            if generated == 0:
                job.status = "error"
                job.error_message = "Nenhuma assinatura foi gerada. Corrija os erros da planilha e tente novamente."
                db.session.commit()
                return

            zip_name = f"{secrets.token_hex(16)}.zip"
            zip_path = os.path.join(app.config["GENERATED_UPLOAD_DIR"], zip_name)
            with open(zip_path, "wb") as fh:
                fh.write(zip_buffer.getvalue())

            job.status = "done"
            job.zip_name = zip_name
            job.generated = generated
            job.processed = total
            job.set_errors(errors)
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 — job em segundo plano: qualquer falha precisa virar status "error", nunca travar em silêncio
            db.session.rollback()
            app.logger.exception("Falha no job de importação em lote %s", job_id)
            job = ImportJob.query.get(job_id)
            if job:
                job.status = "error"
                job.error_message = f"Falha inesperada ao gerar o lote: {exc}"
                db.session.commit()


@admin_bp.route("/importar", methods=["GET", "POST"])
@supervisor_or_admin_required
def batch_import():
    form = BatchImportForm()
    errors = []
    # "fetch" = a página tem JavaScript e vai mostrar a barra de progresso via
    # polling; sem esse cabeçalho (JS desabilitado ou formulário enviado do
    # jeito clássico), o comportamento cai para o mesmo fluxo síncrono de
    # sempre — a requisição só termina quando o lote inteiro estiver pronto.
    wants_json = request.headers.get("X-Requested-With") == "fetch"

    _cleanup_stale_import_jobs()

    # Modelo SEM FOTO ativo — usado tanto para a pré-visualização/reposicionamento
    # (GET) quanto para a geração em lote (POST). Sem ele, nem a prévia nem a
    # importação funcionam.
    template = SignatureTemplate.query.filter_by(is_active=True, variant="sem_foto").first()

    def _render(**extra):
        extra.setdefault("errors", errors)
        extra.setdefault("zip_name", None)
        extra.setdefault("generated", 0)
        return render_template(
            "admin/batch_import.html", form=form, template=template, unit_label=DEFAULT_UNIT, **extra
        )

    def _fail(message):
        if wants_json:
            return jsonify(error=message), 400
        flash(message, "error")
        return _render()

    if not template:
        return _fail("Nenhum modelo ativo da variante SEM FOTO. Ative um em Admin → Modelos antes de importar.")

    if form.validate_on_submit():
        try:
            header, data_rows = _read_spreadsheet_rows(form.spreadsheet.data)
            mapping = _map_columns(header)
        except ValueError as exc:
            return _fail(str(exc))

        if len(data_rows) > 500:
            return _fail("A planilha tem mais de 500 linhas. Divida em arquivos menores.")

        output_format = form.output_format.data if form.output_format.data in ("png", "jpg") else "png"
        with_icons = bool(form.with_icons.data)
        background_path = os.path.join(
            current_app.config["TEMPLATES_UPLOAD_DIR"], template.background_filename
        )

        # Posições customizadas na pré-visualização (se o admin/supervisor
        # arrastou algum campo) têm prioridade; senão usa a posição salva no
        # modelo. A partir da v1.6.0 esse posicionamento também é salvo como
        # o padrão do modelo ativo (variante sem_foto) — passa a valer para
        # TODAS as assinaturas, inclusive as geradas individualmente pelos
        # usuários padrão, que leem a mesma SignatureTemplate.get_fields().
        if form.fields_json.data and form.fields_json.data.strip():
            try:
                fields_config = validate_fields_json(form.fields_json.data, "sem_foto")
            except TemplateFieldsError as exc:
                return _fail(str(exc))
            _save_positions_if_changed(template, fields_config)
        else:
            fields_config = template.get_fields()

        job = ImportJob(id=secrets.token_hex(16), user_id=current_user.id, status="running", total=len(data_rows))
        db.session.add(job)
        db.session.commit()

        app_obj = current_app._get_current_object()
        thread = threading.Thread(
            target=_run_batch_import_job,
            args=(app_obj, job.id, current_user.id, data_rows, mapping, output_format, with_icons, fields_config, background_path, template.id),
            daemon=True,
        )
        thread.start()

        if wants_json:
            return jsonify(job_id=job.id, total=job.total)

        # Sem JavaScript: espera o job terminar (do jeito de sempre, a
        # requisição só volta quando o lote inteiro estiver pronto) e mostra
        # o resultado direto — ninguém fica sem resposta por falta de JS.
        thread.join()
        db.session.refresh(job)
        if job.status == "error":
            flash(job.error_message or "Falha ao gerar o lote.", "error")
            return _render(errors=job.get_errors())
        if job.get_errors():
            flash(f"{job.generated} assinatura(s) gerada(s); {len(job.get_errors())} linha(s) com erro foram ignoradas (veja a lista abaixo).", "info")
        else:
            flash(f"{job.generated} assinatura(s) gerada(s) com sucesso.", "success")
        return render_template(
            "admin/batch_import.html", form=BatchImportForm(formdata=None), errors=job.get_errors(),
            zip_name=job.zip_name, generated=job.generated, template=template, unit_label=DEFAULT_UNIT,
        )

    if form.is_submitted():
        if wants_json:
            return jsonify(error="Formulário inválido. Confira os campos e tente novamente."), 400
        flash_form_errors(form)
    return _render()


@admin_bp.route("/importar/progresso/<job_id>")
@supervisor_or_admin_required
def batch_import_progress(job_id):
    """Consultado via JavaScript (polling) pela barra de progresso — só o
    dono do job pode consultar (nada sensível além de contadores, mas não há
    razão para um Supervisor ver o progresso do lote de outro)."""
    job = ImportJob.query.get(job_id)
    if not job or job.user_id != current_user.id:
        abort(404)
    return jsonify(
        status=job.status,
        total=job.total,
        processed=job.processed,
        generated=job.generated,
        zip_name=job.zip_name,
        errors=job.get_errors(),
        error_message=job.error_message,
    )


@admin_bp.route("/importar/resultado/<job_id>")
@supervisor_or_admin_required
def batch_import_result(job_id):
    """Página de resultado para quem importou via JavaScript (a barra de
    progresso redireciona para cá assim que o job termina) — mesmo template
    usado no fluxo síncrono (sem JS), só que lendo os dados do job salvo."""
    job = ImportJob.query.get(job_id)
    if not job or job.user_id != current_user.id:
        abort(404)

    template = SignatureTemplate.query.filter_by(is_active=True, variant="sem_foto").first()

    if job.status == "running":
        flash("A importação ainda está em andamento. Aguarde a barra de progresso terminar.", "info")
        return redirect(url_for("admin.batch_import"))
    if job.status == "error":
        flash(job.error_message or "Falha ao gerar o lote.", "error")
        return redirect(url_for("admin.batch_import"))

    if job.get_errors():
        flash(f"{job.generated} assinatura(s) gerada(s); {len(job.get_errors())} linha(s) com erro foram ignoradas (veja a lista abaixo).", "info")
    else:
        flash(f"{job.generated} assinatura(s) gerada(s) com sucesso.", "success")
    return render_template(
        "admin/batch_import.html", form=BatchImportForm(formdata=None), errors=job.get_errors(),
        zip_name=job.zip_name, generated=job.generated, template=template, unit_label=DEFAULT_UNIT,
    )


@admin_bp.route("/importar/download/<zip_name>")
@supervisor_or_admin_required
def batch_import_download(zip_name):
    if not re.fullmatch(r"[0-9a-f]{32}\.zip", zip_name or ""):
        abort(404)
    return safe_send_file(
        current_app.config["GENERATED_UPLOAD_DIR"], zip_name, download_name="assinaturas.zip"
    )


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------

@admin_bp.route("/auditoria")
@admin_required
def audit_list():
    page = request.args.get("page", 1, type=int) or 1
    user_id = request.args.get("user_id", type=int)

    query = SignatureRecord.query.join(User, SignatureRecord.user_id == User.id).filter(
        SignatureRecord.status == "success"
    )
    if user_id:
        query = query.filter(SignatureRecord.user_id == user_id)

    pagination = query.order_by(SignatureRecord.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    all_users = User.query.order_by(User.name.asc()).all()

    return render_template(
        "admin/audit.html", pagination=pagination, all_users=all_users, selected_user_id=user_id
    )


@admin_bp.route("/auditoria/<int:record_id>/download")
@admin_required
def audit_download(record_id):
    record = SignatureRecord.query.get_or_404(record_id)
    download_name = f"assinatura-{record.full_name.replace(' ', '_')}.{record.output_format}"
    return safe_send_file(
        current_app.config["GENERATED_UPLOAD_DIR"], record.output_filename, download_name=download_name
    )


@admin_bp.route("/auditoria/portal-publico")
@admin_required
def public_access_log():
    """Log de uso do portal público (sem login): toda busca por nome e todo
    download feito por lá, com IP de origem — complementar à auditoria normal."""
    page = request.args.get("page", 1, type=int) or 1
    pagination = (
        PublicAccessLog.query.order_by(PublicAccessLog.created_at.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )
    return render_template("admin/public_access_log.html", pagination=pagination)
