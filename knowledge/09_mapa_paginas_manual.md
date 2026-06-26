# 09 · Mapa do Manual — Fluxo Cronológico e Campos da API

Referência cruzada entre o **manual "Defense API 3.2"** (PDF em `docs/`) e o
consumo de dados implementado nesta API, **na ordem em que acontece**.

> **Páginas:** os números abaixo são as **páginas do PDF** (o que você abre no
> leitor). O número impresso no rodapé é sempre `PDF − 1` (ex.: PDF p. 159 =
> rodapé "158"). Sempre que possível cito também a **seção** (inequívoca).

---

## Ordem cronológica do consumo

| # | Etapa | Seção | Páginas (PDF) |
|---|---|---|---|
| 0 | Visão geral da conexão (3 passos) | 4.2 Get Started with Connection | 18 |
| 1 | Algoritmos de criptografia (MD5/RSA/AES) | 3.3.5 Example of Encryption mode | 13–16 |
| 2 | 1º Login (authorize) | 6.2.1.1 First Login | 111–112 |
| 3 | Cálculo da assinatura (5× MD5) | 4.3.1 (generateSignature) | 23 |
| 4 | 2º Login (authorize) | 6.2.1.2 The Second Login | 112–114 |
| 5 | Heartbeat (keepalive) | 6.2.1.3 Heartbeat Keep-alive | 114–115 |
| 6 | Renovar token (updateToken) | 6.2.1.4 Update Token | 115–116 |
| 7 | Inventário — árvore de organização | 6.2.3.2.1 Device Organization Tree (All) | 143–146 |
| 8 | Inventário — dispositivos/canais | 6.2.3.2.3 Getting Device Tree (All) | 149–153 |
| 9 | Iniciar vídeo (obter RTSP) | 6.2.4.2 Start Real-time Video | 159–161 |
| 10 | Montar/consumir o RTSP | 5.3 Video Services (Live View) | 72–74 (+ 80–81) |

Exemplo completo de login em Java (passos 1–6 juntos): **4.3.1**, PDF p. 19–23.

---

## Campos por etapa

### 1. Criptografia (PDF 13–16, seção 3.3.5)
- `encryptWithMD5`, `getRsaKeys`, `decryptRSAByPrivateKey`, `encryptWithAES7`,
  `decryptWithAES7`. AES = **CBC + PKCS7**; RSA = **PKCS#1 v1.5** (2048).

### 2. 1º Login — `POST /accounts/authorize` (PDF 111–112, seção 6.2.1.1)
- **Request:** `userName`, `ipAddress` (opc.), `clientType` (`WINPC_V2`).
- **Response:** `realm`, `randomKey`, `encryptType`, `publickey`.
- Observação: o `randomKey` expira em **10 s** (o 2º login deve ocorrer dentro disso).

### 3. Assinatura (PDF 23, seção 4.3.1)
```
temp1=md5(password); temp2=md5(user+temp1); temp3=md5(temp2)
temp4=md5(user+":"+realm+":"+temp3); signature=md5(temp4+":"+randomKey)
```
`temp4` é guardado para o updateToken: `md5(temp4+":"+token)`.

### 4. 2º Login — `POST /accounts/authorize` (PDF 112–114, seção 6.2.1.2)
- **Request:** `mac`, `signature`, `userName`, `randomKey`, `publicKey` (RSA do
  cliente, base64), `encryptType` (`MD5`), `ipAddress`, `clientType`, `userType`.
- **Response:** `token`, `duration`, `tokenRate`, `userId`, `credential`,
  `secretKey`, `secretVector` (estes dois = chave/vetor AES **encriptados em RSA**
  com a chave pública do cliente → decriptar com a privada), `reused`, …
- ⚠️ **Grafia do campo:** a referência formal usa **`encryptType`**; o exemplo
  Java (4.3.1) escreve **`encrytType`** (typo). Como `MD5` é o padrão, ambos
  funcionam — esta API envia `encrytType` (validado ao vivo). Se um servidor
  exigir o nome correto, troque para `encryptType`.

### 5. Keepalive — `PUT /accounts/keepalive` (PDF 114–115, seção 6.2.1.3)
- **Header:** `X-Subject-Token: {token}`. **Body:** `{ "token", "duration" }`.
- **Response:** `code` (`1000` = ok), `data.token`, `data.duration`.
- Chamar a cada **~22 s** (token expira em ~30 s sem heartbeat).

### 6. Update Token — `POST /accounts/updateToken` (PDF 115–116, seção 6.2.1.4)
- **Header:** `X-Subject-Token: {token}`. **Body:** `{ "signature": md5(temp4+":"+token) }`.
- **Response:** `data.token` (novo). Chamar a cada **~22 min** (`tokenRate` ~1800 s).

### 7. Árvore de organização — `GET /tree/deviceOrg` (PDF 143–146, seção 6.2.3.2.1)
- **Query:** `channelTypes` (1 = encoder/câmera), `sort`, `orgCode` (vazio = raiz `001`).
- **Response:** `data.departments[]` → `code`, `parentCode`, `name`, `channel[].id`.
- Uso aqui: mapear **código da unidade → nome da unidade**.

### 8. Dispositivos e canais — `POST /tree/devices` (PDF 149–153, seção 6.2.3.2.3)
- **Body:** `orgCode`, `deviceCodes` (vazio = todos), `categories`, `containVirtualDevice`.
- **Response:** `data.devices[]` → `name`, `orgCode`, `status`,
  `units[].channels[]` → `channelCode`, `channelName`, `channelType` (1 = câmera), `status`.
- Uso aqui: montar a lista de câmeras por unidade (`GET /api/v1/cameras`).

### 9. Start Real-time Video — `POST /MTS/Video/StartVideo` (PDF 159–161, seção 6.2.4.2)
- **Header:** `X-Subject-Token: {token}`.
- **Request:** `clientType`, `clientMac`, `project`, `method`
  (`MTS.Video.StartVideo`), `data{ streamType (1=principal,2=sub), channelId,
  dataType (1=vídeo), enableRtsps, enableMulticast, trackId, … }`.
- **Response:** `code`, `data{ url, token, session, vkId, vkValue, … }`.

### 10. Montagem e consumo do RTSP (PDF 72–74 e 80–81, seção 5.3)
- **URL final** = `url` + `?token=` + `token` (o `url` puro é recusado).
- O token RTSP é de **uso único** e expira em **~30 s** sem uso.
- Interação RTSP padrão: OPTIONS → DESCRIBE → SETUP → PLAY.

---

## Onde cada etapa vive nesta API
| Etapa do manual | Implementação |
|---|---|
| 1–6 (auth/sessão) | `app/crypto.py`, `app/defense_client.py` |
| 7–8 (inventário) | `DefenseManager.list_cameras` → `GET /api/v1/cameras` |
| 9 (StartVideo) | `DefenseManager.start_video` → `/cameras/{id}/rtsp` e `/stream` |
| 10 (RTSP/MJPEG) | `app/streaming.py` |
