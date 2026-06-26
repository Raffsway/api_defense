# 03 · Fluxo de Autenticação (RSA / MD5 / AES)

> Fonte: manual Defense API 3.2, seções 3.3.5 e 4.3.1. Implementado em
> `app/crypto.py` (`DefenseCrypto`) e `app/defense_client.py` (`DefenseManager`).
>
> Para o mapa cronológico de **páginas do manual + campos por etapa**, veja
> [09_mapa_paginas_manual.md](09_mapa_paginas_manual.md).

## Visão geral

O login é em **duas etapas** no mesmo endpoint `POST /accounts/authorize`.
A 1ª chamada **retorna HTTP 401 de propósito** (é o protocolo) trazendo os
dados de criptografia; a 2ª envia a assinatura e a chave pública RSA.

## Etapa 1 — Primeira autorização

```http
POST /brms/api/v1.0/accounts/authorize
{ "userName": "system", "ipAddress": "", "clientType": "WINPC_V2" }
```
Resposta (HTTP 401, normal) contém:
- `realm`
- `randomKey`

## Cálculo da assinatura (5× MD5)

```
temp1     = md5(password)
temp2     = md5(userName + temp1)
temp3     = md5(temp2)
temp4     = md5(userName + ":" + realm + ":" + temp3)   # guardar para updateToken
signature = md5(temp4 + ":" + randomKey)
```
MD5 sempre em **hex minúsculo**.

## Etapa 2 — Segunda autorização

Gera-se um par RSA 2048 (pública em DER/X.509 → base64) e envia:
```http
POST /brms/api/v1.0/accounts/authorize
{
  "mac": "2C-F0-5D-4D-5E-DB",
  "signature": "<signature>",
  "userName": "system",
  "randomKey": "<randomKey>",
  "publicKey": "<base64 X.509>",
  "encrytType": "MD5",          // grafia literal do manual (sic)
  "ipAddress": "",
  "clientType": "WINPC_V2",
  "userType": "0"
}
```
Resposta de sucesso contém:
- `token` — usado no header `X-Subject-Token` das chamadas seguintes
- `userId`, `duration`
- `secretKey`, `secretVector` — **chave e vetor AES**, encriptados em RSA com a
  nossa chave pública → decriptar com a nossa privada (PKCS#1 v1.5).
  Necessários apenas para criptografar senhas e o password do MQ.

## Manutenção da sessão

| Ação | Quando | Como |
|---|---|---|
| **Keepalive** | a cada ~22s | `PUT /accounts/keepalive` com `{ "token": token }` + header `X-Subject-Token`. Sucesso = `code == "1000"` |
| **updateToken** | a cada ~22min (60 heartbeats) | `POST /accounts/updateToken` com `{ token, signature: md5(temp4 + ":" + token) }` → novo `data.token` |

Sem keepalive o token expira em ~30s; sem updateToken expira no `tokenRate` (~30min).

## Tratamento de erros

- **401** em qualquer chamada de negócio → re-login automático + 1 nova tentativa.
- Códigos `7001`/`7002` (token inválido/expirado) → idem.
- Falha no login inicial **não derruba** o servidor; é refeito sob demanda.

## Primitivas de criptografia (resumo)

| Operação | Algoritmo |
|---|---|
| Assinatura | MD5 (5 iterações) |
| Troca de chave AES | RSA **PKCS#1 v1.5**, 2048 bits (blocos de 256 bytes) |
| Senhas / MQ | AES **CBC** + **PKCS7**, entrada/saída em hex |
