"""Entrypoint da Middle-Layer Defense IA -> Cliente.

Uso:
    python main.py
    # ou
    uvicorn main:app --host 0.0.0.0 --port 8000

Abra http://localhost:8000/ para o painel navegavel
ou  http://localhost:8000/docs para a documentacao Swagger.
"""
from __future__ import annotations

import uvicorn

from app.config import settings
from app.web import WebApplication

# Instancia da aplicacao (objeto unico) e o app FastAPI exposto ao uvicorn.
web_application = WebApplication()
app = web_application.app


def main() -> None:
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    main()
