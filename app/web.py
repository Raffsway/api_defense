"""WebApplication: monta a aplicacao FastAPI e os endpoints da API.

Esta classe orquestra os componentes (DefenseManager + CameraHub), define o
ciclo de vida (login + keepalive) e expoe apenas os endpoints HTTP da API. A
unica interface e a documentacao Swagger em /docs (sem frontend).

Veja docs/code/web.md para a documentacao completa.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from app import __version__
from app.config import settings
from app.defense_client import DefenseError, DefenseManager
from app.streaming import CameraHub

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("api")


class WebApplication:
    """Fabrica e configura a aplicacao FastAPI da Middle-Layer."""

    def __init__(self) -> None:
        self.manager = DefenseManager()
        # Hub de captura compartilhada: reaproveita 1 conexao RTSP por camera
        # entre todos os espectadores (varias cameras/abas no navegador).
        self.hub = CameraHub(self.manager.start_video)
        self.app = self._build_app()

    # ------------------------------------------------------------------ #
    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="Defense API",
            description="API que entrega o feed das cameras do Intelbras Defense IA 3.2.",
            version=__version__,
            lifespan=self._lifespan,
        )
        self._register_routes(app)
        return app

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        logger.info("Autenticando no Defense IA (%s)...", settings.defense_base_url)
        try:
            await self.manager.login()
            self.manager.start_keepalive()
            logger.info("Sessao ativa. Keepalive a cada %ss.", settings.keepalive_interval)
        except Exception as exc:  # nao impede o servidor de subir
            logger.error("Falha no login inicial: %s (sera refeito sob demanda).", exc)
        yield
        logger.info("Encerrando capturas e sessao Defense IA...")
        await self.hub.shutdown()
        await self.manager.close()

    # ------------------------------------------------------------------ #
    def _register_routes(self, app: FastAPI) -> None:

        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            """Redireciona a raiz para a documentacao Swagger."""
            return RedirectResponse(url="/docs")

        @app.get("/health", tags=["infra"])
        async def health() -> dict:
            """Status da sessao Defense IA."""
            return {
                "status": "ok",
                "version": __version__,
                "defense_base_url": settings.defense_base_url,
                "defense_authenticated": self.manager.is_authenticated,
                "user_id": self.manager.user_id,
                "active_streams": self.hub.stats(),
            }

        @app.get("/api/v1/cameras", tags=["cameras"])
        async def list_cameras(
            online_only: bool = Query(default=False, description="Somente câmeras online"),
        ) -> JSONResponse:
            """Lista as câmeras do Defense agrupadas por unidade (preenche o mural)."""
            try:
                data = await self.manager.list_cameras(online_only=online_only)
            except DefenseError as exc:
                raise HTTPException(status_code=502, detail=str(exc))
            except httpx.RequestError as exc:
                raise HTTPException(status_code=503, detail=f"Defense IA inacessível: {exc!s}")
            return JSONResponse(data)

        @app.get("/api/v1/cameras/{channel_id}/rtsp", tags=["cameras"])
        async def get_rtsp(
            channel_id: str,
            stream_type: Optional[str] = Query(
                default=None, description="1 = principal, 2 = secundario"
            ),
        ) -> JSONResponse:
            """Retorna a URL RTSP direta da câmera (token de vídeo embutido).

            ⚠️ **Token de uso único:** o `rtsp_url` traz um token gerado pelo
            Defense que é **válido para UMA conexão** e **expira em ~30s** sem
            uso. Não dá para copiar/colar e reutilizar o link (um player como o
            VLC pedirá usuário/senha quando o token vencer).

            **Como consumir corretamente:**
            - **Apenas visualizar** (VLC/navegador): use o endpoint `/stream`
              (MJPEG) — a API renova o token a cada acesso, sem login.
            - **Integração (cliente/NVR):** chame este endpoint **imediatamente
              antes** de abrir o RTSP e, a **cada reconexão**, chame de novo para
              obter um token novo. Veja o exemplo em
              `knowledge/10_consumo_rtsp.md`.
            """
            rtsp_url = await self._safe_start_video(channel_id, stream_type)
            return JSONResponse({"channel_id": channel_id, "rtsp_url": rtsp_url})

        @app.get("/api/v1/cameras/{channel_id}/stream", tags=["cameras"])
        async def get_stream(
            channel_id: str,
            stream_type: Optional[str] = Query(
                default=None, description="1 = principal, 2 = secundario"
            ),
        ) -> StreamingResponse:
            """Proxy HTTP MJPEG usando captura compartilhada (1 decode por câmera).

            Forma **recomendada para apenas visualizar**: o link é **reutilizável**
            e **não pede login** — a API gerencia o token de uso único do Defense
            internamente. Abra direto no navegador ou em
            `VLC → Abrir Fluxo de Rede`. Vários espectadores na mesma câmera
            compartilham 1 conexão RTSP. Veja `knowledge/10_consumo_rtsp.md`.
            """
            return StreamingResponse(
                self.hub.mjpeg_stream(channel_id, stream_type),
                media_type=self.hub.content_type,
                headers={"Cache-Control": "no-cache, no-store"},
            )

    # ------------------------------------------------------------------ #
    async def _safe_start_video(self, channel_id: str, stream_type: Optional[str]) -> str:
        """Chama StartVideo convertendo erros em HTTPException adequada."""
        try:
            return await self.manager.start_video(channel_id, stream_type)
        except DefenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        except httpx.RequestError as exc:
            # Defense IA inacessivel (conexao/timeout): servico indisponivel.
            raise HTTPException(
                status_code=503,
                detail=f"Defense IA inacessivel em {settings.defense_base_url}: {exc!s}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erro ao obter video do canal %s", channel_id)
            raise HTTPException(status_code=500, detail=str(exc))


def create_app() -> FastAPI:
    """Factory usada pelo uvicorn (ex.: uvicorn app.web:create_app --factory)."""
    return WebApplication().app
