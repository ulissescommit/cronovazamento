"""Fingerprinting de schema: usado para estimar DE ONDE um vazamento veio,
comparando o conjunto de campos (colunas) da amostra contra um catálogo de
vazamentos/bases conhecidas.
"""

from __future__ import annotations

import re
import unicodedata


def normalizar_campo(nome: str) -> str:
    """Normaliza um nome de coluna para comparação: minúsculas, sem acento,
    sem separadores, para que 'Data Nascimento', 'data_nascimento' e
    'DT_NASC' tendam a convergir quando fizer sentido (convergência exata só
    ocorre para variações de caixa/separador, não sinônimos)."""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = nome.strip().lower()
    nome = re.sub(r"[\s\-]+", "_", nome)
    nome = re.sub(r"[^a-z0-9_]", "", nome)
    return nome


def assinatura(colunas: list[str]) -> frozenset[str]:
    return frozenset(normalizar_campo(c) for c in colunas if c.strip())


def normalizar_nome(valor: str) -> str:
    """Normaliza um nome de pessoa/sócio/proprietário para comparação fuzzy:
    minúsculas, sem acento, espaços colapsados. Mantém espaços (diferente de
    normalizar_campo) porque aqui comparamos strings inteiras, não tokens."""
    valor = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    valor = valor.strip().lower()
    valor = re.sub(r"[^a-z0-9\s]", "", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor


def similaridade_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    uniao = len(a | b)
    return inter / uniao if uniao else 0.0


def similaridade_dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    soma = len(a) + len(b)
    return (2 * inter) / soma if soma else 0.0
