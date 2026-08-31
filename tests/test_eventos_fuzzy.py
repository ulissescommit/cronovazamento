import unittest
from datetime import date

from cronovazamento.eventos import EventosPessoa
from cronovazamento.evidencias import Direcao, Forca


class TestCasamentoFuzzyPessoa(unittest.TestCase):
    def setUp(self):
        self.mapeamento = {"cpf": "CPF", "nome": "NOME"}
        self.eventos = EventosPessoa(
            eventos=[
                {
                    "cpf": "1",
                    "tipo": "mudanca_nome",
                    "data": "2020-01-01",
                    "nome_anterior": "Maria Souza",
                    "nome_novo": "Maria Souza Lima",
                }
            ]
        )

    def test_exato_nao_casa_com_erro_de_digitacao(self):
        linha = {"CPF": "1", "NOME": "Maria Souza Lma"}  # erro de digitação
        evidencias = self.eventos.gerar_evidencias(linha, self.mapeamento, algoritmos=["exato"])
        self.assertEqual(evidencias, [])

    def test_fuzzy_casa_com_erro_de_digitacao_e_vira_evidencia_fraca(self):
        linha = {"CPF": "1", "NOME": "Maria Souza Lma"}  # erro de digitação
        evidencias = self.eventos.gerar_evidencias(
            linha, self.mapeamento, algoritmos=["levenshtein"], limiar=0.85
        )
        self.assertEqual(len(evidencias), 1)
        ev = evidencias[0]
        self.assertEqual(ev.direcao, Direcao.POS)
        self.assertEqual(ev.data_referencia, date(2020, 1, 1))
        self.assertEqual(ev.forca, Forca.FRACA)  # score < 0.97 -> sempre fraca
        self.assertEqual(ev.algoritmo, "levenshtein")
        self.assertIsNotNone(ev.score)
        self.assertLess(ev.score, 0.97)

    def test_fuzzy_quase_exato_respeita_forca_declarada(self):
        # só acento difere -> normalizar_nome já ignora acento, então isso na
        # prática cai em score 1.0 (equivalente a exato) mesmo via levenshtein
        linha = {"CPF": "1", "NOME": "María Souza Lima"}
        evidencias = self.eventos.gerar_evidencias(linha, self.mapeamento, algoritmos=["levenshtein"])
        self.assertEqual(len(evidencias), 1)
        self.assertEqual(evidencias[0].forca, Forca.FORTE)

    def test_abaixo_do_limiar_nao_gera_evidencia(self):
        linha = {"CPF": "1", "NOME": "Outra Pessoa Completamente Diferente"}
        evidencias = self.eventos.gerar_evidencias(linha, self.mapeamento, algoritmos=["levenshtein"])
        self.assertEqual(evidencias, [])


if __name__ == "__main__":
    unittest.main()
