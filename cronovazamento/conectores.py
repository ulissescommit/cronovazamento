"""Conector com bancos de dados externos — usado pra duas coisas:

  1. alimentar o catálogo: importar o schema (nomes de tabela/coluna, ou de
     coleção/campo no caso de Mongo) de um banco candidato como uma entrada
     de origem, sem precisar de amostra nenhuma;
  2. verificar: buscar, por uma chave (cpf/cnpj/placa), os registros
     correspondentes num banco candidato e comparar campo a campo contra a
     amostra — ver cronovazamento.verificacao.

Cobre os motores relacionais mais usados (Postgres, MySQL/MariaDB, SQL
Server, Oracle, SQLite) através de uma única implementação via SQLAlchemy, e
Mongo à parte via pymongo (documento, não tem "coluna" fixa). Fora do escopo:
bancos chave-valor/índice de busca puro (Redis, Elasticsearch, Cassandra...)
— não têm o modelo de "linha com campos nomeados" que a comparação usa.

Os drivers de cada motor (psycopg2, pymysql, pymssql, oracledb, pymongo) só
são importados dentro das funções que os usam — assim o pacote
`cronovazamento` continua sem dependência obrigatória pra quem só usa o
motor de datação/origem puro via CLI.
"""

from __future__ import annotations

from dataclasses import dataclass

MOTORES_RELACIONAIS = {
    "postgresql": {"dialeto": "postgresql+psycopg2", "porta_padrao": 5432, "rotulo": "PostgreSQL"},
    "mysql": {"dialeto": "mysql+pymysql", "porta_padrao": 3306, "rotulo": "MySQL"},
    "mariadb": {"dialeto": "mysql+pymysql", "porta_padrao": 3306, "rotulo": "MariaDB"},
    "mssql": {"dialeto": "mssql+pymssql", "porta_padrao": 1433, "rotulo": "SQL Server"},
    "oracle": {"dialeto": "oracle+oracledb", "porta_padrao": 1521, "rotulo": "Oracle"},
    "sqlite": {"dialeto": "sqlite", "porta_padrao": None, "rotulo": "SQLite (arquivo)"},
}
MOTORES_DOCUMENTO = {"mongodb": {"porta_padrao": 27017, "rotulo": "MongoDB"}}
MOTORES = {**{k: v["rotulo"] for k, v in MOTORES_RELACIONAIS.items()}, **{k: v["rotulo"] for k, v in MOTORES_DOCUMENTO.items()}}


@dataclass
class ConexaoInfo:
    motor: str
    banco: str
    host: str | None = None
    porta: int | None = None
    usuario: str | None = None
    senha: str | None = None
    caminho_arquivo: str | None = None  # só sqlite: caminho do arquivo .db/.sqlite


def _montar_url_sqlalchemy(info: ConexaoInfo) -> str:
    from sqlalchemy.engine import URL

    cfg = MOTORES_RELACIONAIS[info.motor]
    if info.motor == "sqlite":
        caminho = info.caminho_arquivo or info.banco
        return f"sqlite:///{caminho}"

    return URL.create(
        cfg["dialeto"],
        username=info.usuario,
        password=info.senha,
        host=info.host,
        port=info.porta or cfg["porta_padrao"],
        database=info.banco,
    )


def _motor_e_relacional(motor: str) -> bool:
    return motor in MOTORES_RELACIONAIS


def testar_conexao(info: ConexaoInfo) -> None:
    """Levanta exceção se não conseguir conectar; não retorna nada em caso de sucesso."""
    if _motor_e_relacional(info.motor):
        from sqlalchemy import create_engine, text

        engine = create_engine(_montar_url_sqlalchemy(info))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    elif info.motor == "mongodb":
        from pymongo import MongoClient

        cliente = _cliente_mongo(info)
        try:
            cliente.admin.command("ping")
        finally:
            cliente.close()
    else:
        raise ValueError(f"Motor desconhecido: {info.motor}")


def _cliente_mongo(info: ConexaoInfo):
    from pymongo import MongoClient

    if info.usuario:
        uri = f"mongodb://{info.usuario}:{info.senha}@{info.host}:{info.porta or 27017}/{info.banco}"
    else:
        uri = f"mongodb://{info.host}:{info.porta or 27017}/{info.banco}"
    return MongoClient(uri, serverSelectionTimeoutMS=8000)


def listar_tabelas(info: ConexaoInfo) -> list[str]:
    if _motor_e_relacional(info.motor):
        from sqlalchemy import create_engine, inspect

        engine = create_engine(_montar_url_sqlalchemy(info))
        try:
            return sorted(inspect(engine).get_table_names())
        finally:
            engine.dispose()
    elif info.motor == "mongodb":
        cliente = _cliente_mongo(info)
        try:
            return sorted(cliente[info.banco].list_collection_names())
        finally:
            cliente.close()
    raise ValueError(f"Motor desconhecido: {info.motor}")


def listar_colunas(info: ConexaoInfo, tabela: str, amostra_documentos: int = 25) -> list[str]:
    if _motor_e_relacional(info.motor):
        from sqlalchemy import create_engine, inspect

        engine = create_engine(_montar_url_sqlalchemy(info))
        try:
            return [c["name"] for c in inspect(engine).get_columns(tabela)]
        finally:
            engine.dispose()
    elif info.motor == "mongodb":
        # Mongo não tem schema fixo — infere os campos a partir de uma amostra de documentos
        cliente = _cliente_mongo(info)
        try:
            campos: set[str] = set()
            for doc in cliente[info.banco][tabela].find().limit(amostra_documentos):
                campos.update(k for k in doc.keys() if k != "_id")
            return sorted(campos)
        finally:
            cliente.close()
    raise ValueError(f"Motor desconhecido: {info.motor}")


def buscar_por_chave(
    info: ConexaoInfo, tabela: str, coluna_chave: str, valores: list[str], tamanho_lote: int = 500
) -> dict[str, dict]:
    """Busca as linhas cuja coluna_chave está em `valores`. Retorna um dict
    indexado pelo valor da chave (como string) -> linha (dict de colunas)."""
    valores_unicos = [v for v in dict.fromkeys(valores) if v]
    if not valores_unicos:
        return {}

    resultado: dict[str, dict] = {}

    if _motor_e_relacional(info.motor):
        from sqlalchemy import create_engine, text

        engine = create_engine(_montar_url_sqlalchemy(info))
        try:
            with engine.connect() as conn:
                for inicio in range(0, len(valores_unicos), tamanho_lote):
                    lote = valores_unicos[inicio : inicio + tamanho_lote]
                    marcadores = ", ".join(f":v{i}" for i in range(len(lote)))
                    parametros = {f"v{i}": v for i, v in enumerate(lote)}
                    consulta = text(f'SELECT * FROM "{tabela}" WHERE "{coluna_chave}" IN ({marcadores})')
                    try:
                        linhas = conn.execute(consulta, parametros).mappings().all()
                    except Exception:
                        # alguns dialetos (ex.: MySQL) não usam aspas duplas para identificador
                        consulta = text(f"SELECT * FROM {tabela} WHERE {coluna_chave} IN ({marcadores})")
                        linhas = conn.execute(consulta, parametros).mappings().all()
                    for linha in linhas:
                        resultado[str(linha[coluna_chave])] = dict(linha)
        finally:
            engine.dispose()
        return resultado

    if info.motor == "mongodb":
        cliente = _cliente_mongo(info)
        try:
            for inicio in range(0, len(valores_unicos), tamanho_lote):
                lote = valores_unicos[inicio : inicio + tamanho_lote]
                for doc in cliente[info.banco][tabela].find({coluna_chave: {"$in": lote}}):
                    doc.pop("_id", None)
                    resultado[str(doc[coluna_chave])] = doc
        finally:
            cliente.close()
        return resultado

    raise ValueError(f"Motor desconhecido: {info.motor}")
