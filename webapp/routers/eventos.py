from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..db import obter_sessao

router = APIRouter(prefix="/eventos", tags=["eventos"])
templates = Jinja2Templates(directory="webapp/templates")


@router.get("/pessoa", response_class=HTMLResponse)
def listar_pessoa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoPessoa).order_by(models.EventoPessoa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/pessoa.html", {"eventos": eventos})


@router.post("/pessoa")
def criar_pessoa(
    cpf: str = Form(...),
    tipo: str = Form(...),
    data: date = Form(...),
    nome_anterior: str = Form(""),
    nome_novo: str = Form(""),
    forca: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    sessao.add(
        models.EventoPessoa(
            cpf=cpf.strip(),
            tipo=tipo,
            data=data,
            nome_anterior=nome_anterior.strip() or None,
            nome_novo=nome_novo.strip() or None,
            forca=forca or None,
        )
    )
    sessao.commit()
    return RedirectResponse("/eventos/pessoa", status_code=303)


@router.post("/pessoa/{evento_id}/excluir")
def excluir_pessoa(evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoPessoa).filter(models.EventoPessoa.id == evento_id).delete()
    sessao.commit()
    return RedirectResponse("/eventos/pessoa", status_code=303)


@router.get("/empresa", response_class=HTMLResponse)
def listar_empresa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoEmpresa).order_by(models.EventoEmpresa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/empresa.html", {"eventos": eventos})


@router.post("/empresa")
def criar_empresa(
    cnpj: str = Form(...),
    data: date = Form(...),
    socio: str = Form(...),
    situacao_nova: str = Form(...),
    participacao_nova: str = Form(""),
    forca: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    sessao.add(
        models.EventoEmpresa(
            cnpj=cnpj.strip(),
            data=data,
            socio=socio.strip(),
            situacao_nova=situacao_nova,
            participacao_nova=float(participacao_nova) if participacao_nova.strip() else None,
            forca=forca or None,
        )
    )
    sessao.commit()
    return RedirectResponse("/eventos/empresa", status_code=303)


@router.post("/empresa/{evento_id}/excluir")
def excluir_empresa(evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoEmpresa).filter(models.EventoEmpresa.id == evento_id).delete()
    sessao.commit()
    return RedirectResponse("/eventos/empresa", status_code=303)


@router.get("/veiculo", response_class=HTMLResponse)
def listar_veiculo(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoVeiculo).order_by(models.EventoVeiculo.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/veiculo.html", {"eventos": eventos})


@router.post("/veiculo")
def criar_veiculo(
    placa: str = Form(...),
    data: date = Form(...),
    proprietario_anterior: str = Form(""),
    proprietario_novo: str = Form(""),
    forca: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    sessao.add(
        models.EventoVeiculo(
            placa=placa.strip(),
            data=data,
            proprietario_anterior=proprietario_anterior.strip() or None,
            proprietario_novo=proprietario_novo.strip() or None,
            forca=forca or None,
        )
    )
    sessao.commit()
    return RedirectResponse("/eventos/veiculo", status_code=303)


@router.post("/veiculo/{evento_id}/excluir")
def excluir_veiculo(evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoVeiculo).filter(models.EventoVeiculo.id == evento_id).delete()
    sessao.commit()
    return RedirectResponse("/eventos/veiculo", status_code=303)
