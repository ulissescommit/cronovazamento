from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://cronovazamento:cronovazamento@db:5432/cronovazamento"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def obter_sessao() -> Session:
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


def criar_tabelas() -> None:
    from . import models  # noqa: F401  (garante que os modelos estão registrados no Base)

    Base.metadata.create_all(bind=engine)
