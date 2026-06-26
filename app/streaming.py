"""Streaming RTSP -> MJPEG com captura COMPARTILHADA por camera.

Otimizado para consumir varias cameras (e varios espectadores por camera) no
navegador, ao mesmo tempo, sem multiplicar conexoes RTSP nem decodificacoes:

  * CameraStream  -> 1 thread por camera: abre o RTSP uma unica vez, decodifica
                     e mantem sempre o ultimo frame JPEG pronto. Varios
                     espectadores leem esse mesmo frame.
  * CameraHub     -> registra/reaproveita um CameraStream por (canal, stream_type)
                     e entrega um gerador ASSINCRONO de MJPEG para cada cliente.

Por que assim:
  - 10 navegadores vendo a mesma camera = 1 decode (nao 10).
  - Geradores assincronos nao consomem threads do pool do FastAPI -> escala.
  - A captura sobe no 1o espectador e cai apos o ultimo sair (com carencia).

Veja docs/code/streaming.md para a documentacao completa.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import threading
import time
from typing import AsyncIterator, Awaitable, Callable, Optional

# Forca RTSP sobre TCP (mais estavel) -- antes de usar cv2.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402

from app.config import settings

logger = logging.getLogger("video")

BOUNDARY = "frame"
MJPEG_CONTENT_TYPE = f"multipart/x-mixed-replace; boundary={BOUNDARY}"

# Funcao que devolve a URL RTSP completa de um canal (ex.: DefenseManager.start_video).
UrlProvider = Callable[[str, Optional[str]], Awaitable[str]]


def _mjpeg_chunk(jpg: bytes) -> bytes:
    return (
        b"--" + BOUNDARY.encode() + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
        + jpg + b"\r\n"
    )


class CameraStream:
    """Captura compartilhada de UMA camera (1 thread, N espectadores)."""

    MAX_CONSECUTIVE_FAILURES = 30
    RECONNECT_BACKOFF = 2.0

    def __init__(
        self,
        channel_id: str,
        stream_type: Optional[str],
        url_provider: UrlProvider,
        loop: asyncio.AbstractEventLoop,
        jpeg_quality: int,
        idle_grace: float,
    ) -> None:
        self.channel_id = channel_id
        self.stream_type = stream_type
        self._url_provider = url_provider
        self._loop = loop
        self._jpeg_quality = jpeg_quality
        self._idle_grace = idle_grace

        self._latest: Optional[bytes] = None
        self._version = 0
        self._subscribers = 0
        self._idle_since = time.monotonic()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------ estado -------------------------------- #
    @property
    def latest(self) -> tuple[int, Optional[bytes]]:
        return self._version, self._latest

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def subscribers(self) -> int:
        return self._subscribers

    # --------------------------- ciclo de vida ---------------------------- #
    def _start(self) -> None:
        with self._lock:
            if self._running and self.is_alive():
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run, name=f"cam-{self.channel_id}", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._running = False

    # --------------------------- captura (thread) ------------------------- #
    def _acquire_url(self) -> str:
        """Pede uma URL RTSP fresca ao DefenseManager (rodando no event loop)."""
        future = asyncio.run_coroutine_threadsafe(
            self._url_provider(self.channel_id, self.stream_type), self._loop
        )
        return future.result(timeout=settings.http_timeout + 10)

    def _idle(self) -> bool:
        """True se ninguem assiste ha mais que a carencia (encerra a captura)."""
        return self._subscribers == 0 and (time.monotonic() - self._idle_since) > self._idle_grace

    def _run(self) -> None:
        """Dispatcher: escolhe o motor de decode (ffmpeg/GPU ou opencv/CPU)."""
        try:
            if settings.stream_engine == "ffmpeg":
                self._run_ffmpeg()
            else:
                self._run_opencv()
        finally:
            self._running = False

    # ----------------------- motor OpenCV (CPU) --------------------------- #
    def _run_opencv(self) -> None:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        while self._running:
            try:
                rtsp_url = self._acquire_url()
            except Exception as exc:
                logger.warning("[%s] falha ao obter RTSP: %s", self.channel_id, exc)
                time.sleep(self.RECONNECT_BACKOFF)
                continue

            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if not cap.isOpened():
                logger.error("[%s] nao abriu o RTSP.", self.channel_id)
                cap.release()
                time.sleep(self.RECONNECT_BACKOFF)
                continue

            logger.info("[%s] captura iniciada (opencv).", self.channel_id)
            failures = 0
            while self._running:
                if self._idle():
                    logger.info("[%s] ocioso; encerrando captura.", self.channel_id)
                    self._running = False
                    break
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures >= self.MAX_CONSECUTIVE_FAILURES:
                        logger.warning("[%s] muitas falhas; reconectando.", self.channel_id)
                        break
                    time.sleep(0.03)
                    continue
                failures = 0
                ok, buffer = cv2.imencode(".jpg", frame, encode_params)
                if ok:
                    self._latest = buffer.tobytes()
                    self._version += 1

            cap.release()
            logger.info("[%s] captura liberada.", self.channel_id)

    # -------------------- motor FFmpeg (GPU/NVDEC) ------------------------ #
    def _build_ffmpeg_cmd(self, rtsp_url: str) -> list[str]:
        # MJPEG q:v vai de 2 (melhor) a 31 (pior); mapeia da qualidade 1-100.
        qv = max(2, min(31, round(31 - (self._jpeg_quality / 100.0) * 29)))
        cmd = [settings.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp"]
        if settings.stream_hwaccel and settings.stream_hwaccel != "none":
            # NVDEC: decodifica o H.264/H.265 na GPU (RTX), liberando a CPU.
            cmd += ["-hwaccel", settings.stream_hwaccel]
        cmd += ["-i", rtsp_url, "-an"]
        if settings.stream_scale_width > 0:
            cmd += ["-vf", f"scale={settings.stream_scale_width}:-2"]
        if settings.stream_output_fps > 0:
            fps = settings.stream_output_fps
            cmd += ["-r", str(int(fps)) if float(fps).is_integer() else str(fps)]
        cmd += ["-f", "image2pipe", "-c:v", "mjpeg", "-q:v", str(qv), "pipe:1"]
        return cmd

    def _run_ffmpeg(self) -> None:
        while self._running:
            try:
                rtsp_url = self._acquire_url()
            except Exception as exc:
                logger.warning("[%s] falha ao obter RTSP: %s", self.channel_id, exc)
                time.sleep(self.RECONNECT_BACKOFF)
                continue

            cmd = self._build_ffmpeg_cmd(rtsp_url)
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7
                )
            except FileNotFoundError:
                logger.error("[%s] ffmpeg nao encontrado em '%s'.", self.channel_id, settings.ffmpeg_path)
                time.sleep(self.RECONNECT_BACKOFF)
                continue

            logger.info("[%s] captura iniciada (ffmpeg hwaccel=%s).", self.channel_id, settings.stream_hwaccel)
            buf = bytearray()
            try:
                while self._running:
                    if self._idle():
                        logger.info("[%s] ocioso; encerrando captura.", self.channel_id)
                        self._running = False
                        break
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        logger.warning("[%s] ffmpeg encerrou; reconectando.", self.channel_id)
                        break
                    buf += chunk
                    self._extract_jpegs(buf)
            finally:
                proc.kill()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    pass
            logger.info("[%s] captura liberada (ffmpeg).", self.channel_id)

    def _extract_jpegs(self, buf: bytearray) -> None:
        """Separa JPEGs completos (FFD8..FFD9) do buffer e publica o ultimo."""
        while True:
            soi = buf.find(b"\xff\xd8")
            if soi < 0:
                buf.clear()
                return
            eoi = buf.find(b"\xff\xd9", soi + 2)
            if eoi < 0:
                if soi > 0:
                    del buf[:soi]  # descarta lixo antes do proximo SOI
                return
            frame = bytes(buf[soi:eoi + 2])
            del buf[:eoi + 2]
            self._latest = frame
            self._version += 1

    # --------------------------- espectadores ----------------------------- #
    async def subscribe(self) -> AsyncIterator[bytes]:
        """Gerador assincrono de MJPEG para um espectador."""
        self._subscribers += 1
        self._start()
        interval = 1.0 / settings.stream_output_fps if settings.stream_output_fps > 0 else 0.04
        first_frame_timeout = settings.stream_first_frame_timeout
        started = time.monotonic()
        last_version = -1
        got_first = False
        try:
            while True:
                version, frame = self.latest
                if frame is not None and version != last_version:
                    last_version = version
                    got_first = True
                    yield _mjpeg_chunk(frame)
                elif not got_first and (time.monotonic() - started) > first_frame_timeout:
                    logger.warning("[%s] sem 1o frame em %ss; encerrando.", self.channel_id, first_frame_timeout)
                    break
                await asyncio.sleep(interval)
        finally:
            self._subscribers -= 1
            if self._subscribers <= 0:
                self._subscribers = 0
                self._idle_since = time.monotonic()


class CameraHub:
    """Gerencia um CameraStream por (canal, stream_type), reaproveitando capturas."""

    def __init__(self, url_provider: UrlProvider) -> None:
        self._url_provider = url_provider
        self._streams: dict[tuple[str, Optional[str]], CameraStream] = {}
        self._lock = asyncio.Lock()

    @property
    def content_type(self) -> str:
        return MJPEG_CONTENT_TYPE

    async def _get_or_create(self, channel_id: str, stream_type: Optional[str]) -> CameraStream:
        key = (channel_id, stream_type)
        async with self._lock:
            stream = self._streams.get(key)
            if stream is None or not (stream.is_alive() or stream.subscribers > 0):
                stream = CameraStream(
                    channel_id=channel_id,
                    stream_type=stream_type,
                    url_provider=self._url_provider,
                    loop=asyncio.get_running_loop(),
                    jpeg_quality=settings.stream_jpeg_quality,
                    idle_grace=settings.stream_idle_grace,
                )
                self._streams[key] = stream
            return stream

    async def mjpeg_stream(self, channel_id: str, stream_type: Optional[str]) -> AsyncIterator[bytes]:
        """Entrega o MJPEG de uma camera, reaproveitando a captura compartilhada."""
        stream = await self._get_or_create(channel_id, stream_type)
        async for chunk in stream.subscribe():
            yield chunk

    def stats(self) -> list[dict]:
        """Resumo das capturas ativas (para /health ou debug)."""
        return [
            {
                "channel_id": s.channel_id,
                "stream_type": s.stream_type,
                "subscribers": s.subscribers,
                "alive": s.is_alive(),
            }
            for s in self._streams.values()
        ]

    async def shutdown(self) -> None:
        for stream in self._streams.values():
            stream.stop()
