"""Pacote da Middle-Layer Defense IA -> Cliente.

Modulos (todos orientados a objetos):
  * config          -> classe Settings (configuracao via .env)
  * crypto          -> classe DefenseCrypto (MD5 / RSA / AES)
  * defense_client  -> classe DefenseManager (sessao + StartVideo)
  * streaming       -> classe VideoStreamer (RTSP -> MJPEG)
  * web             -> classe WebApplication (FastAPI, somente API + /docs)
"""

__version__ = "1.0.0"
