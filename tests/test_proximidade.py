import unittest

from cronovazamento.proximidade import obter_conjunto, obter_string
from cronovazamento.schema import assinatura


class TestAlgoritmosConjunto(unittest.TestCase):
    def test_jaccard_identico(self):
        a = assinatura(["CPF", "NOME"])
        self.assertEqual(obter_conjunto("jaccard").comparar(a, a), 1.0)

    def test_dice_maior_ou_igual_a_jaccard(self):
        a = assinatura(["CPF", "NOME", "EMAIL"])
        b = assinatura(["CPF", "NOME", "TELEFONE"])
        jac = obter_conjunto("jaccard").comparar(a, b)
        dice = obter_conjunto("dice").comparar(a, b)
        self.assertGreaterEqual(dice, jac)

    def test_cosseno_tfidf_pesa_campo_raro(self):
        amostra = assinatura(["cpf", "nome", "campo_exclusivo_do_sistema_x"])
        candidato_com_raro = assinatura(["cpf", "nome", "campo_exclusivo_do_sistema_x"])
        candidato_comum = assinatura(["cpf", "nome", "endereco"])
        corpus = [
            assinatura(["cpf", "nome"]),
            assinatura(["cpf", "nome", "endereco"]),
            assinatura(["cpf", "nome", "telefone"]),
            candidato_com_raro,
        ]
        alg = obter_conjunto("cosseno_tfidf")
        score_raro = alg.comparar(amostra, candidato_com_raro, corpus)
        score_comum = alg.comparar(amostra, candidato_comum, corpus)
        self.assertGreater(score_raro, score_comum)

    def test_conjuntos_vazios(self):
        vazio = assinatura([])
        self.assertEqual(obter_conjunto("jaccard").comparar(vazio, vazio), 0.0)
        self.assertEqual(obter_conjunto("dice").comparar(vazio, vazio), 0.0)


class TestAlgoritmosString(unittest.TestCase):
    def test_exato(self):
        alg = obter_string("exato")
        self.assertEqual(alg.comparar("Maria Souza", "maria souza"), 1.0)
        self.assertEqual(alg.comparar("Maria Souza", "Maria Souza Lima"), 0.0)

    def test_levenshtein_tolera_pequeno_erro(self):
        alg = obter_string("levenshtein")
        score = alg.comparar("Mariana Souza", "Mariana Sousa")
        self.assertGreater(score, 0.85)
        self.assertLess(score, 1.0)

    def test_jaro_winkler_favorece_prefixo_comum(self):
        alg = obter_string("jaro_winkler")
        score_prefixo = alg.comparar("Alexandre Silva", "Alexandre Silvva")
        score_sufixo = alg.comparar("Alexandre Silva", "Blexandre Silva")
        self.assertGreater(score_prefixo, score_sufixo)

    def test_fonetico_agrupa_variacao_de_grafia(self):
        alg = obter_string("fonetico")
        self.assertEqual(alg.comparar("Felipe", "Phelippe"), 1.0)
        self.assertEqual(alg.comparar("Souza", "Sousa"), 1.0)

    def test_strings_vazias(self):
        self.assertEqual(obter_string("exato").comparar("", ""), 0.0)
        self.assertEqual(obter_string("levenshtein").comparar("", ""), 1.0)


if __name__ == "__main__":
    unittest.main()
