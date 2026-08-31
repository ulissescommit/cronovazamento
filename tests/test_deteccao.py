import unittest

from cronovazamento.deteccao import classificar_amostra, detectar_tipo_coluna, detectar_tipo_valor


class TestDetectarTipoValor(unittest.TestCase):
    def test_cpf_valido(self):
        # CPF sintético com dígito verificador válido (não corresponde a pessoa real)
        tipo, ambiguos = detectar_tipo_valor("111.444.777-35")
        self.assertEqual(tipo.nome, "cpf")

    def test_cpf_invalido_cai_pra_texto_ou_outro(self):
        tipo, _ = detectar_tipo_valor("111.444.777-99")
        self.assertNotEqual(tipo.nome, "cpf")

    def test_cnpj_valido(self):
        tipo, _ = detectar_tipo_valor("11.222.333/0001-81")
        self.assertEqual(tipo.nome, "cnpj")

    def test_email(self):
        tipo, _ = detectar_tipo_valor("fulano@exemplo.com")
        self.assertEqual(tipo.nome, "email")

    def test_placa_antiga_e_mercosul(self):
        self.assertEqual(detectar_tipo_valor("ABC1234")[0].nome, "placa_veiculo")
        self.assertEqual(detectar_tipo_valor("ABC1D23")[0].nome, "placa_veiculo")

    def test_hash_sha256_por_comprimento(self):
        tipo, _ = detectar_tipo_valor("a" * 64)
        self.assertEqual(tipo.nome, "sha256")

    def test_nome_pessoa(self):
        tipo, _ = detectar_tipo_valor("Maria Souza Lima")
        self.assertEqual(tipo.nome, "nome_pessoa")

    def test_fallback_texto(self):
        tipo, _ = detectar_tipo_valor("xyz123abc")
        self.assertEqual(tipo.nome, "texto")

    def test_valor_vazio(self):
        tipo, _ = detectar_tipo_valor("")
        self.assertEqual(tipo.nome, "texto")


class TestDetectarTipoColuna(unittest.TestCase):
    def test_coluna_predominantemente_cpf(self):
        valores = ["111.444.777-35", "111.444.777-35", "não é cpf"]
        r = detectar_tipo_coluna("CPF", valores)
        self.assertEqual(r.tipo_predominante, "cpf")
        self.assertAlmostEqual(r.confianca, 2 / 3, places=2)

    def test_coluna_vazia(self):
        r = detectar_tipo_coluna("X", [])
        self.assertEqual(r.amostrados, 0)


class TestClassificarAmostra(unittest.TestCase):
    def test_categoria_predominante_dados_pessoais(self):
        colunas = ["CPF", "NOME"]
        linhas = [
            {"CPF": "111.444.777-35", "NOME": "Maria Souza Lima"},
            {"CPF": "111.444.777-35", "NOME": "Joao Nascimento"},
        ]
        relatorio = classificar_amostra(colunas, linhas)
        self.assertEqual(relatorio.categoria_predominante, "Dados pessoais")

    def test_sugestoes_mapeamento(self):
        colunas = ["CPF", "NOME"]
        linhas = [{"CPF": "111.444.777-35", "NOME": "Maria Souza Lima"}] * 5
        relatorio = classificar_amostra(colunas, linhas)
        sugestoes = relatorio.sugestoes_mapeamento()
        self.assertEqual(sugestoes.get("cpf"), "CPF")
        self.assertEqual(sugestoes.get("nome"), "NOME")


if __name__ == "__main__":
    unittest.main()
