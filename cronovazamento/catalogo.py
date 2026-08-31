"""Catálogo de vazamentos/bases conhecidas: cada entrada guarda a assinatura
de campos de um vazamento já identificado (ou de uma base de origem, ex.
'cadastro de cliente da Empresa X'). Comparar uma amostra desconhecida contra
esse catálogo ajuda a estimar a origem, mesmo sem nenhum dado em comum além
dos NOMES e FORMATOS das colunas.

O ranking pode rodar mais de um algoritmo de proximidade (cronovazamento.
proximidade) ao mesmo tempo — cada candidato carrega um score por algoritmo,
para o usuário comparar em vez de confiar numa única métrica combinada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .proximidade import ALGORITMOS_CONJUNTO, obter_conjunto
from .schema import assinatura


@dataclass
class VazamentoConhecido:
    id: str
    nome: str
    campos: list[str]
    fonte_suspeita: str | None = None
    data_conhecida: str | None = None
    observacoes: str | None = None

    @property
    def assinatura(self) -> frozenset[str]:
        return assinatura(self.campos)


@dataclass
class CandidatoOrigem:
    entrada: VazamentoConhecido
    scores: dict[str, float]  # id do algoritmo -> score
    exclusivos_amostra: frozenset[str]
    ausentes_no_candidato: frozenset[str]

    @property
    def score_medio(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


@dataclass
class Catalogo:
    entradas: list[VazamentoConhecido] = field(default_factory=list)

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Catalogo":
        caminho = Path(caminho)
        if not caminho.exists():
            return cls()
        with caminho.open(encoding="utf-8") as f:
            dados = json.load(f)
        entradas = [VazamentoConhecido(**item) for item in dados]
        return cls(entradas=entradas)

    def salvar(self, caminho: str | Path) -> None:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = [
            {
                "id": e.id,
                "nome": e.nome,
                "campos": e.campos,
                "fonte_suspeita": e.fonte_suspeita,
                "data_conhecida": e.data_conhecida,
                "observacoes": e.observacoes,
            }
            for e in self.entradas
        ]
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    def adicionar(self, entrada: VazamentoConhecido) -> None:
        self.entradas.append(entrada)

    def identificar_origem(
        self,
        campos_amostra: list[str],
        algoritmos: list[str] | None = None,
        top_n: int = 5,
    ) -> list[CandidatoOrigem]:
        """Retorna as entradas do catálogo mais parecidas com a amostra,
        rankeadas pela média dos scores dos algoritmos pedidos (padrão:
        todos os algoritmos de conjunto registrados). Cada resultado traz o
        score de CADA algoritmo separadamente, além dos campos EXCLUSIVOS da
        amostra e dos campos do candidato AUSENTES na amostra.
        """
        algoritmos = algoritmos or list(ALGORITMOS_CONJUNTO.keys())
        assinatura_amostra = assinatura(campos_amostra)
        corpus = [e.assinatura for e in self.entradas]

        candidatos: list[CandidatoOrigem] = []
        for entrada in self.entradas:
            scores = {
                alg_id: obter_conjunto(alg_id).comparar(assinatura_amostra, entrada.assinatura, corpus)
                for alg_id in algoritmos
            }
            candidatos.append(
                CandidatoOrigem(
                    entrada=entrada,
                    scores=scores,
                    exclusivos_amostra=assinatura_amostra - entrada.assinatura,
                    ausentes_no_candidato=entrada.assinatura - assinatura_amostra,
                )
            )

        candidatos.sort(key=lambda c: c.score_medio, reverse=True)
        return candidatos[:top_n]


def campos_exclusivos_globais(campos_amostra: list[str], catalogo: Catalogo) -> frozenset[str]:
    """Campos da amostra que não aparecem em NENHUMA entrada do catálogo —
    fortes candidatos a 'assinatura própria' da base de origem (nomes de
    coluna incomuns, específicos de um sistema)."""
    assinatura_amostra = assinatura(campos_amostra)
    conhecidos: set[str] = set()
    for entrada in catalogo.entradas:
        conhecidos |= entrada.assinatura
    return assinatura_amostra - conhecidos
