import unittest

from cronovazamento.verificacao import verificar


class TestVerificacao(unittest.TestCase):
    def setUp(self):
        self.linhas_amostra = [
            {"CPF": "111", "NOME": "Maria Souza"},
            {"CPF": "222", "NOME": "Joao Silva"},
            {"CPF": "333", "NOME": "Carlos Pereira"},
        ]
        self.mapeamento_amostra = {"cpf": "CPF", "nome": "NOME"}
        self.mapeamento_externo = {"cpf": "cpf", "nome": "nome_completo"}

    def test_registro_nao_encontrado(self):
        linhas_externas = {"111": {"cpf": "111", "nome_completo": "Maria Souza"}}
        resultado = verificar(
            self.linhas_amostra, self.mapeamento_amostra, linhas_externas, self.mapeamento_externo, "cpf"
        )
        self.assertEqual(resultado.total, 3)
        self.assertEqual(resultado.encontrados, 1)
        registro_222 = next(r for r in resultado.registros if r.chave == "222")
        self.assertFalse(registro_222.encontrado)

    def test_campo_identico_nao_diverge(self):
        linhas_externas = {"111": {"cpf": "111", "nome_completo": "Maria Souza"}}
        resultado = verificar(
            self.linhas_amostra, self.mapeamento_amostra, linhas_externas, self.mapeamento_externo, "cpf"
        )
        registro = next(r for r in resultado.registros if r.chave == "111")
        self.assertTrue(registro.encontrado)
        self.assertFalse(registro.tem_divergencia)
        self.assertEqual(resultado.percentual_divergente, 0.0)

    def test_campo_diferente_diverge(self):
        linhas_externas = {"111": {"cpf": "111", "nome_completo": "Maria Souza Lima"}}
        resultado = verificar(
            self.linhas_amostra, self.mapeamento_amostra, linhas_externas, self.mapeamento_externo, "cpf",
            algoritmos_string=["exato"],
        )
        registro = next(r for r in resultado.registros if r.chave == "111")
        self.assertTrue(registro.tem_divergencia)
        self.assertEqual(resultado.divergentes, 1)
        self.assertEqual(resultado.percentual_divergente, 100.0)

    def test_algoritmo_fuzzy_reduz_falsa_divergencia(self):
        linhas_externas = {"111": {"cpf": "111", "nome_completo": "MARIA SOUZA"}}  # só caixa difere
        resultado = verificar(
            self.linhas_amostra, self.mapeamento_amostra, linhas_externas, self.mapeamento_externo, "cpf",
            algoritmos_string=["levenshtein"],
        )
        registro = next(r for r in resultado.registros if r.chave == "111")
        self.assertFalse(registro.tem_divergencia)


if __name__ == "__main__":
    unittest.main()
