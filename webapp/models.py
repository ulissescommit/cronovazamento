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
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    linhas: Mapped[list["AmostraLinha"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")
    mapeamentos: Mapped[list["Mapeamento"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")
    analises: Mapped[list["Analise"]] = relationship(back_populates="amostra", cascade="all, delete-orphan")


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
    tipo: Mapped[str] = mapped_column(String(32))  # nascimento | obito | mudanca_nome
    data: Mapped[date] = mapped_column(Date)
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
