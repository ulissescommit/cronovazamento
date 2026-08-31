from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, repositorio
from ..db import obter_sessao
from .catalogo import encontrar_ou_criar_origem

router = APIRouter(prefix="/amostras", tags=["amostras"])
templates = Jinja2Templates(directory="webapp/templates")

CAMPOS_LOGICOS = [
    ("cpf", "CPF (pessoa)"),
    ("nome", "Nome (pessoa)"),
    ("status_obito", "Status de óbito (pessoa, opcional)"),
    ("cnpj", "CNPJ (empresa)"),
    ("socio", "Sócio (empresa)"),
    ("participacao", "Participação (empresa, opcional)"),
    ("placa", "Placa (veículo)"),
    ("proprietario", "Proprietário (veículo)"),
]


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    amostras = sessao.query(models.Amostra).order_by(models.Amostra.criado_em.desc()).all()
    for a in amostras:
        _ = a.linhas  # força carregamento para contar linhas no template
    return templates.TemplateResponse(request, "amostras/lista.html", {"amostras": amostras})


@router.get("/nova", response_class=HTMLResponse)
def form_nova(request: Request):
    return templates.TemplateResponse(request, "amostras/nova.html", {"erro": None})


@router.post("")
def criar(
    request: Request,
    nome: str = Form(...),
    delimitador: str = Form(","),
    arquivo: UploadFile = File(...),
    origem_nome: str = Form(""),
    origem_fonte: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    conteudo = arquivo.file.read().decode("utf-8-sig")
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=delimitador)
    colunas = leitor.fieldnames or []
    linhas = list(leitor)

    if not colunas:
        return templates.TemplateResponse(
            request, "amostras/nova.html", {"erro": "Não foi possível detectar colunas no CSV enviado."}
        )

    amostra = models.Amostra(
        nome=nome, arquivo_original=arquivo.filename or "amostra.csv", delimitador=delimitador, colunas=colunas
    )
    sessao.add(amostra)
    sessao.flush()

    for indice, linha in enumerate(linhas):
        sessao.add(models.AmostraLinha(amostra_id=amostra.id, indice=indice, dados=dict(linha)))

    if origem_nome.strip():
        entrada = encontrar_ou_criar_origem(
            sessao,
            nome=origem_nome.strip(),
            campos=colunas,
            fonte_suspeita=origem_fonte.strip() or None,
        )
        amostra.origem_catalogo_id = entrada.id
        sessao.add(amostra)

    sessao.commit()

    return RedirectResponse(f"/amostras/{amostra.id}", status_code=303)


@router.get("/{amostra_id}", response_class=HTMLResponse)
def detalhe(request: Request, amostra_id: int, sessao: Session = Depends(obter_sessao)):
    amostra = sessao.get(models.Amostra, amostra_id)
    n_linhas = sessao.query(models.AmostraLinha).filter(models.AmostraLinha.amostra_id == amostra_id).count()
    mapeamento = repositorio.carregar_mapeamento(sessao, amostra_id)
    return templates.TemplateResponse(
        request,
        "amostras/detalhe.html",
        {
            "amostra": amostra,
            "n_linhas": n_linhas,
            "mapeamento": mapeamento,
            "campos_logicos": CAMPOS_LOGICOS,
        },
    )


@router.post("/{amostra_id}/mapeamento")
async def salvar_mapeamento(request: Request, amostra_id: int, sessao: Session = Depends(obter_sessao)):
    dados = await request.form()
    mapeamento = {campo: dados.get(campo, "") for campo, _ in CAMPOS_LOGICOS}
    repositorio.salvar_mapeamento(sessao, amostra_id, mapeamento)
    return RedirectResponse(f"/amostras/{amostra_id}", status_code=303)
