import logging
import os
from datetime import datetime

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError

from .config import get_config
from .extensions import db, login_manager, csrf, limiter
from .utils.security import apply_security_headers


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(get_config())

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY não definido. Configure a variável de ambiente SECRET_KEY "
            "(veja .env.example) antes de iniciar a aplicação."
        )

    _configure_logging(app)
    _ensure_directories(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context(app)
    _register_hooks(app)

    @app.after_request
    def _security_headers(response):
        return apply_security_headers(response)

    @app.route("/healthz")
    def healthz():
        # Endpoint leve, sem autenticação, usado pelo HEALTHCHECK do Docker.
        return jsonify(status="ok"), 200

    return app


def _configure_logging(app):
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Nunca logar corpo de requisições/senhas — apenas metadados de operação.
    app.logger.setLevel(level)


def _ensure_directories(app):
    for key in ("INSTANCE_DIR", "TEMPLATES_UPLOAD_DIR", "PHOTOS_UPLOAD_DIR", "GENERATED_UPLOAD_DIR"):
        path = app.config[key]
        os.makedirs(path, exist_ok=True)


def _init_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None


def _register_blueprints(app):
    from .blueprints.auth.routes import auth_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.user.routes import user_bp
    from .blueprints.main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(user_bp, url_prefix="/painel")


def _register_error_handlers(app):
    def _wants_json():
        return request.path.startswith("/api") or request.accept_mimetypes.best == "application/json"

    @app.errorhandler(400)
    def bad_request(err):
        if _wants_json():
            return jsonify(error="Requisição inválida."), 400
        return render_template("errors/generic.html", code=400, message="Requisição inválida."), 400

    @app.errorhandler(401)
    def unauthorized(err):
        if _wants_json():
            return jsonify(error="Autenticação necessária."), 401
        return render_template("errors/generic.html", code=401, message="Faça login para continuar."), 401

    @app.errorhandler(403)
    def forbidden(err):
        if _wants_json():
            return jsonify(error="Acesso negado."), 403
        return render_template("errors/generic.html", code=403, message="Você não tem permissão para acessar esta página."), 403

    @app.errorhandler(404)
    def not_found(err):
        if _wants_json():
            return jsonify(error="Recurso não encontrado."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(err):
        message = "Arquivo(s) muito grande(s). Verifique o limite de tamanho permitido."
        if _wants_json():
            return jsonify(error=message), 413
        return render_template("errors/generic.html", code=413, message=message), 413

    @app.errorhandler(429)
    def rate_limited(err):
        message = "Muitas tentativas em pouco tempo. Aguarde alguns instantes e tente novamente."
        if _wants_json():
            return jsonify(error=message), 429
        return render_template("errors/generic.html", code=429, message=message), 429

    @app.errorhandler(CSRFError)
    def csrf_error(err):
        message = "Sua sessão expirou ou o formulário é inválido. Recarregue a página e tente novamente."
        if _wants_json():
            return jsonify(error=message), 400
        return render_template("errors/generic.html", code=400, message=message), 400

    @app.errorhandler(500)
    def internal_error(err):
        # Nunca expor stack trace/detalhes internos ao usuário final.
        app.logger.exception("Erro interno não tratado")
        db.session.rollback()
        if _wants_json():
            return jsonify(error="Erro interno do servidor."), 500
        return render_template("errors/generic.html", code=500, message="Ocorreu um erro interno. Tente novamente em instantes."), 500


def _register_context(app):
    @app.context_processor
    def inject_globals():
        return {
            "app_version": app.config.get("APP_VERSION", "1.0.0"),
            "current_year": datetime.utcnow().year,
        }


def _register_hooks(app):
    # Login único por usuário: se o token de sessão salvo no navegador não bater
    # mais com o token atual do usuário no banco (porque um login mais recente,
    # em outro dispositivo/navegador, gerou um token novo), esta sessão é
    # encerrada automaticamente — evita duas pessoas usando a mesma conta ao
    # mesmo tempo. Roda antes de qualquer outra checagem.
    session_exempt_endpoints = {"auth.login", "static", "healthz"}

    @app.before_request
    def enforce_single_session():
        if request.endpoint in session_exempt_endpoints:
            return None
        if not current_user.is_authenticated:
            return None

        if not getattr(current_user, "is_active_flag", True):
            logout_user()
            session.pop("session_token", None)
            flash("Esta conta foi desativada. Contate o administrador.", "error")
            return redirect(url_for("auth.login"))

        expected_token = getattr(current_user, "current_session_token", None)
        actual_token = session.get("session_token")

        if not expected_token or actual_token != expected_token:
            logout_user()
            session.pop("session_token", None)
            flash("Sua sessão foi encerrada porque este usuário fez login em outro dispositivo ou navegador.", "error")
            return redirect(url_for("auth.login"))
        return None

    # Força troca de senha em contas recém-criadas/resetadas pelo admin antes
    # de liberar qualquer outra funcionalidade (item de segurança).
    allowed_endpoints = {"auth.change_password", "auth.logout", "static", "healthz"}

    @app.before_request
    def enforce_password_change():
        if not current_user.is_authenticated:
            return None
        if not getattr(current_user, "must_change_password", False):
            return None
        if request.endpoint in allowed_endpoints:
            return None
        return redirect(url_for("auth.change_password"))
