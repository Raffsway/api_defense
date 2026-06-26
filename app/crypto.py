"""Primitivas de criptografia do login Defense IA (classe DefenseCrypto).

Implementa exatamente os algoritmos descritos na secao "3.3.5 Example of
Encryption mode" e "4.3.1 Example of Login Authentication" do manual
Defense API 3.2:

  * MD5 (assinatura de login em 5 etapas)
  * RSA PKCS#1 v1.5 (gera par de chaves e decripta secretKey/secretVector)
  * AES/CBC/PKCS7 (criptografia de senhas e do password do MQ)

Veja docs/code/crypto.md para a documentacao completa.
"""
from __future__ import annotations

import base64
import hashlib

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad


class DefenseCrypto:
    """Agrupa as operacoes de criptografia exigidas pelo Defense IA.

    Todos os metodos sao estaticos (sem estado) -- a classe serve como namespace
    coeso para as primitivas.
    """

    # ------------------------------ MD5 ----------------------------------- #
    @staticmethod
    def md5_hex(text: str) -> str:
        """MD5 em hexadecimal minusculo (equivalente a DigestUtils.md5Hex)."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @classmethod
    def generate_signature(
        cls, username: str, password: str, realm: str, random_key: str
    ) -> tuple[str, str]:
        """Assinatura de login (5 transformacoes MD5).

        Retorna (signature, temp4). O temp4 e reutilizado para assinar o
        updateToken: md5(temp4 + ":" + token).
        """
        temp1 = cls.md5_hex(password)
        temp2 = cls.md5_hex(username + temp1)
        temp3 = cls.md5_hex(temp2)
        temp4 = cls.md5_hex(f"{username}:{realm}:{temp3}")
        signature = cls.md5_hex(f"{temp4}:{random_key}")
        return signature, temp4

    # ------------------------------ RSA ----------------------------------- #
    @staticmethod
    def generate_rsa_keypair(bits: int = 2048) -> RSA.RsaKey:
        """Gera um par de chaves RSA (privada PKCS#8, publica X.509)."""
        return RSA.generate(bits)

    @staticmethod
    def public_key_to_base64(key: RSA.RsaKey) -> str:
        """Exporta a chave publica em DER/X.509 e codifica em base64 (p/ HTTP)."""
        return base64.b64encode(key.publickey().export_key(format="DER")).decode()

    @staticmethod
    def decrypt_rsa(b64_ciphertext: str, private_key: RSA.RsaKey) -> str:
        """Decripta um valor RSA PKCS#1 v1.5 retornado em base64 pelo servidor.

        Itera em blocos de 256 bytes (chave de 2048 bits), como o exemplo Java.
        """
        data = base64.b64decode(b64_ciphertext)
        cipher = PKCS1_v1_5.new(private_key)
        sentinel = b""
        out = bytearray()
        for i in range(0, len(data), 256):
            out += cipher.decrypt(data[i:i + 256], sentinel)
        return out.decode("utf-8")

    # ------------------------------ AES ----------------------------------- #
    @staticmethod
    def encrypt_aes(plaintext: str, aes_key: str, aes_vector: str) -> str:
        """AES/CBC/PKCS7 -> hex minusculo (equivalente a encryptWithAES7)."""
        cipher = AES.new(aes_key.encode("utf-8"), AES.MODE_CBC, aes_vector.encode("utf-8"))
        return cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size)).hex()

    @staticmethod
    def decrypt_aes(hex_ciphertext: str, aes_key: str, aes_vector: str) -> str:
        """AES/CBC/PKCS7 a partir de hex -> texto (equivalente a decryptWithAES7)."""
        cipher = AES.new(aes_key.encode("utf-8"), AES.MODE_CBC, aes_vector.encode("utf-8"))
        decrypted = cipher.decrypt(bytes.fromhex(hex_ciphertext))
        return unpad(decrypted, AES.block_size).decode("utf-8")
