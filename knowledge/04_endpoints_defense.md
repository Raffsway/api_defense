# 04 · Endpoints Internos (Nossa API → Defense IA)

Base URL: `{DEFENSE_SCHEME}://{DEFENSE_IP}:{DEFENSE_PORT}` (ex.: `http://192.168.1.1:80`).
Todas as chamadas de negócio levam o header `X-Subject-Token: {token}`.

## 1. Autorização (login duplo)
```
POST /brms/api/v1.0/accounts/authorize
```
Ver [03_fluxo_autenticacao.md](03_fluxo_autenticacao.md). 1ª chamada → `realm`+`randomKey`
(HTTP 401 normal). 2ª chamada → `token`, `userId`, `secretKey`, `secretVector`.

## 2. Keepalive (heartbeat)
```
PUT /brms/api/v1.0/accounts/keepalive
Header: X-Subject-Token: {token}
Body:   { "token": "{token}" }
```
Sucesso: `code == "1000"`. Chamar a cada ~22s.

## 3. Update Token
```
POST /brms/api/v1.0/accounts/updateToken
Body: { "token": "{token}", "signature": "md5(temp4:token)" }
```
Sucesso devolve `data.token` (novo). Chamar a cada ~22min.

## 4. Start Real-time Video
```
POST /brms/api/v1.0/MTS/Video/StartVideo
Header: X-Subject-Token: {token}
```
Body:
```json
{
  "clientType": "WINPC_V2",
  "clientMac": "30:9c:23:79:40:08",
  "clientPushId": "",
  "project": "PSDK",
  "method": "MTS.Video.StartVideo",
  "data": {
    "streamType": "1",          // 1: principal, 2: secundário
    "optional": "/brms/api/v1.0/MTS/Video/StartVideo",
    "trackId": "",
    "extend": "",
    "channelId": "1000040$1$0$0",
    "keyCode": "",
    "planId": "",
    "dataType": "1",            // 1: vídeo, 2: áudio, 3: áudio+vídeo
    "enableRtsps": "0",
    "enableMulticast": "0"
  }
}
```
Resposta (sucesso `code == 1000`):
```json
{
  "code": 1000,
  "data": {
    "url": "rtsp://192.168.1.1:9100/vms/monitor/param/cameraid=1000040%240%26substream=1",
    "token": "2204",
    "session": "2204"
  }
}
```
**URL RTSP final** = `url` + `?token=` + `token`. O token RTSP é de **uso único**
e expira em ~30s sem uso.

⚠️ **Múltiplos endereços:** em servidores com NAT, o campo `url` pode trazer
**vários endereços separados por `|`** (ex.: `rtsp://IP_INTERNO...|rtsp://IP_PUBLICO...`),
e ainda pode haver `url2` (alternativo). É preciso **separar por `|`**, escolher um
e colar o `?token=` **nele** (não na string inteira). Esta API escolhe o endereço
que contém o `DEFENSE_IP` (configurável via `RTSP_HOST_OVERRIDE`). Ver
`DefenseManager._choose_rtsp` em `app/defense_client.py`.

## Códigos de retorno relevantes
| Código | Significado |
|---|---|
| `1000` | Sucesso |
| `7001` / `7002` | Token inválido / expirado → re-login |
| HTTP `401` | Não autenticado → re-login |

## `channelId`
Identificador único do canal (ex.: `1000040$1$0$0`), correspondente ao
`channelCode` retornado por **"Get Device Organization Tree (All)"**.
