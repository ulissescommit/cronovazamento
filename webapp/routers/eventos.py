from __future__ import annotations

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..db import obter_sessao
from ..util import redirecionar

router = APIRouter(prefix="/eventos", tags=["eventos"])
templates = Jinja2Templates(directory="webapp/templates")


def _linhas_de_arquivo(conteudo: bytes, nome_arquivo: str) -> list[dict]:
    """Aceita .json (lista de objetos, mesmo schema do CLI/data/referencias/*.exemplo.json)
    ou .csv (cabeçalho = nome dos campos). É o caminho principal pra alimentar eventos —
    o formulário de um-por-vez existe só pra ajuste pontual."""
    texto = conteudo.decode("utf-8-sig")
    if nome_arquivo.lower().endswith(".json"):
        dados = json.loads(texto)
        if not isinstance(dados, list):
            raise ValueError("o JSON precisa ser uma lista de eventos")
        return dados
    leitor = csv.DictReader(io.StringIO(texto))
    if not leitor.fieldnames:
        raise ValueError("não foi possível detectar colunas no CSV")
    return [dict(linha) for linha in leitor]


# ---------------------------------------------------------------------------
# pessoa
# ---------------------------------------------------------------------------


@router.get("/pessoa", response_class=HTMLResponse)
def listar_pessoa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoPessoa).order_by(models.EventoPessoa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/pessoa.html", {"eventos": eventos})


@router.post("/pessoa/importar")
async def importar_pessoa(request: Request, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao)):
    resultado = {"importados": 0, "erros": 0, "mensagem_erro": None}
    try:
        linhas = _linhas_de_arquivo(await arquivo.read(), arquivo.filename or "")
        for linha in linhas:
            try:
                sessao.add(
                    models.EventoPessoa(
                        cpf=str(linha["cpf"]).strip(),
                        tipo=str(linha["tipo"]).strip(),
                        data=date.fromisoformat(str(linha["data"]).strip()),
                        nome_anterior=str(linha.get("nome_anterior") or "").strip() or None,
                        nome_novo=str(linha.get("nome_novo") or "").strip() or None,
                        forca=str(linha.get("forca") or "").strip() or None,
                    )
                )
                resultado["importados"] += 1
            except Exception:
                resultado["erros"] += 1
        sessao.commit()
    except Exception as exc:
        resultado["mensagem_erro"] = str(exc)

    eventos = sessao.query(models.EventoPessoa).order_by(models.EventoPessoa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/pessoa.html", {"eventos": eventos, "resultado_importacao": resultado})


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


# ---------------------------------------------------------------------------
# empresa
# ---------------------------------------------------------------------------


@router.get("/empresa", response_class=HTMLResponse)
def listar_empresa(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoEmpresa).order_by(models.EventoEmpresa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/empresa.html", {"eventos": eventos})


@router.post("/empresa/importar")
async def importar_empresa(request: Request, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao)):
    resultado = {"importados": 0, "erros": 0, "mensagem_erro": None}
    try:
        linhas = _linhas_de_arquivo(await arquivo.read(), arquivo.filename or "")
        for linha in linhas:
            try:
                participacao = linha.get("participacao_nova")
                sessao.add(
                    models.EventoEmpresa(
                        cnpj=str(linha["cnpj"]).strip(),
                        data=date.fromisoformat(str(linha["data"]).strip()),
                        socio=str(linha["socio"]).strip(),
                        situacao_nova=str(linha["situacao_nova"]).strip(),
                        participacao_nova=float(participacao) if participacao not in (None, "") else None,
                        forca=str(linha.get("forca") or "").strip() or None,
                    )
                )
                resultado["importados"] += 1
            except Exception:
                resultado["erros"] += 1
        sessao.commit()
    except Exception as exc:
        resultado["mensagem_erro"] = str(exc)

    eventos = sessao.query(models.EventoEmpresa).order_by(models.EventoEmpresa.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/empresa.html", {"eventos": eventos, "resultado_importacao": resultado})


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


# ---------------------------------------------------------------------------
# veiculo
# ---------------------------------------------------------------------------


@router.get("/veiculo", response_class=HTMLResponse)
def listar_veiculo(request: Request, sessao: Session = Depends(obter_sessao)):
    eventos = sessao.query(models.EventoVeiculo).order_by(models.EventoVeiculo.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/veiculo.html", {"eventos": eventos})


@router.post("/veiculo/importar")
async def importar_veiculo(request: Request, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao)):
    resultado = {"importados": 0, "erros": 0, "mensagem_erro": None}
    try:
        linhas = _linhas_de_arquivo(await arquivo.read(), arquivo.filename or "")
        for linha in linhas:
            try:
                sessao.add(
                    models.EventoVeiculo(
                        placa=str(linha["placa"]).strip(),
                        data=date.fromisoformat(str(linha["data"]).strip()),
                        proprietario_anterior=str(linha.get("proprietario_anterior") or "").strip() or None,
                        proprietario_novo=str(linha.get("proprietario_novo") or "").strip() or None,
                        forca=str(linha.get("forca") or "").strip() or None,
                    )
                )
                resultado["importados"] += 1
            except Exception:
                resultado["erros"] += 1
        sessao.commit()
    except Exception as exc:
        resultado["mensagem_erro"] = str(exc)

    eventos = sessao.query(models.EventoVeiculo).order_by(models.EventoVeiculo.data.desc()).all()
    return templates.TemplateResponse(request, "eventos/veiculo.html", {"eventos": eventos, "resultado_importacao": resultado})


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
