from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..db import obter_sessao
from ..util import redirecionar

router = APIRouter(prefix="/eventos", tags=["eventos"])
templates = Jinja2Templates(directory="webapp/templates")


@router.get("/pessoa", response_class=HTMLResponse)
def listar_pessoa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoPessoa).order_by(models.EventoPessoa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/pessoa.html", {"eventos": eventos})


@router.post("/pessoa")
def criar_pessoa(
    request: Request,
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
    return redirecionar(request, "/eventos/pessoa")


@router.post("/pessoa/{evento_id}/excluir")
def excluir_pessoa(request: Request, evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoPessoa).filter(models.EventoPessoa.id == evento_id).delete()
    sessao.commit()
    return redirecionar(request, "/eventos/pessoa")


@router.get("/empresa", response_class=HTMLResponse)
def listar_empresa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoEmpresa).order_by(models.EventoEmpresa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/empresa.html", {"eventos": eventos})


@router.post("/empresa")
def criar_empresa(
    request: Request,
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
    return redirecionar(request, "/eventos/empresa")


@router.post("/empresa/{evento_id}/excluir")
def excluir_empresa(request: Request, evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoEmpresa).filter(models.EventoEmpresa.id == evento_id).delete()
    sessao.commit()
    return redirecionar(request, "/eventos/empresa")


@router.get("/veiculo", response_class=HTMLResponse)
def listar_veiculo(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoVeiculo).order_by(models.EventoVeiculo.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/veiculo.html", {"eventos": eventos})


@router.post("/veiculo")
def criar_veiculo(
    request: Request,
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
    return redirecionar(request, "/eventos/veiculo")


@router.post("/veiculo/{evento_id}/excluir")
def excluir_veiculo(request: Request, evento_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.EventoVeiculo).filter(models.EventoVeiculo.id == evento_id).delete()
    sessao.commit()
    return redirecionar(request, "/eventos/veiculo")
