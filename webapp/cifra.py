"""Cifra/decifra a senha das conexões externas antes de gravar no banco do
próprio cronovazamento. A chave (CRONOVAZAMENTO_CHAVE_CIFRA) fica só em
variável de ambiente — nunca no banco, nunca no git."""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet

    chave = os.environ.get("CRONOVAZAMENTO_CHAVE_CIFRA")
    if not chave:
        raise RuntimeError(
            "CRONOVAZAMENTO_CHAVE_CIFRA não configurada — gere uma com "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "e coloque no .env"
        )
    return Fernet(chave.encode())


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(texto: str) -> str:
    return _fernet().decrypt(texto.encode()).decode()
