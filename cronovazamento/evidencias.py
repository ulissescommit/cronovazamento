"""Motor de estimativa temporal.

A ideia central: uma tabela de referência (população, empresas, DETRAN...)
registra FATOS MUTÁVEIS com data conhecida (nascimento, casamento/mudança de
nome, alteração de quadro societário, transferência de propriedade de
veículo...). Se uma amostra vazada reflete o estado ANTES ou DEPOIS de um
desses fatos, isso vira um limite (">=" ou "<=") para a data do vazamento.

Cruzando várias evidências, a interseção dos limites dá a janela estimada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Direcao(str, Enum):
    POS = ">="  # o vazamento ocorreu em ou depois desta data
    ANTES = "<="  # o vazamento ocorreu em ou antes desta data


class Forca(str, Enum):
    FORTE = "forte"  # fato praticamente imutável / atualização é imediata (ex.: nascimento)
    FRACA = "fraca"  # fato sujeito a defasagem de atualização cadastral (ex.: nome de casada
    # pode não propagar por anos em bases antigas; posse de veículo pode demorar a
    # ser averbada)


@dataclass(frozen=True)
class Evidencia:
    chave: str  # identificador do registro na amostra, ex. "cpf:12345678900"
    tipo_evento: str  # "nascimento" | "obito" | "mudanca_nome" | "alteracao_societaria" | "transferencia_veiculo"
    direcao: Direcao
    data_referencia: date
    forca: Forca
    justificativa: str
    # preenchidos quando o casamento do registro veio de um algoritmo de
    # proximidade fuzzy (não de igualdade exata de string)
    algoritmo: str | None = None
    score: float | None = None


@dataclass
class Conflito:
    inferior: Evidencia
    superior: Evidencia

    def __str__(self) -> str:  # pragma: no cover - texto de apoio
        return (
            f"Conflito: '{self.inferior.justificativa}' exige vazamento >= "
            f"{self.inferior.data_referencia}, mas '{self.superior.justificativa}' "
            f"exige vazamento <= {self.superior.data_referencia}."
        )


@dataclass
class ResultadoJanela:
    limite_inferior: date | None = None
    evidencia_inferior: Evidencia | None = None
    limite_superior: date | None = None
    evidencia_superior: Evidencia | None = None
    evidencias_fracas: list[Evidencia] = field(default_factory=list)
    conflitos: list[Conflito] = field(default_factory=list)

    @property
    def consistente(self) -> bool:
        return not self.conflitos

    @property
    def dias_de_janela(self) -> int | None:
        if self.limite_inferior and self.limite_superior:
            return (self.limite_superior - self.limite_inferior).days
        return None

    def resumo(self) -> str:
        partes = []
        if self.limite_inferior:
            partes.append(f">= {self.limite_inferior.isoformat()} ({self.evidencia_inferior.justificativa})")
        if self.limite_superior:
            partes.append(f"<= {self.limite_superior.isoformat()} ({self.evidencia_superior.justificativa})")
        if not partes:
            partes.append("sem evidências fortes suficientes para delimitar janela")
        if self.evidencias_fracas:
            partes.append(f"+{len(self.evidencias_fracas)} evidência(s) fraca(s) de apoio")
        if not self.consistente:
            partes.append(f"!! {len(self.conflitos)} conflito(s) detectado(s)")
        return " | ".join(partes)


def estimar_janela(evidencias: list[Evidencia]) -> ResultadoJanela:
    """Intersecta as evidências fortes para achar a janela mais estreita possível.

    Evidências fracas não apertam a janela (podem estar defasadas por atraso
    cadastral), mas ficam registradas como apoio/alerta.
    """
    resultado = ResultadoJanela()

    for ev in evidencias:
        if ev.forca is Forca.FRACA:
            resultado.evidencias_fracas.append(ev)
            continue

        if ev.direcao is Direcao.POS:
            if resultado.limite_inferior is None or ev.data_referencia > resultado.limite_inferior:
                resultado.limite_inferior = ev.data_referencia
                resultado.evidencia_inferior = ev
        else:
            if resultado.limite_superior is None or ev.data_referencia < resultado.limite_superior:
                resultado.limite_superior = ev.data_referencia
                resultado.evidencia_superior = ev

    if (
        resultado.limite_inferior
        and resultado.limite_superior
        and resultado.limite_inferior > resultado.limite_superior
    ):
        resultado.conflitos.append(
            Conflito(inferior=resultado.evidencia_inferior, superior=resultado.evidencia_superior)
        )

    return resultado
