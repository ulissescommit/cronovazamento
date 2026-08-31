"""Compara os registros de uma amostra contra linhas já buscadas de um banco
candidato (ver cronovazamento.conectores) para responder "esse vazamento
veio dessa base?" — usando os mesmos algoritmos de proximidade do resto do
motor pra tolerar diferença de formatação entre a amostra e o banco vivo.

Esse módulo não conecta em nada: recebe `linhas_externas` já buscadas
(dict chave -> linha), então é testável sem precisar de um banco de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .proximidade import obter_string

LIMIAR_PADRAO = 0.85


@dataclass(frozen=True)
class ComparacaoCampo:
    campo: str
    valor_amostra: str
    valor_externo: str
    algoritmo: str
    score: float
    limiar: float = LIMIAR_PADRAO

    @property
    def diverge(self) -> bool:
        return self.score < self.limiar


@dataclass
class RegistroVerificado:
    chave: str
    encontrado: bool
    campos: list[ComparacaoCampo] = field(default_factory=list)

    @property
    def tem_divergencia(self) -> bool:
        return any(c.diverge for c in self.campos)


@dataclass
class ResultadoVerificacao:
    registros: list[RegistroVerificado]

    @property
    def total(self) -> int:
        return len(self.registros)

    @property
    def encontrados(self) -> int:
        return sum(1 for r in self.registros if r.encontrado)

    @property
    def divergentes(self) -> int:
        return sum(1 for r in self.registros if r.encontrado and r.tem_divergencia)

    @property
    def percentual_encontrado(self) -> float:
        return (self.encontrados / self.total * 100) if self.total else 0.0

    @property
    def percentual_divergente(self) -> float:
        return (self.divergentes / self.encontrados * 100) if self.encontrados else 0.0


def _melhor_score(valor_a: str, valor_b: str, algoritmos: list[str]) -> tuple[str, float]:
    melhor_id, melhor_score = "exato", 0.0
    for alg_id in algoritmos:
        score = obter_string(alg_id).comparar(valor_a, valor_b)
        if score > melhor_score:
            melhor_id, melhor_score = alg_id, score
    return melhor_id, melhor_score


def verificar(
    linhas_amostra: list[dict[str, str]],
    mapeamento_amostra: dict[str, str],
    linhas_externas: dict[str, dict],
    mapeamento_externo: dict[str, str],
    campo_chave: str,
    algoritmos_string: list[str] | None = None,
    limiar: float = LIMIAR_PADRAO,
) -> ResultadoVerificacao:
    algoritmos_string = algoritmos_string or ["exato"]
    col_chave_amostra = mapeamento_amostra.get(campo_chave)
    if not col_chave_amostra:
        raise ValueError(f"Amostra não tem coluna mapeada para o campo-chave '{campo_chave}'")

    campos_a_comparar = [
        campo
        for campo in mapeamento_amostra
        if campo != campo_chave and campo in mapeamento_externo and mapeamento_amostra.get(campo)
    ]

    registros: list[RegistroVerificado] = []
    for linha in linhas_amostra:
        valor_chave = str(linha.get(col_chave_amostra, "")).strip()
        if not valor_chave:
            continue

        linha_externa = linhas_externas.get(valor_chave)
        if linha_externa is None:
            registros.append(RegistroVerificado(chave=valor_chave, encontrado=False))
            continue

        comparacoes = []
        for campo in campos_a_comparar:
            valor_amostra = str(linha.get(mapeamento_amostra[campo], ""))
            valor_externo = str(linha_externa.get(mapeamento_externo[campo], ""))
            if not valor_amostra and not valor_externo:
                continue
            algoritmo, score = _melhor_score(valor_amostra, valor_externo, algoritmos_string)
            comparacoes.append(
                ComparacaoCampo(
                    campo=campo,
                    valor_amostra=valor_amostra,
                    valor_externo=valor_externo,
                    algoritmo=algoritmo,
                    score=score,
                    limiar=limiar,
                )
            )
        registros.append(RegistroVerificado(chave=valor_chave, encontrado=True, campos=comparacoes))

    return ResultadoVerificacao(registros=registros)
