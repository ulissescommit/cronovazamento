from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from cronovazamento.conectores import MOTORES, MOTORES_RELACIONAIS, ConexaoInfo, listar_colunas, listar_tabelas
from cronovazamento.conectores import testar_conexao as testar_conexao_motor

from .. import cifra, models
from ..db import obter_sessao
from .catalogo import encontrar_ou_criar_origem

router = APIRouter(prefix="/conexoes", tags=["conexoes"])
templates = Jinja2Templates(directory="webapp/templates")


def info_de(conexao: models.ConexaoExterna) -> ConexaoInfo:
    senha = cifra.decifrar(conexao.senha_cifrada) if conexao.senha_cifrada else None
    return ConexaoInfo(
        motor=conexao.motor,
        banco=conexao.banco,
        host=conexao.host,
        porta=conexao.porta,
        usuario=conexao.usuario,
        senha=senha,
        caminho_arquivo=conexao.caminho_arquivo,
    )


@router.get("", response_class=HTMLResponse)
def listar(request: Request, sessao: Session = Depends(obter_sessao)):
    conexoes = sessao.query(models.ConexaoExterna).order_by(models.ConexaoExterna.criado_em.desc()).all()
    return templates.TemplateResponse(
        request, "conexoes/lista.html", {"conexoes": conexoes, "motores": MOTORES, "motores_relacionais": MOTORES_RELACIONAIS}
    )


@router.post("")
def criar(
    nome: str = Form(...),
    motor: str = Form(...),
    host: str = Form(""),
    porta: str = Form(""),
    banco: str = Form(...),
    usuario: str = Form(""),
    senha: str = Form(""),
    caminho_arquivo: str = Form(""),
    sessao: Session = Depends(obter_sessao),
):
    sessao.add(
        models.ConexaoExterna(
            nome=nome.strip(),
            motor=motor,
            host=host.strip() or None,
            porta=int(porta) if porta.strip() else None,
            banco=banco.strip(),
            usuario=usuario.strip() or None,
            senha_cifrada=cifra.cifrar(senha) if senha else None,
            caminho_arquivo=caminho_arquivo.strip() or None,
        )
    )
    sessao.commit()
    return RedirectResponse("/conexoes", status_code=303)


@router.post("/{conexao_id}/excluir")
def excluir(conexao_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.query(models.ConexaoExterna).filter(models.ConexaoExterna.id == conexao_id).delete()
    sessao.commit()
    return RedirectResponse("/conexoes", status_code=303)


@router.get("/{conexao_id}/tabelas", response_class=HTMLResponse)
def tabelas(request: Request, conexao_id: int, tabela: str | None = None, sessao: Session = Depends(obter_sessao)):
    conexao = sessao.get(models.ConexaoExterna, conexao_id)
    erro = None
    lista_tabelas: list[str] = []
    colunas: list[str] = []
    try:
        info = info_de(conexao)
        lista_tabelas = listar_tabelas(info)
        if tabela:
            colunas = listar_colunas(info, tabela)
    except Exception as exc:  # driver ausente, host inalcançável, credencial errada etc.
        erro = str(exc)

    return templates.TemplateResponse(
        request,
        "conexoes/tabelas.html",
        {"conexao": conexao, "erro": erro, "tabelas": lista_tabelas, "tabela_escolhida": tabela, "colunas": colunas},
    )


@router.post("/{conexao_id}/testar", response_class=HTMLResponse)
def testar(request: Request, conexao_id: int, sessao: Session = Depends(obter_sessao)):
    conexao = sessao.get(models.ConexaoExterna, conexao_id)
    try:
        testar_conexao_motor(info_de(conexao))
        resultado = "Conexão OK."
    except Exception as exc:
        resultado = f"Falhou: {exc}"
    conexoes = sessao.query(models.ConexaoExterna).order_by(models.ConexaoExterna.criado_em.desc()).all()
    return templates.TemplateResponse(
        request,
        "conexoes/lista.html",
        {
            "conexoes": conexoes,
            "motores": MOTORES,
            "motores_relacionais": MOTORES_RELACIONAIS,
            "resultado_teste": {"conexao_id": conexao_id, "texto": resultado},
        },
    )


@router.get("/{conexao_id}/importar-schema/{tabela}")
def importar_schema(conexao_id: int, tabela: str, sessao: Session = Depends(obter_sessao)):
    conexao = sessao.get(models.ConexaoExterna, conexao_id)
    colunas = listar_colunas(info_de(conexao), tabela)
    encontrar_ou_criar_origem(
        sessao,
        nome=f"{conexao.nome} — {tabela}",
        campos=colunas,
        fonte_suspeita=conexao.nome,
        observacoes=f"Schema importado direto da conexão '{conexao.nome}', tabela/coleção '{tabela}'",
    )
    return RedirectResponse("/catalogo", status_code=303)
