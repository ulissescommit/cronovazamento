"""Converte entre as tabelas do banco e os objetos que o motor puro
(cronovazamento/) já sabe processar — o motor continua sem saber que existe
um banco por trás; só recebe EventosPessoa/EventosEmpresa/EventosVeiculo/
Catalogo/Amostra do jeito que já esperava vindo de JSON/CSV.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from cronovazamento.catalogo import Catalogo, VazamentoConhecido
from cronovazamento.comparador import Amostra as AmostraMotor
from cronovazamento.comparador import Relatorio
from cronovazamento.eventos import EventosEmpresa, EventosPessoa, EventosVeiculo

from . import models


def carregar_eventos_pessoa(sessao: Session) -> EventosPessoa:
    linhas = sessao.query(models.EventoPessoa).all()
    eventos = [
        {
            "cpf": e.cpf,
            "tipo": e.tipo,
            "data": e.data.isoformat(),
            "nome_anterior": e.nome_anterior,
            "nome_novo": e.nome_novo,
            **({"forca": e.forca} if e.forca else {}),
        }
        for e in linhas
    ]
    return EventosPessoa(eventos=eventos)


def carregar_eventos_empresa(sessao: Session) -> EventosEmpresa:
    linhas = sessao.query(models.EventoEmpresa).all()
    eventos = [
        {
            "cnpj": e.cnpj,
            "tipo": e.tipo,
            "data": e.data.isoformat(),
            "socio": e.socio,
            "situacao_nova": e.situacao_nova,
            "participacao_nova": e.participacao_nova,
            **({"forca": e.forca} if e.forca else {}),
        }
        for e in linhas
    ]
    return EventosEmpresa(eventos=eventos)


def carregar_eventos_veiculo(sessao: Session) -> EventosVeiculo:
    linhas = sessao.query(models.EventoVeiculo).all()
    eventos = [
        {
            "placa": e.placa,
            "tipo": e.tipo,
            "data": e.data.isoformat(),
            "proprietario_anterior": e.proprietario_anterior,
            "proprietario_novo": e.proprietario_novo,
            **({"forca": e.forca} if e.forca else {}),
        }
        for e in linhas
    ]
    return EventosVeiculo(eventos=eventos)


def carregar_catalogo(sessao: Session) -> Catalogo:
    linhas = sessao.query(models.VazamentoCatalogo).all()
    entradas = [
        VazamentoConhecido(
            id=v.identificador,
            nome=v.nome,
            campos=v.campos,
            fonte_suspeita=v.fonte_suspeita,
            data_conhecida=v.data_conhecida,
            observacoes=v.observacoes,
        )
        for v in linhas
    ]
    return Catalogo(entradas=entradas)


def carregar_amostra(sessao: Session, amostra_id: int) -> AmostraMotor:
    amostra_db = sessao.get(models.Amostra, amostra_id)
    if amostra_db is None:
        raise ValueError(f"Amostra {amostra_id} não encontrada")
    linhas_db = (
        sessao.query(models.AmostraLinha)
        .filter(models.AmostraLinha.amostra_id == amostra_id)
        .order_by(models.AmostraLinha.indice)
        .all()
    )
    return AmostraMotor(
        caminho=Path(amostra_db.arquivo_original),
        colunas=list(amostra_db.colunas),
        linhas=[linha.dados for linha in linhas_db],
    )


def carregar_mapeamento(sessao: Session, amostra_id: int) -> dict[str, str]:
    linhas = sessao.query(models.Mapeamento).filter(models.Mapeamento.amostra_id == amostra_id).all()
    return {m.campo_logico: m.coluna for m in linhas}


def salvar_mapeamento(sessao: Session, amostra_id: int, mapeamento: dict[str, str]) -> None:
    sessao.query(models.Mapeamento).filter(models.Mapeamento.amostra_id == amostra_id).delete()
    for campo, coluna in mapeamento.items():
        if coluna:
            sessao.add(models.Mapeamento(amostra_id=amostra_id, campo_logico=campo, coluna=coluna))
    sessao.commit()


CAMPOS_CHAVE_INEDITISMO = ["cpf", "cnpj", "placa"]


def calcular_ineditismo(sessao: Session, amostra_id: int) -> dict | None:
    """Compara os valores da chave dessa amostra (CPF, CNPJ ou placa — o
    primeiro que estiver mapeado) contra todas as OUTRAS amostras já
    carregadas, usando o mapeamento PRÓPRIO de cada uma (a coluna pode ter
    nome diferente em cada vazamento). Alto percentual inédito é indício de
    vazamento novo; baixo percentual sugere reenvio de um vazamento já visto.
    """
    mapeamento_atual = carregar_mapeamento(sessao, amostra_id)
    campo_logico = next((c for c in CAMPOS_CHAVE_INEDITISMO if mapeamento_atual.get(c)), None)
    if not campo_logico:
        return None
    coluna_atual = mapeamento_atual[campo_logico]

    linhas_amostra = sessao.query(models.AmostraLinha).filter(models.AmostraLinha.amostra_id == amostra_id).all()
    valores_amostra = {
        str(linha.dados[coluna_atual]).strip() for linha in linhas_amostra if linha.dados.get(coluna_atual)
    }
    valores_amostra.discard("")
    if not valores_amostra:
        return None

    outros_mapeamentos = (
        sessao.query(models.Mapeamento)
        .filter(models.Mapeamento.campo_logico == campo_logico, models.Mapeamento.amostra_id != amostra_id)
        .all()
    )
    valores_conhecidos: set[str] = set()
    for m in outros_mapeamentos:
        linhas_outra = sessao.query(models.AmostraLinha).filter(models.AmostraLinha.amostra_id == m.amostra_id).all()
        for linha in linhas_outra:
            valor = linha.dados.get(m.coluna)
            if valor:
                valores_conhecidos.add(str(valor).strip())

    ineditos = valores_amostra - valores_conhecidos
    total = len(valores_amostra)
    return {
        "campo_logico": campo_logico,
        "total": total,
        "ineditos": len(ineditos),
        "percentual_inedito": round(len(ineditos) / total * 100, 1),
        "amostras_comparadas": len({m.amostra_id for m in outros_mapeamentos}),
    }


def persistir_analise(
    sessao: Session,
    amostra_id: int,
    relatorio: Relatorio,
    algoritmos_origem: list[str],
    algoritmos_registro: list[str],
    limiar_fuzzy: float,
) -> models.Analise:
    analise = models.Analise(
        amostra_id=amostra_id,
        limite_inferior=relatorio.janela.limite_inferior,
        limite_superior=relatorio.janela.limite_superior,
        consistente=relatorio.janela.consistente,
        algoritmos_origem=algoritmos_origem,
        algoritmos_registro=algoritmos_registro,
        limiar_fuzzy=limiar_fuzzy,
    )
    sessao.add(analise)
    sessao.flush()  # garante analise.id antes de criar as linhas filhas

    for ev in relatorio.evidencias:
        sessao.add(
            models.EvidenciaDB(
                analise_id=analise.id,
                chave=ev.chave,
                tipo_evento=ev.tipo_evento,
                direcao=ev.direcao.value,
                data_referencia=ev.data_referencia,
                forca=ev.forca.value,
                justificativa=ev.justificativa,
                algoritmo=ev.algoritmo,
                score=ev.score,
            )
        )

    if relatorio.origem is not None:
        # mapeia id textual (VazamentoConhecido.id, que é o "identificador" no banco)
        # de volta para o id numérico da linha, para poder guardar a FK
        identificadores = {c.entrada.id for c in relatorio.origem.candidatos}
        linhas_catalogo = (
            sessao.query(models.VazamentoCatalogo)
            .filter(models.VazamentoCatalogo.identificador.in_(identificadores))
            .all()
        )
        id_por_identificador = {v.identificador: v.id for v in linhas_catalogo}

        for candidato in relatorio.origem.candidatos:
            for alg_id, score in candidato.scores.items():
                sessao.add(
                    models.OrigemCandidatoDB(
                        analise_id=analise.id,
                        vazamento_catalogo_id=id_por_identificador.get(candidato.entrada.id),
                        nome_snapshot=candidato.entrada.nome,
                        algoritmo=alg_id,
                        score=score,
                    )
                )

    sessao.commit()
    sessao.refresh(analise)
    return analise
