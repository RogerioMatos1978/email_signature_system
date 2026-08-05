import secrets
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from flask_limiter.util import get_remote_address

from ...extensions import db, limiter
from ...forms import LoginForm, ChangePasswordForm
from ...models import User

auth_bp = Blueprint("auth", __name__)


def _login_rate_key() -> str:
    """Chave de rate limit do login: IP + usuário informado.

    Em Docker/rede local, todos os clientes podem chegar com o mesmo IP interno
    (proxy do Docker) — limitar apenas por IP faria as tentativas de UMA pessoa
    bloquearem o login da rede inteira. Combinar com o usuário mantém a
    proteção contra força bruta por conta, sem punir os demais.
    """
    username = (request.form.get("username") or "").strip().lower()[:80]
    return f"{get_remote_address()}|{username}"


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute", methods=["POST"], key_func=_login_rate_key)
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        user = User.query.filter_by(username=username).first()

        # Mensagem de erro genérica proposital: não revela se o usuário existe
        # ou não (evita enumeração de contas).
        if user is None or not user.check_password(form.password.data):
            flash("Usuário ou senha inválidos.", "error")
            return render_template("auth/login.html", form=form), 401

        if not user.is_active:
            flash("Esta conta está desativada. Contate o administrador.", "error")
            return render_template("auth/login.html", form=form), 403

        # Proteção contra fixação de sessão (OWASP): descarta qualquer dado de
        # sessão pré-login antes de autenticar — a sessão autenticada nasce limpa.
        session.clear()

        login_user(user, remember=False)
        user.last_login_at = datetime.utcnow()

        # Login único por usuário: gera um token novo e o grava no banco,
        # invalidando qualquer sessão anterior desse mesmo usuário (ela será
        # deslogada automaticamente no próximo request — ver enforce_single_session).
        token = secrets.token_hex(32)
        user.current_session_token = token
        session["session_token"] = token
        db.session.commit()

        next_url = request.args.get("next")
        # Nunca redirecionar para URLs externas (proteção contra open redirect).
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    # Só limpa o token no banco se ainda for o desta sessão (evita apagar o
    # token de um login mais recente feito em outro dispositivo).
    if current_user.current_session_token == session.get("session_token"):
        current_user.current_session_token = None
        db.session.commit()
    logout_user()
    session.pop("session_token", None)
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/senha", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Senha atual incorreta.", "error")
            return render_template("auth/change_password.html", form=form)

        if form.current_password.data == form.new_password.data:
            flash("A nova senha deve ser diferente da senha atual.", "error")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        current_user.must_change_password = False
        db.session.commit()
        flash("Senha alterada com sucesso.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/change_password.html", form=form)
