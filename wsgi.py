"""Ponto de entrada WSGI usado pelo Gunicorn em produção."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Uso apenas para desenvolvimento local (flask run/gunicorn são preferidos em produção)
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
