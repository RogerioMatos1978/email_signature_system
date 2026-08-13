import os
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, abort
from flask_login import login_required, current_user
from flask_limiter.util import get_remote_address

from ...extensions import db, limiter
from ...forms import SignatureForm
from ...models import SignatureTemplate, SignatureRecord
from ...utils.validators import validate_and_open_image, generate_safe_filename, ImageValidationError, sanitize_plain_text
from ...utils.image_utils import render_signature, SignatureRenderError
from ...utils.security import safe_send_file
from ...utils.flashing import flash_form_errors
from ...utils.files import delete_record_files

user_bp = Blueprint("user", __name__)

SESSION_PENDING_KEY = "pending_signature_id"
STALE_PENDING_MINUTES = 60


@user_bp.before_request
@login_required
def _guard():
    # Admin e Supervisor têm acesso total à geração individual (com ou sem
    # foto) além da importação em lote — só o Usuário padrão fica restrito
    # à própria assinatura (aplicado abaixo via _generation_blocked()).
    return None


def _get_active_template(variant: str):
    return SignatureTemplate.query.filter_by(is_active=True, variant=variant).first()


def _get_active_templates():
    """Modelos ativos por variante: {"sem_foto": t1|None, "com_foto": t2|None}."""
    return {
        "sem_foto": _get_active_template("sem_foto"),
        "com_foto": _get_active_template("com_foto"),
    }


def _cleanup_stale_pending(user_id: int) -> None:
    """Remove registros pendentes antigos/abandonados do usuário (ex.: quem
    fechou o navegador no meio do fluxo de confirmação), evitando acúmulo de
    arquivos órfãos em disco."""
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_PENDING_MINUTES)
    stale = SignatureRecord.query.filter(
        SignatureRecord.user_id == user_id,
        SignatureRecord.status == "pending",
        SignatureRecord.created_at < cutoff,
    ).all()
    for record in stale:
        delete_record_files(record)
        db.session.delete(record)
    if stale:
        db.session.commit()


def _get_own_pending_record():
    record_id = session.get(SESSION_PENDING_KEY)
    if not record_id:
        return None
    record = SignatureRecord.query.get(record_id)
    if not record or record.user_id != current_user.id or record.status != "pending":
        session.pop(SESSION_PENDING_KEY, None)
        return None
    return record


# ---------------------------------------------------------------------------
# Dashboard / histórico
# ---------------------------------------------------------------------------

@user_bp.route("/")
def dashboard():
    active_template = _get_active_template("sem_foto") or _get_active_template("com_foto")
    last_signature = (
        SignatureRecord.query.filter_by(user_id=current_user.id, status="success")
        .order_by(SignatureRecord.created_at.desc())
        .first()
    )
    return render_template("user/dashboard.html", active_template=active_template, last_signature=last_signature)


@user_bp.route("/historico")
def history():
    page = request.args.get("page", 1, type=int) or 1
    pagination = (
        SignatureRecord.query.filter_by(user_id=current_user.id, status="success")
        .order_by(SignatureRecord.created_at.desc())
        .paginate(page=page, per_page=15, error_out=False)
    )
    return render_template("user/history.html", pagination=pagination)


# ---------------------------------------------------------------------------
# Geração de assinatura (nova → confirmar → resultado)
# ---------------------------------------------------------------------------

def _user_rate_key() -> str:
    """Limita a geração de assinaturas POR USUÁRIO (não por IP): em Docker/rede
    local todos os clientes podem compartilhar o mesmo IP interno, e um limite
    por IP valeria para a organização inteira de uma vez."""
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()


def _generation_blocked() -> bool:
    """True se o usuário já baixou sua assinatura e ainda não foi liberado
    pelo administrador para gerar outra. Essa trava é pensada para o Usuário
    padrão gerar A PRÓPRIA assinatura uma vez só; Administrador e Supervisor
    geram assinaturas de colaboradores diversos o tempo todo (individual ou
    em lote) e nunca são bloqueados por ela."""
    if current_user.is_admin or current_user.is_supervisor:
        return False
    return not current_user.can_generate_signature


@user_bp.route("/nova", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"], key_func=_user_rate_key)
def new_signature():
    if _generation_blocked():
        flash(
            "Você já gerou e baixou sua assinatura. Para gerar uma nova, solicite a liberação ao administrador.",
            "info",
        )
        return redirect(url_for("user.dashboard"))

    templates = _get_active_templates()
    form = SignatureForm()
    has_any_template = any(templates.values())

    if not has_any_template:
        flash("Nenhum modelo de assinatura foi definido pelo administrador ainda. Tente novamente mais tarde.", "error")
        return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=False)

    if form.validate_on_submit():
        _cleanup_stale_pending(current_user.id)

        variant = "com_foto" if form.with_photo.data else "sem_foto"
        active_template = templates[variant]
        if active_template is None:
            flash(f"O modelo \"{'com foto' if variant == 'com_foto' else 'sem foto'}\" não está disponível. Contate o administrador.", "error")
            return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)

        photo_filename = None
        if variant == "com_foto":
            if not (form.photo.data and form.photo.data.filename):
                flash("Para gerar a assinatura com foto, envie a foto do colaborador.", "error")
                return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)
            try:
                photo_img = validate_and_open_image(
                    form.photo.data,
                    current_app.config["MAX_IMAGE_UPLOAD_BYTES"],
                    current_app.config["MAX_IMAGE_DIMENSION"],
                )
            except ImageValidationError as exc:
                flash(str(exc), "error")
                return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)

            from PIL import ImageOps

            photo_img = ImageOps.exif_transpose(photo_img)
            photo_filename = generate_safe_filename("png")
            photo_img.convert("RGBA").save(
                os.path.join(current_app.config["PHOTOS_UPLOAD_DIR"], photo_filename), "PNG", optimize=True
            )

        phone_value = sanitize_plain_text(form.phone.data, 40)
        # O campo separado "WhatsApp (opcional)" foi removido — a única forma
        # de ter um número de WhatsApp na assinatura agora é marcar "Este
        # telefone também é o WhatsApp", que reaproveita o número já digitado
        # no Telefone (só disponível na geração individual, nunca na
        # importação de planilha, que mantém seu próprio fluxo inalterado).
        phone_is_whatsapp = bool(form.phone_is_whatsapp.data)
        whatsapp_value = phone_value if phone_is_whatsapp else ""

        values = {
            "full_name": sanitize_plain_text(form.full_name.data, 80),
            "role_title": sanitize_plain_text(form.role_title.data, 60),
            "unit": sanitize_plain_text(form.unit.data, 60),
            "signature_email": sanitize_plain_text(form.signature_email.data, 190),
            "phone": phone_value,
            "whatsapp": whatsapp_value,
        }
        with_icons = bool(form.with_icons.data)

        # QR Code do WhatsApp (opcional, 36x36px na frente do número) — só
        # existe se houver de fato um número de WhatsApp para acompanhar.
        qrcode_filename = None
        if values["whatsapp"] and form.whatsapp_qrcode.data and form.whatsapp_qrcode.data.filename:
            try:
                qr_img = validate_and_open_image(
                    form.whatsapp_qrcode.data,
                    current_app.config["MAX_IMAGE_UPLOAD_BYTES"],
                    current_app.config["MAX_IMAGE_DIMENSION"],
                )
            except ImageValidationError as exc:
                flash(f"QR Code do WhatsApp: {exc}", "error")
                return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)

            from PIL import ImageOps as _ImageOps

            qr_img = _ImageOps.exif_transpose(qr_img)
            qrcode_filename = generate_safe_filename("png")
            qr_img.convert("RGBA").save(
                os.path.join(current_app.config["QRCODES_UPLOAD_DIR"], qrcode_filename), "PNG", optimize=True
            )

        output_format = form.output_format.data if form.output_format.data in ("png", "jpg") else "png"
        output_filename = generate_safe_filename(output_format)
        output_path = os.path.join(current_app.config["GENERATED_UPLOAD_DIR"], output_filename)
        photo_path = (
            os.path.join(current_app.config["PHOTOS_UPLOAD_DIR"], photo_filename) if photo_filename else None
        )
        qrcode_path = (
            os.path.join(current_app.config["QRCODES_UPLOAD_DIR"], qrcode_filename) if qrcode_filename else None
        )
        background_path = os.path.join(
            current_app.config["TEMPLATES_UPLOAD_DIR"], active_template.background_filename
        )

        # Evita duplicar o mesmo número na assinatura (uma vez como
        # "Telefone", outra como "WhatsApp"): quando o telefone está marcado
        # como WhatsApp, a linha de Telefone não é desenhada — o número
        # aparece só uma vez, na linha de WhatsApp (com QR Code, se enviado).
        # O registro no banco (values/record) continua com o telefone
        # completo, só a IMAGEM gerada omite a linha redundante.
        render_values = dict(values)
        if phone_is_whatsapp:
            render_values["phone"] = ""

        try:
            render_signature(
                background_path=background_path,
                fields_config=active_template.get_fields(),
                values=render_values,
                photo_path=photo_path,
                output_path=output_path,
                output_format=output_format,
                max_width=current_app.config["OUTPUT_MAX_WIDTH"],
                jpeg_quality=current_app.config["JPEG_QUALITY"],
                variant=variant,
                with_icons=with_icons,
                qrcode_path=qrcode_path,
                whatsapp_icon_enabled=False,
            )
        except SignatureRenderError as exc:
            flash(str(exc), "error")
            return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)

        record = SignatureRecord(
            user_id=current_user.id,
            template_id=active_template.id,
            full_name=values["full_name"],
            role_title=values["role_title"],
            unit=values["unit"],
            signature_email=values["signature_email"],
            phone=values["phone"],
            whatsapp=values["whatsapp"] or None,
            with_icons=with_icons,
            source="individual",
            photo_filename=photo_filename,
            qrcode_filename=qrcode_filename,
            output_filename=output_filename,
            output_format=output_format,
            status="pending",
        )
        db.session.add(record)
        db.session.commit()

        session[SESSION_PENDING_KEY] = record.id
        return redirect(url_for("user.confirm_signature"))

    if form.is_submitted():
        flash_form_errors(form)
    return render_template("user/new_signature.html", form=form, templates=templates, has_any_template=True)


@user_bp.route("/nova/confirmar", methods=["GET", "POST"])
def confirm_signature():
    record = _get_own_pending_record()
    if not record:
        flash("Nenhuma assinatura pendente de confirmação. Preencha o formulário novamente.", "info")
        return redirect(url_for("user.new_signature"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "confirmar":
            record.status = "success"
            db.session.commit()
            session.pop(SESSION_PENDING_KEY, None)
            flash("Assinatura gerada e registrada com sucesso.", "success")
            return redirect(url_for("user.result", record_id=record.id))

        # Cancelar: descarta os arquivos temporários e o registro pendente.
        delete_record_files(record)
        db.session.delete(record)
        db.session.commit()
        session.pop(SESSION_PENDING_KEY, None)
        flash("Geração cancelada. Você pode revisar e enviar novamente.", "info")
        return redirect(url_for("user.new_signature"))

    return render_template("user/confirm.html", record=record)


@user_bp.route("/resultado/<int:record_id>")
def result(record_id):
    record = SignatureRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    if record.status != "success":
        abort(404)
    return render_template("user/result.html", record=record)


# ---------------------------------------------------------------------------
# Arquivos
# ---------------------------------------------------------------------------

@user_bp.route("/visualizar/<int:record_id>")
def preview_file(record_id):
    """Serve a imagem (pendente ou final) para exibição inline nas telas de
    confirmação e resultado — nunca como anexo para download direto aqui."""
    record = SignatureRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return safe_send_file(
        current_app.config["GENERATED_UPLOAD_DIR"], record.output_filename, as_attachment=False
    )


@user_bp.route("/download/<int:record_id>")
def download_file(record_id):
    record = SignatureRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    if record.status != "success":
        abort(404)

    # Regra de negócio: quando o PRÓPRIO Usuário padrão baixa sua assinatura,
    # a geração de novas assinaturas é bloqueada para ele — somente o
    # administrador pode liberar de novo (Admin → Usuários). Administrador e
    # Supervisor nunca são bloqueados (geram para colaboradores diversos).
    # O download em si continua sempre disponível no histórico.
    if (
        not current_user.is_admin
        and not current_user.is_supervisor
        and record.user_id == current_user.id
        and current_user.can_generate_signature
    ):
        current_user.can_generate_signature = False
        db.session.commit()

    download_name = f"assinatura-{record.full_name.replace(' ', '_')}.{record.output_format}"
    return safe_send_file(
        current_app.config["GENERATED_UPLOAD_DIR"], record.output_filename, download_name=download_name
    )
