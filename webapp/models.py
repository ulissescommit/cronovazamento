from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Amostra(Base):
    __tablename__ = "amostras"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    arquivo_original: Mapped[str] = mapped_column(String(255))
    delimitador: Mapped[str] = mapped_column(String(4), default=",")
    colunas: Mapped[list] = mapped_column(JSON)
    # quando a amostra foi enviada pra dentro da ferramenta — serve como
    # registro de "quando essa amostra foi mandada"
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # origem declarada manualmente por quem sobe a amostra (opcional) —
    # aponta pra entrada do catálogo criada/reaproveitada nesse envio
    origem_catalogo_id: Mapped[int | None] = mapped_column(ForeignKey("vazamentos_catalogo.id"), default=None)

    linhas: Mapped[list["AmostraLinha"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")
    mapeamentos: Mapped[list["Mapeamento"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")
    analises: Mapped[list["Analise"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")
    origem_catalogo: Mapped["VazamentoCatalogo | None"] = relationship(foreign_keys=[origem_catalogo_id])


class AmostraLinha(Base):
    __tablename__ = "amostra_linhas"

    id: Mapped[int] = mapped_column(primary_key=True)
    amostra_id: Mapped[int] = mapped_column(ForeignKey("amostras.id"))
    indice: Mapped[int]
    dados: Mapped[dict] = mapped_column(JSON)

    amostra: Mapped[Amostra] = relationship(back_populates="linhas")


class Mapeamento(Base):
    __tablename__ = "mapeamentos"
    __table_args__ = (UniqueConstraint("amostra_id", "campo_logico", name="uq_mapeamento_amostra_campo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    amostra_id: Mapped[int] = mapped_column(ForeignKey("amostras.id"))
    campo_logico: Mapped[str] = mapped_column(String(64))
    coluna: Mapped[str] = mapped_column(String(255))

    amostra: Mapped[Amostra] = relationship(back_populates="mapeamentos")


class EventoPessoa(Base):
    __tablename__ = "eventos_pessoa"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(32), index=True)
    # nascimento | obito | mudanca_nome | mudanca_telefone | mudanca_email |
    # mudanca_endereco | nova_conta_social
    tipo: Mapped[str] = mapped_column(String(32))
    data: Mapped[date] = mapped_column(Date)
    # reaproveitadas como "valor anterior/novo" genérico pra qualquer tipo de
    # mudança (nome, telefone, e-mail, endereço, usuário social) — o nome da
    # coluna ficou de quando só existia mudança de nome; ver cronovazamento/eventos.py
    nome_anterior: Mapped[str | None] = mapped_column(String(255), default=None)
    nome_novo: Mapped[str | None] = mapped_column(String(255), default=None)
    forca: Mapped[str | None] = mapped_column(String(16), default=None)


class EventoEmpresa(Base):
    __tablename__ = "eventos_empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str] = mapped_column(String(32), index=True)
    tipo: Mapped[str] = mapped_column(String(32), default="alteracao_societaria")
    data: Mapped[date] = mapped_column(Date)
    socio: Mapped[str] = mapped_column(String(255))
    situacao_nova: Mapped[str] = mapped_column(String(16))  # presente | ausente
    participacao_nova: Mapped[float | None] = mapped_column(Float, default=None)
    forca: Mapped[str | None] = mapped_column(String(16), default=None)


class EventoVeiculo(Base):
    __tablename__ = "eventos_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    placa: Mapped[str] = mapped_column(String(16), index=True)
    tipo: Mapped[str] = mapped_column(String(32), default="transferencia_propriedade")
    data: Mapped[date] = mapped_column(Date)
    proprietario_anterior: Mapped[str | None] = mapped_column(String(255), default=None)
    proprietario_novo: Mapped[str | None] = mapped_column(String(255), default=None)
    forca: Mapped[str | None] = mapped_column(String(16), default=None)


class VazamentoCatalogo(Base):
    __tablename__ = "vazamentos_catalogo"

    id: Mapped[int] = mapped_column(primary_key=True)
    identificador: Mapped[str] = mapped_column(String(128), unique=True)
    nome: Mapped[str] = mapped_column(String(255))
    campos: Mapped[list] = mapped_column(JSON)
    fonte_suspeita: Mapped[str | None] = mapped_column(String(255), default=None)
    data_conhecida: Mapped[str | None] = mapped_column(String(32), default=None)
    observacoes: Mapped[str | None] = mapped_column(Text, default=None)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConexaoExterna(Base):
    """Uma conexão cadastrada com um banco de dados candidato a origem do
    vazamento — reaproveitável entre 'alimentar catálogo' e 'verificar'."""

    __tablename__ = "conexoes_externas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    motor: Mapped[str] = mapped_column(String(32))  # postgresql | mysql | mariadb | mssql | oracle | sqlite | mongodb
    host: Mapped[str | None] = mapped_column(String(255), default=None)
    porta: Mapped[int | None] = mapped_column(default=None)
    banco: Mapped[str] = mapped_column(String(255))
    usuario: Mapped[str | None] = mapped_column(String(255), default=None)
    senha_cifrada: Mapped[str | None] = mapped_column(Text, default=None)
    caminho_arquivo: Mapped[str | None] = mapped_column(String(500), default=None)  # só sqlite
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    verificacoes: Mapped[list["VerificacaoConexao"]] = relationship(
        back_populates="conexao", cascade="all, delete-orphan"
    )


class VerificacaoConexao(Base):
    """Resultado persistido de rodar 'esse vazamento veio dessa base?' contra
    uma tabela/coleção de uma ConexaoExterna."""

    __tablename__ = "verificacoes_conexao"

    id: Mapped[int] = mapped_column(primary_key=True)
    amostra_id: Mapped[int] = mapped_column(ForeignKey("amostras.id"))
    conexao_id: Mapped[int] = mapped_column(ForeignKey("conexoes_externas.id"))
    tabela: Mapped[str] = mapped_column(String(255))
    mapeamento_externo: Mapped[dict] = mapped_column(JSON)
    campo_chave: Mapped[str] = mapped_column(String(32))
    algoritmos_string: Mapped[list] = mapped_column(JSON)
    limiar: Mapped[float] = mapped_column(Float)
    executado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_linhas: Mapped[int] = mapped_column(default=0)
    encontrados: Mapped[int] = mapped_column(default=0)
    divergentes: Mapped[int] = mapped_column(default=0)
    # snapshot serializado dos registros divergentes (chave + campos comparados) — informativo,
    # não normalizado em tabela própria por não ser um dado consultado além dessa tela
    registros_divergentes: Mapped[list] = mapped_column(JSON)

    amostra: Mapped[Amostra] = relationship()
    conexao: Mapped[ConexaoExterna] = relationship(back_populates="verificacoes")


class Analise(Base):
    __tablename__ = "analises"

    id: Mapped[int] = mapped_column(primary_key=True)
    amostra_id: Mapped[int] = mapped_column(ForeignKey("amostras.id"))
    executado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    limite_inferior: Mapped[date | None] = mapped_column(Date, default=None)
    limite_superior: Mapped[date | None] = mapped_column(Date, default=None)
    consistente: Mapped[bool] = mapped_column(default=True)
    algoritmos_origem: Mapped[list] = mapped_column(JSON)
    algoritmos_registro: Mapped[list] = mapped_column(JSON)
    limiar_fuzzy: Mapped[float] = mapped_column(Float)

    amostra: Mapped[Amostra] = relationship(back_populates="analises")
    evidencias: Mapped[list["EvidenciaDB"]] = relationship(back_populates="analise", cascade="all, delete-orphan")
    origem_candidatos: Mapped[list["OrigemCandidatoDB"]] = relationship(
        back_populates="analise", cascade="all, delete-orphan"
    )


class EvidenciaDB(Base):
    __tablename__ = "evidencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    analise_id: Mapped[int] = mapped_column(ForeignKey("analises.id"))
    chave: Mapped[str] = mapped_column(String(128))
    tipo_evento: Mapped[str] = mapped_column(String(32))
    direcao: Mapped[str] = mapped_column(String(4))
    data_referencia: Mapped[date] = mapped_column(Date)
    forca: Mapped[str] = mapped_column(String(16))
    justificativa: Mapped[str] = mapped_column(Text)
    algoritmo: Mapped[str | None] = mapped_column(String(32), default=None)
    score: Mapped[float | None] = mapped_column(Float, default=None)

    analise: Mapped[Analise] = relationship(back_populates="evidencias")


class OrigemCandidatoDB(Base):
    __tablename__ = "origem_candidatos"

    id: Mapped[int] = mapped_column(primary_key=True)
    analise_id: Mapped[int] = mapped_column(ForeignKey("analises.id"))
    vazamento_catalogo_id: Mapped[int | None] = mapped_column(ForeignKey("vazamentos_catalogo.id"), default=None)
    nome_snapshot: Mapped[str] = mapped_column(String(255))
    algoritmo: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)

    analise: Mapped[Analise] = relationship(back_populates="origem_candidatos")
