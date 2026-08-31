from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..db import obter_sessao
from ..util import redirecionar

router = APIRouter(prefix="/catalogo", tags=["catalogo"])
templates = Jinja2Templates(directory="webapp/templates")


def _parse_campos(texto: str) -> list[str]:
    partes = re.split(r"[\n,]+", texto)
    return [p.strip() for p in partes if p.strip()]


def _slugificar(texto: str, alternativa: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", texto.lower()).strip("-") or alternativa


def encontrar_ou_criar_origem(
    sessao: Session,
    nome: str,
    campos: list[str],
    fonte_suspeita: str | None = None,
    observacoes: str | None = None,
) -> models.VazamentoCatalogo:
    """Acha a entrada do catálogo com esse nome (por slug) e MESCLA os campos
    novos nela — assim o catálogo aprende/acumula schema a cada amostra que
    declara a mesma origem — ou cria uma entrada nova se for a primeira vez.
    """
    identificador_base = _slugificar(nome, "origem")
    existente = (
        sessao.query(models.VazamentoCatalogo)
        .filter(models.VazamentoCatalogo.identificador == identificador_base)
        .first()
    )
    if existente:
        campos_mesclados = list(dict.fromkeys([*existente.campos, *campos]))  # união, preserva ordem
        existente.campos = campos_mesclados
        if fonte_suspeita and not existente.fonte_suspeita:
            existente.fonte_suspeita = fonte_suspeita
        sessao.add(existente)
        sessao.commit()
        sessao.refresh(existente)
        return existente

    entrada = models.VazamentoCatalogo(
        identificador=identificador_base,
        nome=nome,
        campos=campos,
        fonte_suspeita=fonte_suspeita,
        observacoes=observacoes,
    )
    sessao.add(entrada)
    sessao.commit()
    sessao.refresh(entrada)
    return entrada


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    entradas = sessao.query(models.VazamentoCatalogo).order_by(models.VazamentoCatalogo.criado_em.desc()).all()
    n_amostras_por_entrada = {
        entrada.id: sessao.query(models.Amostra).filter(models.Amostra.origem_catalogo_id == entrada.id).count()
        for entrada in entradas
    }
    return templates.TemplateResponse(
        request, "catalogo/lista.html", {"entradas": entradas, "n_amostras_por_entrada": n_amostras_por_entrada}
    )


@router.post("")
def criar(
    request: Request,
    identificador: str = Form(...),
    nome: str = Form(...),
    campos: str = Form(...),
    fonte_suspeita: str = Form(""),
    data_conhecida: str = Form(""),
    observacoes: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    sessao.add(
        models.VazamentoCatalogo(
            identificador=identificador.strip(),
            nome=nome.strip(),
            campos=_parse_campos(campos),
            fonte_suspeita=fonte_suspeita.strip() or None,
            data_conhecida=data_conhecida.strip() or None,
            observacoes=observacoes.strip() or None,
        )
    )
    sessao.commit()
    return redirecionar(request, "/catalogo")


@router.get("/de-amostra/{amostra_id}")
def de_amostra(request: Request, amostra_id: int, sessao: Session = Depends(obter_sessao)):
    amostra = sessao.get(models.Amostra, amostra_id)
    entrada = encontrar_ou_criar_origem(
        sessao,
        nome=amostra.nome,
        campos=list(amostra.colunas),
        observacoes=f"Cadastrado a partir da amostra #{amostra_id}",
    )
    amostra.origem_catalogo_id = entrada.id
    sessao.add(amostra)
    sessao.commit()
    return redirecionar(request, "/catalogo")


@router.post("/{entrada_id}/excluir")
def excluir(request: Request, entrada_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.VazamentoCatalogo).filter(models.VazamentoCatalogo.id == entrada_id).delete()
    sessao.commit()
    return redirecionar(request, "/catalogo")
