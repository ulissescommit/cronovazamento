"""Registro de algoritmos de proximidade estatística, usados em dois pontos
do motor:

  - comparação de SCHEMA (conjunto de colunas da amostra x conjunto de
    colunas de cada entrada do catálogo), para estimar a origem;
  - comparação de STRING (nome de pessoa/sócio/proprietário na amostra x
    valor conhecido num evento de referência), para casar registros de forma
    tolerante a variação de acento, abreviação e erro de digitação.

Cada algoritmo é uma função pura, registrada por id, para que a UI e o CLI
possam listar as opções disponíveis e o usuário escolher quais rodar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable

from .schema import normalizar_nome, similaridade_dice, similaridade_jaccard


# ---------------------------------------------------------------------------
# Algoritmos sobre CONJUNTOS (fingerprint de schema)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlgoritmoConjunto:
    id: str
    nome: str
    descricao: str
    funcao: Callable[[frozenset[str], frozenset[str], "Iterable[frozenset[str]] | None"], float]

    def comparar(
        self,
        a: frozenset[str],
        b: frozenset[str],
        corpus: Iterable[frozenset[str]] | None = None,
    ) -> float:
        return self.funcao(a, b, corpus)


def _jaccard(a: frozenset[str], b: frozenset[str], _corpus=None) -> float:
    return similaridade_jaccard(a, b)


def _dice(a: frozenset[str], b: frozenset[str], _corpus=None) -> float:
    return similaridade_dice(a, b)


def _cosseno_tfidf(a: frozenset[str], b: frozenset[str], corpus: Iterable[frozenset[str]] | None) -> float:
    """Similaridade de cosseno sobre vetores binários ponderados por IDF: um
    campo raro no catálogo (aparece em poucas entradas) pesa mais que um
    campo comum como 'nome' ou 'email' — mais informativo para apontar
    origem do que Jaccard puro, que trata todo campo com o mesmo peso."""
    corpus = list(corpus) if corpus else []
    campos = a | b
    if not campos:
        return 0.0

    n_docs = max(len(corpus), 1)
    idf: dict[str, float] = {}
    for campo in campos:
        df = sum(1 for doc in corpus if campo in doc) if corpus else 0
        # +1 de suavização (evita divisão por zero / idf infinito para campo inédito)
        idf[campo] = math.log((n_docs + 1) / (df + 1)) + 1.0

    produto_escalar = sum(idf[c] ** 2 for c in (a & b))
    norma_a = math.sqrt(sum(idf[c] ** 2 for c in a)) or 1.0
    norma_b = math.sqrt(sum(idf[c] ** 2 for c in b)) or 1.0
    return produto_escalar / (norma_a * norma_b)


ALGORITMOS_CONJUNTO: dict[str, AlgoritmoConjunto] = {
    a.id: a
    for a in [
        AlgoritmoConjunto(
            id="jaccard",
            nome="Jaccard",
            descricao="Interseção sobre união dos campos. Simples, trata todo campo com o mesmo peso.",
            funcao=_jaccard,
        ),
        AlgoritmoConjunto(
            id="dice",
            nome="Dice (Sørensen–Dice)",
            descricao="Parecido com Jaccard, mas dá peso maior à interseção — mais tolerante a diferença de tamanho entre os conjuntos.",
            funcao=_dice,
        ),
        AlgoritmoConjunto(
            id="cosseno_tfidf",
            nome="Cosseno (TF-IDF)",
            descricao="Pesa mais campos raros no catálogo do que campos comuns (nome, email). Precisa do catálogo inteiro como corpus para calcular o peso.",
            funcao=_cosseno_tfidf,
        ),
    ]
}


# ---------------------------------------------------------------------------
# Algoritmos sobre STRINGS (casamento fuzzy de registro)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlgoritmoString:
    id: str
    nome: str
    descricao: str
    funcao: Callable[[str, str], float]

    def comparar(self, a: str, b: str) -> float:
        return self.funcao(normalizar_nome(a), normalizar_nome(b))


def _exato(a: str, b: str) -> float:
    return 1.0 if a == b and a != "" else 0.0


def _levenshtein_distancia(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            custo = 0 if ca == cb else 1
            atual[j] = min(
                anterior[j] + 1,  # remoção
                atual[j - 1] + 1,  # inserção
                anterior[j - 1] + custo,  # substituição
            )
        anterior = atual
    return anterior[-1]


def _levenshtein(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    dist = _levenshtein_distancia(a, b)
    maior = max(len(a), len(b))
    return 1.0 - (dist / maior) if maior else 1.0


def _jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0

    janela = max(len_a, len_b) // 2 - 1
    janela = max(janela, 0)

    a_casado = [False] * len_a
    b_casado = [False] * len_b

    correspondencias = 0
    for i, ca in enumerate(a):
        inicio = max(0, i - janela)
        fim = min(i + janela + 1, len_b)
        for j in range(inicio, fim):
            if b_casado[j] or a[i] != b[j]:
                continue
            a_casado[i] = True
            b_casado[j] = True
            correspondencias += 1
            break

    if correspondencias == 0:
        return 0.0

    transposicoes = 0
    k = 0
    for i in range(len_a):
        if not a_casado[i]:
            continue
        while not b_casado[k]:
            k += 1
        if a[i] != b[k]:
            transposicoes += 1
        k += 1
    transposicoes //= 2

    m = correspondencias
    return (m / len_a + m / len_b + (m - transposicoes) / m) / 3.0


def _jaro_winkler(a: str, b: str, prefixo_max: int = 4, fator_prefixo: float = 0.1) -> float:
    jaro = _jaro(a, b)
    prefixo = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        prefixo += 1
        if prefixo == prefixo_max:
            break
    return jaro + prefixo * fator_prefixo * (1 - jaro)


_SUBSTITUICOES_FONETICAS = [
    ("ph", "f"),
    ("th", "t"),
    ("ch", "x"),
    ("sh", "x"),
    ("qu", "k"),
    ("ss", "s"),
    ("sc", "s"),
    ("ç", "s"),
    ("z", "s"),
    ("y", "i"),
    ("w", "v"),
    ("h", ""),
]


def _chave_fonetica(valor: str) -> str:
    """Chave fonética simplificada (aproximação de Soundex adaptada a
    padrões comuns de nomes em português). Não é um algoritmo linguístico
    rigoroso — serve para agrupar variações de grafia foneticamente
    equivalentes (ex.: 'Felipe'/'Philippe', 'Souza'/'Souza')."""
    v = valor
    for origem, destino in _SUBSTITUICOES_FONETICAS:
        v = v.replace(origem, destino)
    # colapsa letras repetidas (ex.: "carro" -> "caro")
    resultado = []
    anterior = None
    for c in v:
        if c == anterior:
            continue
        if c.isalpha() or c.isdigit():
            resultado.append(c)
        anterior = c
    return "".join(resultado)


def _fonetico(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    chave_a, chave_b = _chave_fonetica(a), _chave_fonetica(b)
    if chave_a == chave_b and chave_a != "":
        return 1.0
    # sem casamento exato de chave: ainda dá um score parcial via Levenshtein
    # sobre as chaves, mas nunca alto o bastante pra passar num limiar normal
    return _levenshtein(chave_a, chave_b) * 0.6


ALGORITMOS_STRING: dict[str, AlgoritmoString] = {
    a.id: a
    for a in [
        AlgoritmoString(
            id="exato",
            nome="Igualdade exata",
            descricao="1.0 se as strings normalizadas forem idênticas, 0.0 caso contrário.",
            funcao=_exato,
        ),
        AlgoritmoString(
            id="levenshtein",
            nome="Levenshtein (razão de edição)",
            descricao="Baseado no número mínimo de inserções/remoções/substituições para transformar uma string na outra.",
            funcao=_levenshtein,
        ),
        AlgoritmoString(
            id="jaro_winkler",
            nome="Jaro-Winkler",
            descricao="Dá peso extra a prefixos em comum. Bom para nomes curtos com pequenas variações no fim.",
            funcao=_jaro_winkler,
        ),
        AlgoritmoString(
            id="fonetico",
            nome="Fonético (aproximado)",
            descricao="Agrupa por chave fonética simplificada — útil para grafias diferentes do mesmo som (ex.: Felipe/Philippe).",
            funcao=_fonetico,
        ),
    ]
}


def listar_algoritmos_conjunto() -> list[AlgoritmoConjunto]:
    return list(ALGORITMOS_CONJUNTO.values())


def listar_algoritmos_string() -> list[AlgoritmoString]:
    return list(ALGORITMOS_STRING.values())


def obter_conjunto(id_algoritmo: str) -> AlgoritmoConjunto:
    try:
        return ALGORITMOS_CONJUNTO[id_algoritmo]
    except KeyError:
        raise ValueError(f"Algoritmo de conjunto desconhecido: '{id_algoritmo}'") from None


def obter_string(id_algoritmo: str) -> AlgoritmoString:
    try:
        return ALGORITMOS_STRING[id_algoritmo]
    except KeyError:
        raise ValueError(f"Algoritmo de string desconhecido: '{id_algoritmo}'") from None
