"""Carrega e casa 'eventos' de referência (fatos mutáveis com data conhecida)
contra as linhas de uma amostra vazada, gerando Evidencia.

Um evento de referência é algo como:
  - pessoa nasceu / morreu em D
  - pessoa mudou de nome em D (casamento etc.)
  - empresa alterou quadro societário em D (sócio entrou/saiu, % mudou)
  - veículo mudou de proprietário em D (DETRAN)

Os eventos ficam em JSON, e o usuário fornece um MAPEAMENTO indicando qual
coluna da amostra corresponde a cada campo lógico (cpf, nome, cnpj, socio,
placa, proprietario...), já que cada vazamento nomeia as colunas do seu jeito.

O casamento de nomes (pessoa, sócio, proprietário) roda por um ou mais
algoritmos de proximidade (cronovazamento.proximidade) em vez de exigir
igualdade exata de string — tolera acento, abreviação e erro de digitação.
Um casamento abaixo de QUASE_EXATO vira sempre evidência fraca, mesmo que o
evento declare força "forte", porque é uma identificação aproximada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .evidencias import Direcao, Evidencia, Forca
from .proximidade import obter_string

LIMIAR_PADRAO = 0.85
QUASE_EXATO = 0.97
ALGORITMOS_PADRAO = ["exato"]


def _parse_data(valor: str) -> date:
    return date.fromisoformat(valor)


def _forca(evento: dict[str, Any], padrao: Forca) -> Forca:
    valor = evento.get("forca")
    if valor is None:
        return padrao
    return Forca(valor)


def _melhor_correspondencia(
    valor_amostra: str, algoritmos: list[str]
) -> Callable[[str], tuple[str, float]]:
    """Retorna uma função que, para um valor de referência, dá o (id do
    algoritmo, score) da melhor correspondência entre os algoritmos pedidos."""

    def avaliar(valor_referencia: str) -> tuple[str, float]:
        melhor_id, melhor_score = "exato", 0.0
        for alg_id in algoritmos:
            alg = obter_string(alg_id)
            score = alg.comparar(valor_amostra, valor_referencia)
            if score > melhor_score:
                melhor_id, melhor_score = alg_id, score
        return melhor_id, melhor_score

    return avaliar


def _forca_fuzzy(algoritmo: str, score: float, padrao: Forca) -> Forca:
    if algoritmo == "exato" or score >= QUASE_EXATO:
        return padrao
    return Forca.FRACA


@dataclass
class BaseEventos:
    eventos: list[dict[str, Any]]

    @classmethod
    def carregar(cls, caminho: str | Path) -> "BaseEventos":
        caminho = Path(caminho)
        with caminho.open(encoding="utf-8") as f:
            dados = json.load(f)
        return cls(eventos=dados)

    def por_chave(self, chave: str) -> list[dict[str, Any]]:
        campo_chave = self._campo_chave
        return [e for e in self.eventos if str(e.get(campo_chave)) == str(chave)]


class EventosPessoa(BaseEventos):
    _campo_chave = "cpf"

    def gerar_evidencias(
        self,
        linha: dict[str, str],
        mapeamento: dict[str, str],
        algoritmos: list[str] = ALGORITMOS_PADRAO,
        limiar: float = LIMIAR_PADRAO,
    ) -> list[Evidencia]:
        col_cpf = mapeamento.get("cpf")
        col_nome = mapeamento.get("nome")
        col_status_obito = mapeamento.get("status_obito")  # coluna booleana/flag opcional
        if not col_cpf or col_cpf not in linha:
            return []

        cpf = linha[col_cpf]
        evidencias: list[Evidencia] = []
        for ev in self.por_chave(cpf):
            tipo = ev["tipo"]
            data_ref = _parse_data(ev["data"])
            chave = f"cpf:{cpf}"

            if tipo == "nascimento":
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="nascimento",
                        direcao=Direcao.POS,
                        data_referencia=data_ref,
                        forca=_forca(ev, Forca.FORTE),
                        justificativa=f"CPF {cpf} só existe/nasceu em {data_ref.isoformat()}",
                    )
                )

            elif tipo == "obito":
                marcado_como_falecido = False
                if col_status_obito and col_status_obito in linha:
                    valor = str(linha[col_status_obito]).strip().lower()
                    marcado_como_falecido = valor in {"1", "true", "sim", "s", "falecido", "obito", "óbito"}
                if marcado_como_falecido:
                    evidencias.append(
                        Evidencia(
                            chave=chave,
                            tipo_evento="obito",
                            direcao=Direcao.POS,
                            data_referencia=data_ref,
                            forca=_forca(ev, Forca.FORTE),
                            justificativa=f"CPF {cpf} consta como falecido, óbito em {data_ref.isoformat()}",
                        )
                    )
                else:
                    evidencias.append(
                        Evidencia(
                            chave=chave,
                            tipo_evento="obito",
                            direcao=Direcao.ANTES,
                            data_referencia=data_ref,
                            forca=_forca(ev, Forca.FRACA),
                            justificativa=(
                                f"CPF {cpf} não consta como falecido, mas óbito é de "
                                f"{data_ref.isoformat()} (base pode estar desatualizada)"
                            ),
                        )
                    )

            elif tipo == "mudanca_nome":
                if not col_nome or col_nome not in linha:
                    continue
                nome_amostra = linha[col_nome]
                nome_novo = str(ev.get("nome_novo", ""))
                nome_anterior = str(ev.get("nome_anterior", ""))
                avaliar = _melhor_correspondencia(nome_amostra, algoritmos)

                alg_novo, score_novo = avaliar(nome_novo) if nome_novo else ("exato", 0.0)
                alg_anterior, score_anterior = avaliar(nome_anterior) if nome_anterior else ("exato", 0.0)

                if score_novo >= limiar and score_novo >= score_anterior:
                    forca = _forca_fuzzy(alg_novo, score_novo, _forca(ev, Forca.FORTE))
                    detalhe = "" if alg_novo == "exato" else f" (algoritmo {alg_novo}, score {score_novo:.2f})"
                    evidencias.append(
                        Evidencia(
                            chave=chave,
                            tipo_evento="mudanca_nome",
                            direcao=Direcao.POS,
                            data_referencia=data_ref,
                            forca=forca,
                            justificativa=(
                                f"CPF {cpf} aparece com o nome novo ('{ev.get('nome_novo')}'){detalhe}, "
                                f"mudança ocorreu em {data_ref.isoformat()}"
                            ),
                            algoritmo=None if alg_novo == "exato" else alg_novo,
                            score=None if alg_novo == "exato" else score_novo,
                        )
                    )
                elif score_anterior >= limiar:
                    forca = _forca_fuzzy(alg_anterior, score_anterior, Forca.FRACA)
                    detalhe = "" if alg_anterior == "exato" else f" (algoritmo {alg_anterior}, score {score_anterior:.2f})"
                    evidencias.append(
                        Evidencia(
                            chave=chave,
                            tipo_evento="mudanca_nome",
                            direcao=Direcao.ANTES,
                            data_referencia=data_ref,
                            forca=forca,
                            justificativa=(
                                f"CPF {cpf} ainda aparece com o nome anterior "
                                f"('{ev.get('nome_anterior')}'){detalhe}, mudança seria em "
                                f"{data_ref.isoformat()} (nome antigo pode persistir por atraso cadastral)"
                            ),
                            algoritmo=None if alg_anterior == "exato" else alg_anterior,
                            score=None if alg_anterior == "exato" else score_anterior,
                        )
                    )

        return evidencias


class EventosEmpresa(BaseEventos):
    _campo_chave = "cnpj"

    def gerar_evidencias(
        self,
        linha: dict[str, str],
        mapeamento: dict[str, str],
        algoritmos: list[str] = ALGORITMOS_PADRAO,
        limiar: float = LIMIAR_PADRAO,
    ) -> list[Evidencia]:
        col_cnpj = mapeamento.get("cnpj")
        col_socio = mapeamento.get("socio")
        col_participacao = mapeamento.get("participacao")
        if not col_cnpj or col_cnpj not in linha:
            return []

        cnpj = linha[col_cnpj]
        evidencias: list[Evidencia] = []
        for ev in self.por_chave(cnpj):
            if ev["tipo"] != "alteracao_societaria":
                continue
            data_ref = _parse_data(ev["data"])
            chave = f"cnpj:{cnpj}"
            socio = str(ev.get("socio", ""))
            situacao_nova = ev.get("situacao_nova")  # "presente" | "ausente"

            if not col_socio:
                continue

            valor_amostra = str(linha.get(col_socio, ""))
            alg_socio, score_socio = _melhor_correspondencia(valor_amostra, algoritmos)(socio) if socio else ("exato", 0.0)
            socio_na_amostra = score_socio >= limiar
            detalhe = "" if alg_socio == "exato" or not socio_na_amostra else f" (algoritmo {alg_socio}, score {score_socio:.2f})"

            if situacao_nova == "presente" and socio_na_amostra:
                just = f"Sócio '{socio}' entrou no quadro de {cnpj} em {data_ref.isoformat()} e já consta na amostra{detalhe}"
                if col_participacao and ev.get("participacao_nova") is not None:
                    just += f" (participação {ev['participacao_nova']}%)"
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="alteracao_societaria",
                        direcao=Direcao.POS,
                        data_referencia=data_ref,
                        forca=_forca_fuzzy(alg_socio, score_socio, _forca(ev, Forca.FORTE)),
                        justificativa=just,
                        algoritmo=None if alg_socio == "exato" else alg_socio,
                        score=None if alg_socio == "exato" else score_socio,
                    )
                )
            elif situacao_nova == "ausente" and not socio_na_amostra:
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="alteracao_societaria",
                        direcao=Direcao.POS,
                        data_referencia=data_ref,
                        forca=_forca(ev, Forca.FRACA),
                        justificativa=(
                            f"Sócio '{socio}' saiu do quadro de {cnpj} em {data_ref.isoformat()} "
                            "e não consta na amostra (Junta Comercial pode ter atraso de registro)"
                        ),
                    )
                )
            elif situacao_nova == "presente" and not socio_na_amostra:
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="alteracao_societaria",
                        direcao=Direcao.ANTES,
                        data_referencia=data_ref,
                        forca=_forca(ev, Forca.FRACA),
                        justificativa=(
                            f"Sócio '{socio}' entraria no quadro de {cnpj} em {data_ref.isoformat()} "
                            "mas não consta na amostra"
                        ),
                    )
                )

        return evidencias


class EventosVeiculo(BaseEventos):
    _campo_chave = "placa"

    def gerar_evidencias(
        self,
        linha: dict[str, str],
        mapeamento: dict[str, str],
        algoritmos: list[str] = ALGORITMOS_PADRAO,
        limiar: float = LIMIAR_PADRAO,
    ) -> list[Evidencia]:
        col_placa = mapeamento.get("placa")
        col_proprietario = mapeamento.get("proprietario")
        if not col_placa or col_placa not in linha:
            return []

        placa = linha[col_placa]
        evidencias: list[Evidencia] = []
        for ev in self.por_chave(placa):
            if ev["tipo"] != "transferencia_propriedade":
                continue
            if not col_proprietario:
                continue
            data_ref = _parse_data(ev["data"])
            chave = f"placa:{placa}"
            valor_amostra = str(linha.get(col_proprietario, ""))
            novo = str(ev.get("proprietario_novo", ""))
            anterior = str(ev.get("proprietario_anterior", ""))
            avaliar = _melhor_correspondencia(valor_amostra, algoritmos)

            alg_novo, score_novo = avaliar(novo) if novo else ("exato", 0.0)
            alg_anterior, score_anterior = avaliar(anterior) if anterior else ("exato", 0.0)

            if score_novo >= limiar and score_novo >= score_anterior:
                detalhe = "" if alg_novo == "exato" else f" (algoritmo {alg_novo}, score {score_novo:.2f})"
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="transferencia_veiculo",
                        direcao=Direcao.POS,
                        data_referencia=data_ref,
                        forca=_forca_fuzzy(alg_novo, score_novo, _forca(ev, Forca.FORTE)),
                        justificativa=(
                            f"Placa {placa} já consta com o novo proprietário{detalhe}, "
                            f"transferência em {data_ref.isoformat()}"
                        ),
                        algoritmo=None if alg_novo == "exato" else alg_novo,
                        score=None if alg_novo == "exato" else score_novo,
                    )
                )
            elif score_anterior >= limiar:
                detalhe = "" if alg_anterior == "exato" else f" (algoritmo {alg_anterior}, score {score_anterior:.2f})"
                evidencias.append(
                    Evidencia(
                        chave=chave,
                        tipo_evento="transferencia_veiculo",
                        direcao=Direcao.ANTES,
                        data_referencia=data_ref,
                        forca=_forca_fuzzy(alg_anterior, score_anterior, Forca.FRACA),
                        justificativa=(
                            f"Placa {placa} ainda consta com o proprietário anterior{detalhe}, "
                            f"transferência seria em {data_ref.isoformat()} "
                            "(DETRAN pode ter atraso de averbação)"
                        ),
                        algoritmo=None if alg_anterior == "exato" else alg_anterior,
                        score=None if alg_anterior == "exato" else score_anterior,
                    )
                )

        return evidencias
