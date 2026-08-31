"""Detecção de tipo de dado por coluna — arquitetura portada do projeto
misp-classifier (github.com/ulissescommit/misp-classifier): validadores
determinísticos ordenados do mais específico ao mais genérico, o primeiro que
casa vence, com uma confiança associada.

Usado para três coisas:
  1. sugerir o mapeamento de campos automaticamente, em vez de só manual;
  2. rotular a CATEGORIA do vazamento (dados pessoais, financeiro,
     credenciais/rede...) a partir dos tipos de dado predominantes;
  3. dar contexto a quem está triando uma amostra desconhecida.

Diferente do misp-classifier (focado em IOCs de CTI), aqui os tipos são os
que aparecem em vazamentos de dados brasileiros — CPF/CNPJ com dígito
verificador de verdade, telefone, placa, CEP — mas os validadores genéricos
reutilizáveis (e-mail, URL, IP, hash, cartão via Luhn) vieram do mesmo motor.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class TipoDado:
    nome: str
    categoria: str
    descricao: str
    validador: Callable[[str], bool]


# ---------------------------------------------------------------------------
# validadores
# ---------------------------------------------------------------------------


def _limpar_digitos(v: str) -> str:
    return re.sub(r"\D", "", v)


def _cpf_valido(v: str) -> bool:
    d = _limpar_digitos(v)
    if len(d) != 11 or d == d[0] * 11:
        return False

    def _dv(digitos: str, peso_inicial: int) -> int:
        soma = sum(int(x) * p for x, p in zip(digitos, range(peso_inicial, 1, -1)))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    return d[-2:] == f"{_dv(d[:9], 10)}{_dv(d[:10], 11)}"


def _cnpj_valido(v: str) -> bool:
    d = _limpar_digitos(v)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def _dv(digitos: str, pesos: list[int]) -> int:
        soma = sum(int(x) * p for x, p in zip(digitos, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    return d[-2:] == f"{_dv(d[:12], pesos1)}{_dv(d[:13], pesos2)}"


def _telefone_br_valido(v: str) -> bool:
    d = _limpar_digitos(v)
    if d.startswith("0055"):
        d = d[4:]
    elif d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) not in (10, 11):
        return False
    ddd = int(d[:2])
    if not (11 <= ddd <= 99):
        return False
    # celular (11 dígitos): terceiro dígito é sempre 9 desde a portabilidade;
    # fixo (10 dígitos): geralmente começa em 2-5. Sem isso, qualquer sequência
    # de 10-11 dígitos (inclusive CPF inválido por dígito verificador) colidia aqui.
    if len(d) == 11:
        return d[2] == "9"
    return d[2] in "2345"


def _placa_valida(v: str) -> bool:
    s = re.sub(r"[\s-]", "", v.strip().upper())
    return bool(re.match(r"^[A-Z]{3}\d{4}$", s)) or bool(re.match(r"^[A-Z]{3}\d[A-Z]\d{2}$", s))


def _cep_valido(v: str) -> bool:
    return len(_limpar_digitos(v)) == 8


def _hex_len(n: int) -> Callable[[str], bool]:
    pat = re.compile(rf"^[0-9a-fA-F]{{{n}}}$")
    return lambda v: bool(pat.match(v.strip()))


_RE_EMAIL = re.compile(r"^[^@\s]+@(?=.{1,253}$)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
_RE_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s]+$")


def _v_ip_any(v: str) -> bool:
    try:
        ipaddress.ip_address(v.strip())
        return True
    except ValueError:
        return False


def _luhn_ok(numero: str) -> bool:
    digitos = [int(c) for c in numero if c.isdigit()]
    if len(digitos) < 12:
        return False
    checksum = 0
    paridade = len(digitos) % 2
    for i, d in enumerate(digitos):
        if i % 2 == paridade:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _cartao_valido(v: str) -> bool:
    s = v.strip().replace(" ", "").replace("-", "")
    return s.isdigit() and 12 <= len(s) <= 19 and _luhn_ok(s)


def _nome_pessoa_provavel(v: str) -> bool:
    s = v.strip()
    if not (4 <= len(s) <= 80):
        return False
    palavras = s.split()
    if len(palavras) < 2:
        return False
    return all(re.match(r"^[A-Za-zÀ-ÿ'\.]+$", p) for p in palavras)


# ---------------------------------------------------------------------------
# registro de tipos — ordem = prioridade de desempate (mais específico primeiro)
# ---------------------------------------------------------------------------

TIPOS: list[TipoDado] = [
    TipoDado("sha256", "Credenciais/hash", "Hash SHA-256", _hex_len(64)),
    TipoDado("sha1", "Credenciais/hash", "Hash SHA-1", _hex_len(40)),
    TipoDado("md5", "Credenciais/hash", "Hash MD5", _hex_len(32)),
    TipoDado("cpf", "Dados pessoais", "CPF (dígito verificador válido)", _cpf_valido),
    TipoDado("cnpj", "Empresarial", "CNPJ (dígito verificador válido)", _cnpj_valido),
    TipoDado("cartao_credito", "Financeiro", "Número de cartão (Luhn)", _cartao_valido),
    TipoDado("cep", "Endereço", "CEP", _cep_valido),
    TipoDado("placa_veiculo", "Veículo", "Placa (padrão antigo ou Mercosul)", _placa_valida),
    TipoDado("telefone", "Contato", "Telefone brasileiro", _telefone_br_valido),
    TipoDado("email", "Contato", "E-mail", lambda v: bool(_RE_EMAIL.match(v.strip()))),
    TipoDado("url", "Rede", "URL", lambda v: bool(_RE_URL.match(v.strip()))),
    TipoDado("ip", "Rede", "Endereço IP", _v_ip_any),
    TipoDado("nome_pessoa", "Dados pessoais", "Provável nome completo de pessoa", _nome_pessoa_provavel),
]

FALLBACK = TipoDado("texto", "Não identificado", "Texto livre / não classificado", lambda v: True)

# tipos com valor idêntico a outro possível tipo (mesma lógica do misp-classifier
# para ip-src/ip-dst): aqui reservado para uso futuro, hoje nenhum tipo colide.
AMBIGUOS: dict[str, list[str]] = {}

# usado pra sugerir o mapeamento de campo lógico a partir do tipo detectado
TIPO_PARA_CAMPO_LOGICO: dict[str, str] = {
    "cpf": "cpf",
    "cnpj": "cnpj",
    "placa_veiculo": "placa",
    "nome_pessoa": "nome",
}


def detectar_tipo_valor(valor: str) -> tuple[TipoDado, list[str]]:
    """Retorna (tipo detectado, alternativas ambíguas) pela primeira regra que casar."""
    if not valor or not str(valor).strip():
        return FALLBACK, []
    for t in TIPOS:
        try:
            if t.validador(str(valor)):
                return t, AMBIGUOS.get(t.nome, [])
        except Exception:
            continue
    return FALLBACK, []


@dataclass
class ResultadoColuna:
    coluna: str
    tipo_predominante: str
    categoria: str
    confianca: float  # proporção dos valores amostrados que bateram no tipo predominante
    amostrados: int


def detectar_tipo_coluna(coluna: str, valores: list, limite_amostra: int = 50) -> ResultadoColuna:
    amostra = [v for v in valores[:limite_amostra] if v and str(v).strip()]
    if not amostra:
        return ResultadoColuna(coluna, FALLBACK.nome, FALLBACK.categoria, 0.0, 0)

    contagem: dict[str, int] = {}
    for v in amostra:
        tipo, _ = detectar_tipo_valor(str(v))
        contagem[tipo.nome] = contagem.get(tipo.nome, 0) + 1

    nome_predominante = max(contagem, key=contagem.get)
    confianca = contagem[nome_predominante] / len(amostra)
    tipos_por_nome = {t.nome: t for t in TIPOS} | {FALLBACK.nome: FALLBACK}
    tipo = tipos_por_nome[nome_predominante]
    return ResultadoColuna(coluna, tipo.nome, tipo.categoria, round(confianca, 3), len(amostra))


@dataclass
class RelatorioClassificacao:
    colunas: list[ResultadoColuna]
    categoria_predominante: str
    contagem_categorias: dict[str, int]

    def sugestoes_mapeamento(self) -> dict[str, str]:
        """campo_logico -> nome da coluna, pra pré-selecionar o formulário de
        mapeamento. Só sugere quando a confiança é razoável (evita sugerir
        'nome' pra uma coluna que só por acaso bateu em 2-3 valores)."""
        sugestoes: dict[str, str] = {}
        for r in self.colunas:
            campo = TIPO_PARA_CAMPO_LOGICO.get(r.tipo_predominante)
            if campo and campo not in sugestoes and r.confianca >= 0.6:
                sugestoes[campo] = r.coluna
        return sugestoes


def classificar_amostra(colunas: list[str], linhas: list[dict], limite_amostra: int = 50) -> RelatorioClassificacao:
    resultados = [
        detectar_tipo_coluna(c, [linha.get(c, "") for linha in linhas], limite_amostra) for c in colunas
    ]
    contagem_categorias: dict[str, int] = {}
    for r in resultados:
        if r.tipo_predominante == FALLBACK.nome:
            continue
        contagem_categorias[r.categoria] = contagem_categorias.get(r.categoria, 0) + 1
    categoria_predominante = (
        max(contagem_categorias, key=contagem_categorias.get) if contagem_categorias else "Não identificado"
    )
    return RelatorioClassificacao(
        colunas=resultados,
        categoria_predominante=categoria_predominante,
        contagem_categorias=contagem_categorias,
    )
