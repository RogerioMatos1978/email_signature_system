from datetime import datetime

from flask import Blueprint, redirect, url_for, render_template, current_app, abort, request, flash
from flask_login import login_required, current_user
from flask_limiter.util import get_remote_address

from ...extensions import db, limiter
from ...models import SignatureTemplate, SignatureRecord, PublicAccessLog
from ...utils.security import safe_send_file
from ...utils.validators import normalize_search_text
from ...utils.files import delete_record_files

main_bp = Blueprint("main", __name__)

# Busca pública (sem login): exige pelo menos 3 caracteres para evitar
# resultados enormes/genéricos e reduzir varredura casual de nomes.
PUBLIC_SEARCH_MIN_CHARS = 3
PUBLIC_SEARCH_MAX_RESULTS = 15
PUBLIC_SEARCH_SCAN_LIMIT = 3000  # teto de registros carregados por busca


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.is_supervisor:
        return redirect(url_for("admin.batch_import"))
    return redirect(url_for("user.dashboard"))


def _search_public_signatures(query_name: str):
    """Busca (sem login) por assinaturas já geradas com nome parecido, tolerante
    a acento/caixa. Carrega um teto de registros recentes e filtra em Python —
    suficiente para a escala de uma organização (centenas/poucos milhares de
    colaboradores); evita depender de extensão de "unaccent" no SQLite."""
    norm_query = normalize_search_text(query_name)
    if len(norm_query) < PUBLIC_SEARCH_MIN_CHARS:
        return []
    candidates = (
        SignatureRecord.query.filter(SignatureRecord.status == "success")
        .order_by(SignatureRecord.created_at.desc())
        .limit(PUBLIC_SEARCH_SCAN_LIMIT)
        .all()
    )
    matches = [r for r in candidates if norm_query in normalize_search_text(r.full_name)]
    return matches[:PUBLIC_SEARCH_MAX_RESULTS]


@main_bp.route("/ajuda/outlook")
@limiter.limit("30 per minute", key_func=get_remote_address)
def outlook_help():
    """Página pública (sem login): instruções de uso no Outlook + busca de
    autoatendimento — o colaborador procura pelo próprio nome e baixa a
    assinatura já gerada para ele (em lote ou individualmente), sem precisar
    de conta no sistema. Continua acessível também para usuários logados
    (link no menu), sem nenhuma mudança de comportamento para eles."""
    query_name = (request.args.get("nome") or "").strip()[:120]
    searched = bool(query_name)
    matches = []

    if searched:
        matches = _search_public_signatures(query_name)
        db.session.add(PublicAccessLog(
            action="search",
            searched_name=query_name,
            matches_found=len(matches),
            ip_address=get_remote_address(),
        ))
        db.session.commit()

    return render_template(
        "main/help_outlook.html",
        query_name=query_name,
        matches=matches,
        searched=searched,
        min_chars=PUBLIC_SEARCH_MIN_CHARS,
    )


@main_bp.route("/ajuda/outlook/baixar/<int:record_id>", methods=["POST"])
@limiter.limit("20 per minute", key_func=get_remote_address)
def public_download(record_id):
    """Download (sem login) de uma assinatura já gerada — a regra de
    disponibilidade depende de como a assinatura foi gerada (ver
    SignatureRecord.is_publicly_available):
    - Gerada individualmente: download único; depois disso só Supervisor ou
      Administrador conseguem baixá-la de novo (via Auditoria) e reenviar por
      WhatsApp.
    - Gerada por importação de planilha (colaborador tipicamente sem conta de
      usuário cadastrada): permite até PUBLIC_BATCH_DOWNLOAD_LIMIT downloads;
      ao atingir o limite, o registro é apagado — sem trava de "peça ao
      Supervisor", basta reimportar a planilha quando precisar de novo."""
    record = SignatureRecord.query.get_or_404(record_id)
    if record.status != "success" or not record.is_publicly_available:
        flash(
            "Esta assinatura não está mais disponível para download pelo portal público. "
            "Solicite ao Supervisor ou Administrador que baixe e envie por WhatsApp.",
            "error",
        )
        return redirect(url_for("main.outlook_help", nome=record.full_name))

    record.public_downloaded_at = datetime.utcnow()
    if record.source == "batch":
        record.public_download_count += 1
    db.session.add(PublicAccessLog(
        action="download",
        searched_name=record.full_name,
        record_id=record.id,
        ip_address=get_remote_address(),
    ))
    db.session.commit()

    download_name = f"assinatura-{record.full_name.replace(' ', '_')}.{record.output_format}"
    response = safe_send_file(
        current_app.config["GENERATED_UPLOAD_DIR"], record.output_filename, download_name=download_name
    )

    # Regra nova (v2.2.0): assinaturas de lote esgotaram o limite de
    # downloads públicos — apaga o registro e o arquivo. O sistema operacional
    # já abriu o arquivo para enviar a resposta acima (o send_file mantém o
    # descritor aberto durante o envio), então remover o arquivo agora não
    # interrompe este download: só impede novos.
    if record.source == "batch" and record.public_download_count >= SignatureRecord.PUBLIC_BATCH_DOWNLOAD_LIMIT:
        delete_record_files(record)
        db.session.delete(record)
        db.session.commit()

    return response


@main_bp.route("/modelo/fundo/<int:template_id>")
@login_required
def template_background(template_id):
    """Serve a imagem de fundo de um modelo — usada tanto no editor do admin
    quanto na pré-visualização em tempo real do usuário padrão."""
    template = SignatureTemplate.query.get_or_404(template_id)
    return safe_send_file(
        current_app.config["TEMPLATES_UPLOAD_DIR"],
        template.background_filename,
        as_attachment=False,
    )
