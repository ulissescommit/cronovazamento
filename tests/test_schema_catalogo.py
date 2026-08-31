import unittest

from cronovazamento.catalogo import Catalogo, VazamentoConhecido
from cronovazamento.schema import assinatura, normalizar_campo, similaridade_jaccard


class TestSchema(unittest.TestCase):
    def test_normalizar_campo(self):
        self.assertEqual(normalizar_campo("Data Nascimento"), "data_nascimento")
        self.assertEqual(normalizar_campo("DT_NASC"), "dt_nasc")
        self.assertEqual(normalizar_campo("E-mail"), "e_mail")

    def test_similaridade_jaccard(self):
        a = assinatura(["CPF", "NOME", "EMAIL"])
        b = assinatura(["cpf", "nome", "telefone"])
        sim = similaridade_jaccard(a, b)
        self.assertTrue(0 < sim < 1)


class TestCatalogo(unittest.TestCase):
    def test_identificar_origem_ranking(self):
        catalogo = Catalogo()
        catalogo.adicionar(VazamentoConhecido(id="a", nome="A", campos=["CPF", "NOME", "EMAIL"]))
        catalogo.adicionar(VazamentoConhecido(id="b", nome="B", campos=["PLACA", "UF", "MODELO"]))

        candidatos = catalogo.identificar_origem(["cpf", "nome", "email", "telefone"], algoritmos=["jaccard"])
        melhor = candidatos[0]
        self.assertEqual(melhor.entrada.id, "a")
        self.assertGreater(melhor.score_medio, 0)
        self.assertIn("jaccard", melhor.scores)


if __name__ == "__main__":
    unittest.main()
