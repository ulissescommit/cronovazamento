"""Orquestra a análise de uma amostra: lê o CSV, cruza cada linha contra as
bases de eventos de referência (pessoa/empresa/veículo) e agrega tudo numa
janela temporal estimada, além de rodar o fingerprinting de origem contra o
catálogo de vazamentos conhecidos — usando os algoritmos de proximidade
escolhidos pelo usuário em cada uma das duas etapas.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .catalogo import Catalogo, CandidatoOrigem, campos_exclusivos_globais
from .eventos import ALGORITMOS_PADRAO, LIMIAR_PADRAO, EventosEmpresa, EventosPessoa, EventosVeiculo
from .evidencias import Evidencia, ResultadoJanela, estimar_janela
from .proximidade import ALGORITMOS_CONJUNTO


@dataclass
class Amostra:
    caminho: Path
    colunas: list[str]
    linhas: list[dict[str, str]]

    @classmethod
    def carregar_csv(cls, caminho: str | Path, delimitador: str = ",") -> "Amostra":
        caminho = Path(caminho)
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            leitor = csv.DictReader(f, delimiter=delimitador)
            colunas = leitor.fieldnames or []
            linhas = [dict(row) for row in leitor]
        return cls(caminho=caminho, colunas=colunas, linhas=linhas)


@dataclass
class RelatorioOrigem:
    candidatos: list[CandidatoOrigem]
    campos_exclusivos: frozenset[str]
    algoritmos: list[str]


@dataclass
class Relatorio:
    amostra: str
    n_linhas: int
    janela: ResultadoJanela
    evidencias: list[Evidencia]
    origem: RelatorioOrigem | None

    def texto(self) -> str:
        linhas = []
        linhas.append(f"Amostra: {self.amostra} ({self.n_linhas} linhas)")
        linhas.append("")
        linhas.append("== Janela temporal estimada ==")
        linhas.append(self.janela.resumo())
        if self.janela.dias_de_janela is not None:
            linhas.append(f"Largura da janela: {self.janela.dias_de_janela} dia(s)")
        if not self.janela.consistente:
            linhas.append("")
            linhas.append("Conflitos:")
            for c in self.janela.conflitos:
                linhas.append(f"  - {c}")

        linhas.append("")
        linhas.append(f"Evidências fortes usadas: {sum(1 for e in self.evidencias if e.forca.value == 'forte')}")
        linhas.append(f"Evidências fracas (apoio): {len(self.janela.evidencias_fracas)}")
        fuzzy = [e for e in self.evidencias if e.algoritmo]
        if fuzzy:
            linhas.append(f"Evidências via casamento fuzzy: {len(fuzzy)}")

        if self.origem is not None:
            linhas.append("")
            linhas.append(f"== Origem provável (algoritmos: {', '.join(self.origem.algoritmos)}) ==")
            for c in self.origem.candidatos:
                scores_txt = "  ".join(f"{alg}={score:.0%}" for alg, score in c.scores.items())
                linhas.append(f"  {c.score_medio:.0%} média  [{scores_txt}]  {c.entrada.nome} (id={c.entrada.id})")
                if c.entrada.fonte_suspeita:
                    linhas.append(f"        fonte suspeita: {c.entrada.fonte_suspeita}")
            if self.origem.campos_exclusivos:
                linhas.append("")
                linhas.append(
                    "Campos da amostra sem paralelo em nenhum vazamento catalogado "
                    "(possível assinatura própria do sistema de origem):"
                )
                linhas.append("  " + ", ".join(sorted(self.origem.campos_exclusivos)))

        return "\n".join(linhas)


def analisar(
    amostra: Amostra,
    mapeamento: dict[str, str],
    eventos_pessoa: EventosPessoa | None = None,
    eventos_empresa: EventosEmpresa | None = None,
    eventos_veiculo: EventosVeiculo | None = None,
    catalogo: Catalogo | None = None,
    algoritmos_registro: list[str] = ALGORITMOS_PADRAO,
    algoritmos_origem: list[str] | None = None,
    limiar_fuzzy: float = LIMIAR_PADRAO,
) -> Relatorio:
    todas_evidencias: list[Evidencia] = []

    for linha in amostra.linhas:
        if eventos_pessoa is not None:
            todas_evidencias.extend(
                eventos_pessoa.gerar_evidencias(linha, mapeamento, algoritmos_registro, limiar_fuzzy)
            )
        if eventos_empresa is not None:
            todas_evidencias.extend(
                eventos_empresa.gerar_evidencias(linha, mapeamento, algoritmos_registro, limiar_fuzzy)
            )
        if eventos_veiculo is not None:
            todas_evidencias.extend(
                eventos_veiculo.gerar_evidencias(linha, mapeamento, algoritmos_registro, limiar_fuzzy)
            )

    janela = estimar_janela(todas_evidencias)

    origem = None
    if catalogo is not None:
        algoritmos_origem_resolvidos = algoritmos_origem or list(ALGORITMOS_CONJUNTO.keys())
        candidatos = catalogo.identificar_origem(amostra.colunas, algoritmos=algoritmos_origem_resolvidos)
        exclusivos = campos_exclusivos_globais(amostra.colunas, catalogo)
        origem = RelatorioOrigem(
            candidatos=candidatos, campos_exclusivos=exclusivos, algoritmos=algoritmos_origem_resolvidos
        )

    return Relatorio(
        amostra=str(amostra.caminho),
        n_linhas=len(amostra.linhas),
        janela=janela,
        evidencias=todas_evidencias,
        origem=origem,
    )
