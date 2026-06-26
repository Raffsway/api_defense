"""DefenseManager: gestor da sessao autenticada com o Intelbras Defense IA 3.2.

Encapsula:
  * Login em duas etapas (assinatura MD5 + chave publica RSA).
  * Decriptacao RSA de secretKey/secretVector (chave/vetor AES).
  * Keepalive (~22s) e updateToken (~22min) em background.
  * StartVideo + montagem da URL RTSP completa.
  * Re-login automatico em 401 / token invalido.

Veja docs/code/defense_client.md para a documentacao completa.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx
from Crypto.PublicKey import RSA

from app.config import settings
from app.crypto import DefenseCrypto

logger = logging.getLogger("defense")

SUCCESS_CODE = "1000"
_AUTH_PATH = "/brms/api/v1.0/accounts/authorize"
_KEEPALIVE_PATH = "/brms/api/v1.0/accounts/keepalive"
_UPDATE_TOKEN_PATH = "/brms/api/v1.0/accounts/updateToken"
_START_VIDEO_PATH = "/brms/api/v1.0/MTS/Video/StartVideo"
_DEVICE_ORG_PATH = "/brms/api/v1.0/tree/deviceOrg"
_DEVICES_PATH = "/brms/api/v1.0/tree/devices"
_INVALID_TOKEN_CODES = {"7001", "7002"}
_ENCODER_CHANNEL_TYPE = "1"  # canal de cameras (encoder)


class DefenseError(RuntimeError):
    """Erro de negocio retornado pela plataforma Defense IA."""


class DefenseManager:
    """Mantem uma sessao autenticada e expoe operacoes de alto nivel."""

    def __init__(self, crypto: Optional[DefenseCrypto] = None) -> None:
        self._crypto = crypto or DefenseCrypto()
        self._client = httpx.AsyncClient(
            base_url=settings.defense_base_url,
            timeout=settings.http_timeout,
            verify=settings.verify_tls,
        )
        # Estado da sessao
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.aes_key: Optional[str] = None
        self.aes_vector: Optional[str] = None
        self._temp4: Optional[str] = None

        self._keepalive_task: Optional[asyncio.Task[None]] = None
        self._login_lock = asyncio.Lock()

    @property
    def is_authenticated(self) -> bool:
        return self.token is not None

    # --------------------------- ciclo de vida ----------------------------- #
    async def login(self) -> None:
        """Executa o fluxo de login duplo e popula o estado da sessao."""
        async with self._login_lock:
            realm, random_key = await self._first_authorize()
            await self._second_authorize(realm, random_key)
            logger.info("Login no Defense IA concluido (userId=%s).", self.user_id)

    async def _first_authorize(self) -> tuple[str, str]:
        """1a etapa: o servidor responde 401 com realm + randomKey (normal)."""
        body = {
            "userName": settings.defense_username,
            "ipAddress": "",
            "clientType": settings.client_type,
        }
        resp = await self._client.post(_AUTH_PATH, json=body)
        data = _safe_json(resp)
        realm, random_key = data.get("realm"), data.get("randomKey")
        if not realm or not random_key:
            raise DefenseError(f"1a autorizacao sem realm/randomKey: {data}")
        return realm, random_key

    async def _second_authorize(self, realm: str, random_key: str) -> None:
        """2a etapa: envia assinatura + chave publica RSA e obtem o token."""
        signature, temp4 = self._crypto.generate_signature(
            settings.defense_username, settings.defense_password, realm, random_key
        )
        self._temp4 = temp4

        rsa_key: RSA.RsaKey = self._crypto.generate_rsa_keypair(2048)
        public_b64 = self._crypto.public_key_to_base64(rsa_key)

        body = {
            "mac": settings.client_mac,
            "signature": signature,
            "userName": settings.defense_username,
            "randomKey": random_key,
            "publicKey": public_b64,
            "encrytType": "MD5",  # grafia literal do manual (sic)
            "ipAddress": "",
            "clientType": settings.client_type,
            "userType": "0",
        }
        resp = await self._client.post(_AUTH_PATH, json=body)
        data = _safe_json(resp)
        token = data.get("token")
        if not token:
            raise DefenseError(f"2a autorizacao falhou (sem token): {data}")

        self.token = token
        self.user_id = data.get("userId")

        secret_key_rsa = data.get("secretKey")
        secret_vector_rsa = data.get("secretVector")
        if secret_key_rsa and secret_vector_rsa:
            try:
                self.aes_key = self._crypto.decrypt_rsa(secret_key_rsa, rsa_key)
                self.aes_vector = self._crypto.decrypt_rsa(secret_vector_rsa, rsa_key)
            except Exception as exc:  # AES so e necessario p/ senhas/MQ
                logger.warning("Falha ao decriptar secretKey/secretVector: %s", exc)

    async def close(self) -> None:
        await self.stop_keepalive()
        await self._client.aclose()

    # ----------------------------- keep-alive ------------------------------ #
    def start_keepalive(self) -> None:
        if self._keepalive_task is None or self._keepalive_task.done():
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def stop_keepalive(self) -> None:
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        self._keepalive_task = None

    async def _keepalive_loop(self) -> None:
        heartbeat_count = 0
        while True:
            try:
                await asyncio.sleep(settings.keepalive_interval)
                await self._keepalive_once()
                heartbeat_count += 1
                if heartbeat_count >= settings.update_token_every_n_heartbeats:
                    heartbeat_count = 0
                    await self._update_token()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Heartbeat falhou (%s). Tentando re-login...", exc)
                try:
                    await self.login()
                except Exception as login_exc:
                    logger.error("Re-login falhou: %s", login_exc)

    async def _keepalive_once(self) -> None:
        resp = await self._client.put(
            _KEEPALIVE_PATH, json={"token": self.token}, headers=self._auth_headers()
        )
        data = _safe_json(resp)
        if str(data.get("code")) != SUCCESS_CODE:
            raise DefenseError(f"keepalive retornou {data}")
        logger.debug("keepalive ok")

    async def _update_token(self) -> None:
        if not self._temp4 or not self.token:
            return
        signature = self._crypto.md5_hex(f"{self._temp4}:{self.token}")
        resp = await self._client.post(
            _UPDATE_TOKEN_PATH,
            json={"token": self.token, "signature": signature},
            headers=self._auth_headers(),
        )
        data = _safe_json(resp)
        if str(data.get("code")) == SUCCESS_CODE:
            new_token = (data.get("data") or {}).get("token")
            if new_token:
                self.token = new_token
                logger.info("Token renovado.")
        else:
            logger.warning("updateToken retornou %s; forcando re-login.", data)
            await self.login()

    # ----------------------------- video ----------------------------------- #
    async def start_video(self, channel_id: str, stream_type: Optional[str] = None) -> str:
        """Chama StartVideo e devolve a URL RTSP completa (com ?token=...)."""
        stream_type = stream_type or settings.default_stream_type
        body = {
            "clientType": settings.client_type,
            "clientMac": settings.client_mac,
            "clientPushId": "",
            "project": "PSDK",
            "method": "MTS.Video.StartVideo",
            "data": {
                "streamType": stream_type,
                "optional": _START_VIDEO_PATH,
                "trackId": "",
                "extend": "",
                "channelId": channel_id,
                "keyCode": "",
                "planId": "",
                "dataType": "1",  # 1: video, 2: audio, 3: audio+video
                "enableRtsps": "0",
                "enableMulticast": "0",
            },
        }
        data = await self._post_with_relogin(_START_VIDEO_PATH, body)
        if str(data.get("code")) != SUCCESS_CODE:
            raise DefenseError(f"StartVideo falhou: {data}")

        payload = data.get("data") or {}
        url, video_token = payload.get("url"), payload.get("token")
        if not url:
            raise DefenseError(f"StartVideo nao retornou url: {data}")

        full_url = f"{url}?token={video_token}" if video_token else url
        logger.info("RTSP gerada para canal %s", channel_id)
        return full_url

    # --------------------------- inventario --------------------------------- #
    async def list_cameras(self, online_only: bool = False) -> dict[str, Any]:
        """Lista as cameras (canais encoder) agrupadas por unidade/organizacao.

        Combina:
          * /tree/deviceOrg  -> nome de cada unidade (departamento);
          * /tree/devices    -> dispositivos + canais (channelCode/channelName).
        """
        # 1) Mapa codigo-da-unidade -> nome.
        org_names: dict[str, str] = {}
        try:
            tree = await self._request_with_relogin(
                "GET", f"{_DEVICE_ORG_PATH}?channelTypes={_ENCODER_CHANNEL_TYPE}&sort=&orgCode="
            )
            for dep in (tree.get("data") or {}).get("departments", []):
                if dep.get("code"):
                    org_names[dep["code"]] = dep.get("name") or dep["code"]
        except Exception as exc:  # nao fatal: usamos o orgCode como nome
            logger.warning("Falha ao obter deviceOrg: %s", exc)

        # 2) Dispositivos + canais.
        body = {"orgCode": "", "deviceCodes": [], "categories": [], "containVirtualDevice": "1"}
        data = await self._request_with_relogin("POST", _DEVICES_PATH, json=body)
        if str(data.get("code")) != SUCCESS_CODE:
            raise DefenseError(f"tree/devices falhou: {data}")

        # 3) Agrupa canais por unidade.
        units: dict[str, dict[str, Any]] = {}
        total = 0
        for device in (data.get("data") or {}).get("devices", []):
            device_name = device.get("name") or device.get("code")
            org_code = device.get("orgCode") or "001"
            device_online = str(device.get("status")) == "1"
            for unit in device.get("units", []):
                for ch in unit.get("channels", []):
                    if ch.get("channelType") != _ENCODER_CHANNEL_TYPE:
                        continue
                    online = str(ch.get("status")) == "1"
                    if online_only and not online:
                        continue
                    bucket = units.setdefault(
                        org_code,
                        {"code": org_code, "name": org_names.get(org_code, org_code), "cameras": []},
                    )
                    bucket["cameras"].append(
                        {
                            "channel_code": ch.get("channelCode"),
                            "channel_name": ch.get("channelName") or ch.get("channelCode"),
                            "device_name": device_name,
                            "online": online and device_online,
                        }
                    )
                    total += 1

        unit_list = sorted(units.values(), key=lambda u: u["name"])
        return {"total": total, "units": unit_list}

    # ----------------------------- helpers ---------------------------------- #
    def _auth_headers(self) -> dict[str, str]:
        return {
            "X-Subject-Token": self.token or "",
            "Content-Type": "application/json;charset=UTF-8",
        }

    async def _post_with_relogin(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST autenticado; em 401/token invalido refaz login e tenta 1x."""
        return await self._request_with_relogin("POST", path, json=body)

    async def _request_with_relogin(
        self, method: str, path: str, json: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Requisicao autenticada; em 401/token invalido refaz login e tenta 1x."""
        if not self.token:
            await self.login()

        resp = await self._client.request(method, path, json=json, headers=self._auth_headers())
        if resp.status_code == 401:
            logger.info("401 em %s; refazendo login.", path)
            await self.login()
            resp = await self._client.request(method, path, json=json, headers=self._auth_headers())

        data = _safe_json(resp)
        if str(data.get("code")) in _INVALID_TOKEN_CODES:
            await self.login()
            resp = await self._client.request(method, path, json=json, headers=self._auth_headers())
            data = _safe_json(resp)
        return data


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        raise DefenseError(f"Resposta nao-JSON ({resp.status_code}): {resp.text[:300]}")
