from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models
from .db import criar_tabelas, obter_sessao
from .routers import amostras, analises, catalogo, conexoes, eventos, verificacoes

DIR_RAIZ = Path(__file__).resolve().parent.parent
DIR_EXEMPLOS_AMOSTRAS = DIR_RAIZ / "data" / "amostras"
DIR_EXEMPLOS_REFERENCIAS = DIR_RAIZ / "data" / "referencias"
DIR_EXEMPLOS_CATALOGO = DIR_RAIZ / "data" / "catalogo"

app = FastAPI(title="cronovazamento")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/templates")

app.include_router(amostras.router)
app.include_router(eventos.router)
app.include_router(catalogo.router)
app.include_router(analises.router)
app.include_router(conexoes.router)
app.include_router(verificacoes.router)


@app.on_event("startup")
def _startup() -> None:
    criar_tabelas()


@app.get("/", response_class=HTMLResponse)
def painel(request: Request, sessao: Session = Depends(obter_sessao)):
    n_amostras = sessao.query(models.Amostra).count()
    n_eventos = (
        sessao.query(models.EventoPessoa).count()
        + sessao.query(models.EventoEmpresa).count()
        + sessao.query(models.EventoVeiculo).count()
    )
    n_catalogo = sessao.query(models.VazamentoCatalogo).count()
    n_analises = sessao.query(models.Analise).count()
    amostras_recentes = sessao.query(models.Amostra).order_by(models.Amostra.criado_em.desc()).limit(5).all()
    analises_recentes = sessao.query(models.Analise).order_by(models.Analise.executado_em.desc()).limit(5).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "n_amostras": n_amostras,
            "n_eventos": n_eventos,
            "n_catalogo": n_catalogo,
            "n_analises": n_analises,
            "amostras_recentes": amostras_recentes,
            "analises_recentes": analises_recentes,
        },
    )


@app.post("/exemplos/importar")
def importar_exemplos(sessao: Session = Depends(obter_sessao)):
    """Carrega os dados sintéticos de data/*.exemplo.* no banco, só para dar
    uma volta rápida na ferramenta sem preencher formulário manualmente."""
    caminho_amostra = DIR_EXEMPLOS_AMOSTRAS / "amostra.exemplo.csv"
    if caminho_amostra.exists():
        with caminho_amostra.open(encoding="utf-8-sig", newline="") as f:
            leitor = csv.DictReader(f)
            colunas = leitor.fieldnames or []
            linhas = list(leitor)
        amostra = models.Amostra(
            nome="Amostra de exemplo (sintética)",
            arquivo_original="amostra.exemplo.csv",
            delimitador=",",
            colunas=colunas,
        )
        sessao.add(amostra)
        sessao.flush()
        for indice, linha in enumerate(linhas):
            sessao.add(models.AmostraLinha(amostra_id=amostra.id, indice=indice, dados=dict(linha)))
        sessao.add(models.Mapeamento(amostra_id=amostra.id, campo_logico="cpf", coluna="CPF"))
        sessao.add(models.Mapeamento(amostra_id=amostra.id, campo_logico="nome", coluna="NOME_COMPLETO"))
        sessao.add(models.Mapeamento(amostra_id=amostra.id, campo_logico="status_obito", coluna="STATUS_OBITO"))

    caminho_eventos_pessoa = DIR_EXEMPLOS_REFERENCIAS / "eventos_pessoa.exemplo.json"
    if caminho_eventos_pessoa.exists():
        with caminho_eventos_pessoa.open(encoding="utf-8") as f:
            for ev in json.load(f):
                sessao.add(
                    models.EventoPessoa(
                        cpf=ev["cpf"],
                        tipo=ev["tipo"],
                        data=date.fromisoformat(ev["data"]),
                        nome_anterior=ev.get("nome_anterior"),
                        nome_novo=ev.get("nome_novo"),
                        forca=ev.get("forca"),
                    )
                )

    caminho_catalogo = DIR_EXEMPLOS_CATALOGO / "catalogo.exemplo.json"
    if caminho_catalogo.exists():
        with caminho_catalogo.open(encoding="utf-8") as f:
            for entrada in json.load(f):
                ja_existe = (
                    sessao.query(models.VazamentoCatalogo)
                    .filter(models.VazamentoCatalogo.identificador == entrada["id"])
                    .first()
                )
                if ja_existe:
                    continue
                sessao.add(
                    models.VazamentoCatalogo(
                        identificador=entrada["id"],
                        nome=entrada["nome"],
                        campos=entrada["campos"],
                        fonte_suspeita=entrada.get("fonte_suspeita"),
                        data_conhecida=entrada.get("data_conhecida"),
                        observacoes=entrada.get("observacoes"),
                    )
                )

    sessao.commit()
    return RedirectResponse("/", status_code=303)
