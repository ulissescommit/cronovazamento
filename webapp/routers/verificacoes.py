from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from cronovazamento.conectores import buscar_por_chave, listar_colunas
from cronovazamento.proximidade import listar_algoritmos_string
from cronovazamento.verificacao import verificar

from .. import models, repositorio
from ..db import obter_sessao
from .amostras import CAMPOS_LOGICOS
from .conexoes import info_de

router = APIRouter(prefix="/verificacoes", tags=["verificacoes"])
templates = Jinja2Templates(directory="webapp/templates")

CAMPOS_CHAVE_POSSIVEIS = ["cpf", "cnpj", "placa"]


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    verificacoes = sessao.query(models.VerificacaoConexao).order_by(models.VerificacaoConexao.executado_em.desc()).all()
    return templates.TemplateResponse(request, "verificacoes/lista.html", {"verificacoes": verificacoes})


@router.get("/nova", response_class=HTMLResponse)
def form_nova(
    request: Request,
    amostra_id: int,
    conexao_id: int,
    tabela: str | None = None,
    sessao: Session = Depends(obter_sessao),
):
    amostra = sessao.get(models.Amostra, amostra_id)
    conexao = sessao.get(models.ConexaoExterna, conexao_id)
    mapeamento_amostra = repositorio.carregar_mapeamento(sessao, amostra_id)

    erro = None
    tabelas_disponiveis: list[str] = []
    colunas_externas: list[str] = []
    try:
        from cronovazamento.conectores import listar_tabelas

        info = info_de(conexao)
        tabelas_disponiveis = listar_tabelas(info)
        if tabela:
            colunas_externas = listar_colunas(info, tabela)
    except Exception as exc:
        erro = str(exc)

    campos_chave_disponiveis = [c for c in CAMPOS_CHAVE_POSSIVEIS if mapeamento_amostra.get(c)]

    return templates.TemplateResponse(
        request,
        "verificacoes/nova.html",
        {
            "amostra": amostra,
            "conexao": conexao,
            "mapeamento_amostra": mapeamento_amostra,
            "erro": erro,
            "tabelas": tabelas_disponiveis,
            "tabela_escolhida": tabela,
            "colunas_externas": colunas_externas,
            "campos_logicos": CAMPOS_LOGICOS,
            "campos_chave_disponiveis": campos_chave_disponiveis,
            "algoritmos_string": listar_algoritmos_string(),
        },
    )


@router.post("")
async def criar(request: Request, sessao: Session = Depends(obter_sessao)):
    dados = await request.form()
    amostra_id = int(dados["amostra_id"])
    conexao_id = int(dados["conexao_id"])
    tabela = dados["tabela"]
    campo_chave = dados["campo_chave"]
    algoritmos_string = dados.getlist("algoritmo") or ["exato"]
    limiar = float(dados.get("limiar", 0.85))

    mapeamento_externo = {campo: dados.get(f"externo_{campo}", "") for campo, _ in CAMPOS_LOGICOS}
    mapeamento_externo = {k: v for k, v in mapeamento_externo.items() if v}

    conexao = sessao.get(models.ConexaoExterna, conexao_id)
    amostra_motor = repositorio.carregar_amostra(sessao, amostra_id)
    mapeamento_amostra = repositorio.carregar_mapeamento(sessao, amostra_id)

    col_chave_amostra = mapeamento_amostra[campo_chave]
    valores_chave = [linha[col_chave_amostra] for linha in amostra_motor.linhas if linha.get(col_chave_amostra)]

    linhas_externas = buscar_por_chave(info_de(conexao), tabela, mapeamento_externo[campo_chave], valores_chave)

    resultado = verificar(
        amostra_motor.linhas,
        mapeamento_amostra,
        linhas_externas,
        mapeamento_externo,
        campo_chave,
        algoritmos_string=algoritmos_string,
        limiar=limiar,
    )

    registros_divergentes = [
        {
            "chave": r.chave,
            "campos": [
                {
                    "campo": c.campo,
                    "valor_amostra": c.valor_amostra,
                    "valor_externo": c.valor_externo,
                    "algoritmo": c.algoritmo,
                    "score": c.score,
                }
                for c in r.campos
                if c.diverge
            ],
        }
        for r in resultado.registros
        if r.encontrado and r.tem_divergencia
    ]

    verificacao = models.VerificacaoConexao(
        amostra_id=amostra_id,
        conexao_id=conexao_id,
        tabela=tabela,
        mapeamento_externo=mapeamento_externo,
        campo_chave=campo_chave,
        algoritmos_string=algoritmos_string,
        limiar=limiar,
        total_linhas=resultado.total,
        encontrados=resultado.encontrados,
        divergentes=resultado.divergentes,
        registros_divergentes=registros_divergentes,
    )
    sessao.add(verificacao)
    sessao.commit()
    sessao.refresh(verificacao)

    return RedirectResponse(f"/verificacoes/{verificacao.id}", status_code=303)


@router.get("/{verificacao_id}", response_class=HTMLResponse)
def detalhe(request: Request, verificacao_id: int, sessao: Session = Depends(obter_sessao)):
    verificacao = sessao.get(models.VerificacaoConexao, verificacao_id)
    percentual_encontrado = (verificacao.encontrados / verificacao.total_linhas * 100) if verificacao.total_linhas else 0.0
    percentual_divergente = (verificacao.divergentes / verificacao.encontrados * 100) if verificacao.encontrados else 0.0
    return templates.TemplateResponse(
        request,
        "verificacoes/detalhe.html",
        {
            "verificacao": verificacao,
            "percentual_encontrado": percentual_encontrado,
            "percentual_divergente": percentual_divergente,
        },
    )
