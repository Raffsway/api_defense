# `app/crypto.py` — `DefenseCrypto`

## Responsabilidade
Implementar as primitivas de criptografia exigidas pelo login do Defense IA,
exatamente como o manual descreve (seção 3.3.5). É um **namespace coeso** de
métodos sem estado (estáticos/de classe).

## Métodos

### `md5_hex(text) -> str`
MD5 em hexadecimal minúsculo. Equivalente a `DigestUtils.md5Hex` (Java).

### `generate_signature(username, password, realm, random_key) -> (signature, temp4)`
Assinatura de login em **5 iterações MD5**:
```
temp1 = md5(password)
temp2 = md5(username + temp1)
temp3 = md5(temp2)
temp4 = md5(username + ":" + realm + ":" + temp3)
signature = md5(temp4 + ":" + random_key)
```
Retorna também `temp4`, reutilizado para assinar o `updateToken`
(`md5(temp4 + ":" + token)`).

### `generate_rsa_keypair(bits=2048) -> RsaKey`
Gera par RSA (privada PKCS#8, pública X.509).

### `public_key_to_base64(key) -> str`
Exporta a pública em DER/X.509 e codifica em base64 (formato exigido no corpo HTTP).

### `decrypt_rsa(b64_ciphertext, private_key) -> str`
Decripta valores RSA **PKCS#1 v1.5** retornados em base64 (`secretKey`/`secretVector`).
Itera em **blocos de 256 bytes** (chave de 2048 bits), como o exemplo Java.

### `encrypt_aes(plaintext, aes_key, aes_vector) -> str` / `decrypt_aes(...)`
AES **CBC + PKCS7**, com entrada/saída em **hex**. Equivalentes a
`encryptWithAES7` / `decryptWithAES7`. Usados para senhas e password do MQ.

## Validação
As primitivas foram testadas em round-trip:
- assinatura/temp4 com 32 chars hex;
- RSA: encriptar com a pública → `decrypt_rsa` recupera o texto;
- AES: `encrypt_aes` → `decrypt_aes` recupera o texto.

## Decisões de projeto
- Métodos **estáticos**: a criptografia não tem estado; a classe agrupa as
  operações e facilita injeção/mocking em `DefenseManager`.
- Padding **PKCS#7** explícito via `Crypto.Util.Padding` para casar com o Java.
