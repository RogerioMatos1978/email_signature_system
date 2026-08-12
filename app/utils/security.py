"""Helpers de segurança reutilizados pelos blueprints."""
import os

from flask import send_from_directory, abort, request


def safe_send_file(base_dir: str, filename: str, download_name: str | None = None, as_attachment: bool = True):
    """Serve um arquivo garantindo que o caminho resolvido permaneça dentro de
    base_dir — defesa em profundidade contra path traversal, mesmo que os
    nomes de arquivo já sejam gerados de forma segura (uuid4) no upload."""
    if not filename:
        abort(404)

    base_dir_real = os.path.realpath(base_dir)
    target_path = os.path.realpath(os.path.join(base_dir_real, filename))

    if os.path.commonpath([base_dir_real, target_path]) != base_dir_real:
        abort(404)
    if not os.path.isfile(target_path):
        abort(404)

    return send_from_directory(
        base_dir_real,
        os.path.basename(target_path),
        as_attachment=as_attachment,
        download_name=download_name or os.path.basename(target_path),
    )


def apply_security_headers(response):
    """Adiciona cabeçalhos HTTP de segurança padrão a todas as respostas."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "script-src 'self'; "
        # 'unsafe-inline' em style-src é necessário aqui: o editor visual de
        # posicionamento dos campos (admin) precisa mover marcadores para
        # coordenadas arbitrárias (x/y em %) via JavaScript, o que não é
        # possível com um conjunto fixo de classes CSS. script-src continua
        # restrito a 'self' (sem inline/eval), que é o vetor de XSS relevante.
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

    # HSTS: só faz sentido (e só é seguro) anunciar quando a requisição já
    # chegou via HTTPS de verdade — `request.is_secure` só reflete isso
    # corretamente atrás de um proxy reverso se TRUST_PROXY_HEADERS estiver
    # ativo (ver app/config.py e o ProxyFix em app/__init__.py). Em uso local
    # (HTTP puro, sem proxy) este cabeçalho simplesmente não é enviado.
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response
