from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from cronovazamento.comparador import analisar
from cronovazamento.proximidade import listar_algoritmos_conjunto, listar_algoritmos_string

from .. import models, repositorio
from ..db import obter_sessao

router = APIRouter(prefix="/analises", tags=["analises"])
templates = Jinja2Templates(directory="webapp/templates")


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    analises = sessao.query(models.Analise).order_by(models.Analise.executado_em.desc()).all()
    return templates.TemplateResponse(request, "analises/lista.html", {"analises": analises})


@router.get("/nova", response_class=HTMLResponse)
def form_nova(request: Request, amostra_id: int, sessao: Session = Depends(obter_sessao)):
    amostra = sessao.get(models.Amostra, amostra_id)
    n_linhas = sessao.query(models.AmostraLinha).filter(models.AmostraLinha.amostra_id == amostra_id).count()
    mapeamento = repositorio.carregar_mapeamento(sessao, amostra_id)
    return templates.TemplateResponse(
        request,
        "analises/nova.html",
        {
            "amostra": amostra,
            "n_linhas": n_linhas,
            "mapeamento": mapeamento,
            "algoritmos_string": listar_algoritmos_string(),
            "algoritmos_conjunto": listar_algoritmos_conjunto(),
        },
    )


@router.post("")
async def criar(request: Request, sessao: Session = Depends(obter_sessao)):
    dados = await request.form()
    amostra_id = int(dados["amostra_id"])
    algoritmos_registro = dados.getlist("algoritmo_registro") or ["exato"]
    algoritmos_origem = dados.getlist("algoritmo_origem") or None
    limiar_fuzzy = float(dados.get("limiar", 0.85))

    amostra_motor = repositorio.carregar_amostra(sessao, amostra_id)
    mapeamento = repositorio.carregar_mapeamento(sessao, amostra_id)
    eventos_pessoa = repositorio.carregar_eventos_pessoa(sessao)
    eventos_empresa = repositorio.carregar_eventos_empresa(sessao)
    eventos_veiculo = repositorio.carregar_eventos_veiculo(sessao)
    catalogo = repositorio.carregar_catalogo(sessao)

    relatorio = analisar(
        amostra_motor,
        mapeamento,
        eventos_pessoa=eventos_pessoa,
        eventos_empresa=eventos_empresa,
        eventos_veiculo=eventos_veiculo,
        catalogo=catalogo,
        algoritmos_registro=algoritmos_registro,
        algoritmos_origem=algoritmos_origem,
        limiar_fuzzy=limiar_fuzzy,
    )

    algoritmos_origem_efetivos = relatorio.origem.algoritmos if relatorio.origem else (algoritmos_origem or [])
    analise = repositorio.persistir_analise(
        sessao, amostra_id, relatorio, algoritmos_origem_efetivos, algoritmos_registro, limiar_fuzzy
    )

    return RedirectResponse(f"/analises/{analise.id}", status_code=303)


@router.get("/{analise_id}", response_class=HTMLResponse)
def detalhe(request: Request, analise_id: int, sessao: Session = Depends(obter_sessao)):
    analise = sessao.get(models.Analise, analise_id)
    evidencias = (
        sessao.query(models.EvidenciaDB)
        .filter(models.EvidenciaDB.analise_id == analise_id)
        .order_by(models.EvidenciaDB.data_referencia)
        .all()
    )
    origem_linhas = (
        sessao.query(models.OrigemCandidatoDB).filter(models.OrigemCandidatoDB.analise_id == analise_id).all()
    )

    candidatos_por_nome: dict[str, dict] = {}
    for linha in origem_linhas:
        c = candidatos_por_nome.setdefault(linha.nome_snapshot, {"nome_snapshot": linha.nome_snapshot, "scores": {}})
        c["scores"][linha.algoritmo] = linha.score
    candidatos = list(candidatos_por_nome.values())
    for c in candidatos:
        c["score_medio"] = sum(c["scores"].values()) / len(c["scores"]) if c["scores"] else 0.0
    candidatos.sort(key=lambda c: c["score_medio"], reverse=True)

    dias_de_janela = None
    if analise.limite_inferior and analise.limite_superior:
        dias_de_janela = (analise.limite_superior - analise.limite_inferior).days

    return templates.TemplateResponse(
        request,
        "analises/detalhe.html",
        {
            "analise": analise,
            "evidencias": evidencias,
            "candidatos": candidatos,
            "dias_de_janela": dias_de_janela,
        },
    )
