import unittest
from datetime import date

from cronovazamento.evidencias import Direcao, Evidencia, Forca, estimar_janela


def _ev(direcao, data, forca=Forca.FORTE, just="teste"):
    return Evidencia(
        chave="teste",
        tipo_evento="teste",
        direcao=direcao,
        data_referencia=data,
        forca=forca,
        justificativa=just,
    )


class TestEstimarJanela(unittest.TestCase):
    def test_janela_simples(self):
        evidencias = [
            _ev(Direcao.POS, date(2019, 1, 1)),
            _ev(Direcao.ANTES, date(2020, 1, 1)),
        ]
        resultado = estimar_janela(evidencias)
        self.assertEqual(resultado.limite_inferior, date(2019, 1, 1))
        self.assertEqual(resultado.limite_superior, date(2020, 1, 1))
        self.assertTrue(resultado.consistente)

    def test_janela_usa_limite_mais_apertado(self):
        evidencias = [
            _ev(Direcao.POS, date(2018, 1, 1)),
            _ev(Direcao.POS, date(2020, 1, 1)),  # deve prevalecer (mais recente)
            _ev(Direcao.ANTES, date(2022, 1, 1)),
            _ev(Direcao.ANTES, date(2021, 1, 1)),  # deve prevalecer (mais antiga)
        ]
        resultado = estimar_janela(evidencias)
        self.assertEqual(resultado.limite_inferior, date(2020, 1, 1))
        self.assertEqual(resultado.limite_superior, date(2021, 1, 1))

    def test_conflito_detectado(self):
        evidencias = [
            _ev(Direcao.POS, date(2021, 1, 1)),
            _ev(Direcao.ANTES, date(2019, 1, 1)),
        ]
        resultado = estimar_janela(evidencias)
        self.assertFalse(resultado.consistente)
        self.assertEqual(len(resultado.conflitos), 1)

    def test_evidencia_fraca_nao_aperta_janela(self):
        evidencias = [
            _ev(Direcao.ANTES, date(2019, 1, 1), forca=Forca.FRACA),
        ]
        resultado = estimar_janela(evidencias)
        self.assertIsNone(resultado.limite_superior)
        self.assertEqual(len(resultado.evidencias_fracas), 1)


if __name__ == "__main__":
    unittest.main()
