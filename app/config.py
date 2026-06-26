"""Configuracao centralizada (carregada do arquivo .env).

A classe Settings le todas as variaveis de ambiente uma unica vez. O arquivo
.env (na raiz do projeto) e carregado automaticamente via python-dotenv.

Veja docs/code/config.md para a documentacao completa.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env da raiz do projeto (um nivel acima do pacote app/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    """Configuracao imutavel da aplicacao, derivada do ambiente/.env."""

    # --- Autenticacao Defense IA (preenchido no .env) ---
    defense_ip: str = field(default_factory=lambda: _env("DEFENSE_IP", "192.168.1.1"))
    defense_port: int = field(default_factory=lambda: int(_env("DEFENSE_PORT", "80")))
    defense_scheme: str = field(default_factory=lambda: _env("DEFENSE_SCHEME", "http"))
    defense_username: str = field(default_factory=lambda: _env("DEFENSE_USERNAME", "system"))
    defense_password: str = field(default_factory=lambda: _env("DEFENSE_PASSWORD", ""))

    # --- Identificacao do cliente exigida pela API ---
    client_mac: str = field(default_factory=lambda: _env("DEFENSE_CLIENT_MAC", "2C-F0-5D-4D-5E-DB"))
    client_type: str = field(default_factory=lambda: _env("DEFENSE_CLIENT_TYPE", "WINPC_V2"))
    verify_tls: bool = field(default_factory=lambda: _env("DEFENSE_VERIFY_TLS", "true").lower() != "false")

    # --- Temporizacao da sessao (segundos) ---
    keepalive_interval: int = field(default_factory=lambda: int(_env("DEFENSE_KEEPALIVE_INTERVAL", "22")))
    update_token_every_n_heartbeats: int = field(default_factory=lambda: int(_env("DEFENSE_UPDATE_TOKEN_EVERY", "60")))
    http_timeout: float = field(default_factory=lambda: float(_env("DEFENSE_HTTP_TIMEOUT", "15")))
    default_stream_type: str = field(default_factory=lambda: _env("DEFENSE_DEFAULT_STREAM_TYPE", "1"))
    # Quando a StartVideo devolve varios enderecos RTSP (interno|publico), forca
    # escolher o que contiver este host/IP. Vazio = prefere o DEFENSE_IP.
    rtsp_host_override: str = field(default_factory=lambda: _env("RTSP_HOST_OVERRIDE", ""))

    # --- Streaming MJPEG ---
    stream_fps_limit: float = field(default_factory=lambda: float(_env("STREAM_FPS_LIMIT", "0")))
    stream_jpeg_quality: int = field(default_factory=lambda: int(_env("STREAM_JPEG_QUALITY", "80")))
    # FPS de saida reemitido para cada espectador (independe da taxa da camera).
    stream_output_fps: float = field(default_factory=lambda: float(_env("STREAM_OUTPUT_FPS", "15")))
    # Motor de decode: "opencv" (CPU/padrao) ou "ffmpeg" (suporta NVDEC/GPU).
    stream_engine: str = field(default_factory=lambda: _env("STREAM_ENGINE", "opencv").lower())
    # Aceleracao de hardware do ffmpeg: "cuda" (NVDEC/RTX) ou "none".
    stream_hwaccel: str = field(default_factory=lambda: _env("STREAM_HWACCEL", "cuda").lower())
    # Caminho do executavel ffmpeg (precisa de build com CUDA p/ NVDEC).
    ffmpeg_path: str = field(default_factory=lambda: _env("FFMPEG_PATH", "ffmpeg"))
    # Largura para reescalar o frame (0 = mantem original). Reduz banda/CPU.
    stream_scale_width: int = field(default_factory=lambda: int(_env("STREAM_SCALE_WIDTH", "0")))
    # Segundos que a captura compartilhada continua viva apos o ultimo espectador sair.
    stream_idle_grace: float = field(default_factory=lambda: float(_env("STREAM_IDLE_GRACE", "10")))
    # Tempo maximo aguardando o 1o frame antes de encerrar o stream (camera morta/erro).
    stream_first_frame_timeout: float = field(default_factory=lambda: float(_env("STREAM_FIRST_FRAME_TIMEOUT", "20")))

    # --- Servidor da nossa API ---
    api_host: str = field(default_factory=lambda: _env("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(_env("API_PORT", "8000")))

    @property
    def defense_base_url(self) -> str:
        """URL base da plataforma Defense IA, montada a partir de scheme/ip/porta."""
        return f"{self.defense_scheme}://{self.defense_ip}:{self.defense_port}"


# Instancia unica reutilizada em toda a aplicacao.
settings = Settings()
