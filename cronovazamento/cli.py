from __future__ import annotations

import argparse
import json
import sys

from .catalogo import Catalogo, VazamentoConhecido
from .comparador import Amostra, analisar
from .eventos import EventosEmpresa, EventosPessoa, EventosVeiculo
from .proximidade import ALGORITMOS_CONJUNTO, ALGORITMOS_STRING


def _parse_mapeamento(pares: list[str]) -> dict[str, str]:
    mapeamento = {}
    for par in pares:
        if "=" not in par:
            raise argparse.ArgumentTypeError(f"mapeamento inválido: '{par}' (use campo=coluna)")
        campo, coluna = par.split("=", 1)
        mapeamento[campo.strip()] = coluna.strip()
    return mapeamento


def cmd_analisar(args: argparse.Namespace) -> int:
    amostra = Amostra.carregar_csv(args.amostra, delimitador=args.delimitador)
    mapeamento = _parse_mapeamento(args.mapa or [])

    eventos_pessoa = EventosPessoa.carregar(args.eventos_pessoa) if args.eventos_pessoa else None
    eventos_empresa = EventosEmpresa.carregar(args.eventos_empresa) if args.eventos_empresa else None
    eventos_veiculo = EventosVeiculo.carregar(args.eventos_veiculo) if args.eventos_veiculo else None
    catalogo = Catalogo.carregar(args.catalogo) if args.catalogo else None

    relatorio = analisar(
        amostra,
        mapeamento,
        eventos_pessoa=eventos_pessoa,
        eventos_empresa=eventos_empresa,
        eventos_veiculo=eventos_veiculo,
        catalogo=catalogo,
        algoritmos_registro=args.algoritmo_registro or ["exato"],
        algoritmos_origem=args.algoritmo_origem or None,
        limiar_fuzzy=args.limiar,
    )

    print(relatorio.texto())

    if args.saida:
        dados = {
            "amostra": relatorio.amostra,
            "n_linhas": relatorio.n_linhas,
            "janela": {
                "limite_inferior": relatorio.janela.limite_inferior.isoformat()
                if relatorio.janela.limite_inferior
                else None,
                "limite_superior": relatorio.janela.limite_superior.isoformat()
                if relatorio.janela.limite_superior
                else None,
                "consistente": relatorio.janela.consistente,
            },
            "evidencias": [
                {
                    "chave": e.chave,
                    "tipo_evento": e.tipo_evento,
                    "direcao": e.direcao.value,
                    "data_referencia": e.data_referencia.isoformat(),
                    "forca": e.forca.value,
                    "justificativa": e.justificativa,
                    "algoritmo": e.algoritmo,
                    "score": e.score,
                }
                for e in relatorio.evidencias
            ],
            "origem": (
                {
                    "algoritmos": relatorio.origem.algoritmos,
                    "candidatos": [
                        {
                            "id": c.entrada.id,
                            "nome": c.entrada.nome,
                            "score_medio": c.score_medio,
                            "scores": c.scores,
                        }
                        for c in relatorio.origem.candidatos
                    ],
                }
                if relatorio.origem
                else None
            ),
        }
        with open(args.saida, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"\nRelatório salvo em {args.saida}")

    return 0


def cmd_catalogar(args: argparse.Namespace) -> int:
    amostra = Amostra.carregar_csv(args.amostra, delimitador=args.delimitador)
    catalogo = Catalogo.carregar(args.catalogo)
    catalogo.adicionar(
        VazamentoConhecido(
            id=args.id,
            nome=args.nome,
            campos=amostra.colunas,
            fonte_suspeita=args.fonte,
            data_conhecida=args.data,
            observacoes=args.observacoes,
        )
    )
    catalogo.salvar(args.catalogo)
    print(f"Adicionado '{args.nome}' ({len(amostra.colunas)} campos) ao catálogo {args.catalogo}")
    return 0


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cronovazamento", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_analisar = sub.add_parser("analisar", help="Estima janela temporal e origem de uma amostra")
    p_analisar.add_argument("--amostra", required=True, help="CSV da amostra vazada")
    p_analisar.add_argument("--delimitador", default=",")
    p_analisar.add_argument(
        "--mapa",
        action="append",
        metavar="campo=coluna",
        help="Mapeia campo lógico (cpf, nome, cnpj, socio, participacao, placa, "
        "proprietario, status_obito) para o nome da coluna na amostra. Repetível.",
    )
    p_analisar.add_argument("--eventos-pessoa", help="JSON com eventos de pessoa (nascimento/obito/mudanca_nome)")
    p_analisar.add_argument("--eventos-empresa", help="JSON com eventos de empresa (alteracao_societaria)")
    p_analisar.add_argument("--eventos-veiculo", help="JSON com eventos de veículo (transferencia_propriedade)")
    p_analisar.add_argument("--catalogo", help="JSON com catálogo de vazamentos conhecidos (fingerprint de origem)")
    p_analisar.add_argument(
        "--algoritmo-registro",
        action="append",
        choices=list(ALGORITMOS_STRING.keys()),
        help=f"Algoritmo(s) de proximidade para casar nome/sócio/proprietário. Repetível. "
        f"Opções: {', '.join(ALGORITMOS_STRING.keys())}. Padrão: exato.",
    )
    p_analisar.add_argument(
        "--algoritmo-origem",
        action="append",
        choices=list(ALGORITMOS_CONJUNTO.keys()),
        help=f"Algoritmo(s) de proximidade para o fingerprint de origem. Repetível. "
        f"Opções: {', '.join(ALGORITMOS_CONJUNTO.keys())}. Padrão: todos.",
    )
    p_analisar.add_argument(
        "--limiar", type=float, default=0.85, help="Score mínimo (0-1) para considerar um casamento fuzzy válido"
    )
    p_analisar.add_argument("--saida", help="Caminho para salvar o relatório em JSON")
    p_analisar.set_defaults(func=cmd_analisar)

    p_catalogar = sub.add_parser("catalogar", help="Adiciona a assinatura de campos de uma amostra ao catálogo")
    p_catalogar.add_argument("--amostra", required=True)
    p_catalogar.add_argument("--delimitador", default=",")
    p_catalogar.add_argument("--catalogo", required=True)
    p_catalogar.add_argument("--id", required=True)
    p_catalogar.add_argument("--nome", required=True)
    p_catalogar.add_argument("--fonte")
    p_catalogar.add_argument("--data")
    p_catalogar.add_argument("--observacoes")
    p_catalogar.set_defaults(func=cmd_catalogar)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = montar_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
