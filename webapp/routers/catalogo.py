from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..db import obter_sessao

router = APIRouter(prefix="/catalogo", tags=["catalogo"])
templates = Jinja2Templates(directory="webapp/templates")


def _parse_campos(texto: str) -> list[str]:
    partes = re.split(r"[\n,]+", texto)
    return [p.strip() for p in partes if p.strip()]


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    entradas = sessao.query(models.VazamentoCatalogo).order_by(models.VazamentoCatalogo.criado_em.desc()).all()
    return templates.TemplateResponse(request, "catalogo/lista.html", {"entradas": entradas})


@router.post("")
def criar(
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
    return RedirectResponse("/catalogo", status_code=303)


@router.get("/de-amostra/{amostra_id}")
def de_amostra(amostra_id: int, sessao: Session = Depends(obter_sessao)):
    amostra = sessao.get(models.Amostra, amostra_id)
    identificador = re.sub(r"[^a-z0-9-]+", "-", amostra.nome.lower()).strip("-") or f"amostra-{amostra_id}"
    existentes = {e.identificador for e in sessao.query(models.VazamentoCatalogo.identificador).all()}
    base = identificador
    contador = 2
    while identificador in existentes:
        identificador = f"{base}-{contador}"
        contador += 1

    sessao.add(
        models.VazamentoCatalogo(
            identificador=identificador,
            nome=amostra.nome,
            campos=list(amostra.colunas),
            observacoes=f"Cadastrado automaticamente a partir da amostra #{amostra_id}",
        )
    )
    sessao.commit()
    return RedirectResponse("/catalogo", status_code=303)


@router.post("/{entrada_id}/excluir")
def excluir(entrada_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.VazamentoCatalogo).filter(models.VazamentoCatalogo.id == entrada_id).delete()
    sessao.commit()
    return RedirectResponse("/catalogo", status_code=303)
