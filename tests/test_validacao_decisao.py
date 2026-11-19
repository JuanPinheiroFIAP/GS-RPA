"""Cenários de DECISÃO: regras de validação (aceita, corrige ou rejeita) e de prioridade/alerta."""
from __future__ import annotations

import unittest

from base import LUGARES, relato  # noqa: F401  (base ajusta o sys.path)
from rpa_relatos.decisao import gerar_alertas, prioridade
from rpa_relatos.validacao import validar

CATALOGO = {l["id"]: l for l in LUGARES}


class TestValidacao(unittest.TestCase):
    def v(self, **campos):
        return validar(relato(1, **campos), CATALOGO, "sal")

    def test_relato_valido_e_aceito_sem_dado_pessoal(self):
        r = self.v()
        self.assertTrue(r.ok)
        self.assertNotIn("autor_email", r.registro)
        self.assertNotIn("autor_nome", r.registro)
        self.assertEqual(len(r.registro["autor_hash"]), 16)

    def test_rejeicoes_com_motivo_fixo(self):
        casos = {
            "nota_fora_da_faixa": {"nota": 9},
            "nota_nao_numerica": {"nota": "cinco"},
            "lugar_inexistente": {"lugar_id": "lugar-9999"},
            "necessidade_invalida": {"necessidade": "outro"},
            "sem_data_hora": {"criado_em": None},
            "data_invalida": {"criado_em": "ontem"},
            "tipo_invalido": {"tipo": "neutro"},
            "relato_id_ausente": {"relato_id": ""},
        }
        for motivo, campos in casos.items():
            with self.subTest(motivo=motivo):
                r = self.v(**campos)
                self.assertFalse(r.ok)
                self.assertEqual(r.motivo, motivo)

    def test_recupera_em_vez_de_rejeitar(self):
        r = self.v(necessidade=" Vision", nota="4", criado_em="2026-11-16T10:00:00")
        self.assertTrue(r.ok)
        self.assertEqual(r.registro["necessidade"], "vision")
        self.assertEqual(r.registro["nota"], 4)
        self.assertEqual(sorted(r.correcoes), ["fuso_assumido_brasilia", "necessidade_normalizada", "nota_convertida_para_inteiro"])

    def test_email_invalido_nao_derruba_o_relato(self):
        r = self.v(autor_email="pessoa1example.com")
        self.assertTrue(r.ok)
        self.assertIsNone(r.registro["autor_hash"])
        self.assertIn("email_invalido_autor_descartado", r.avisos)

    def test_dado_pessoal_digitado_no_texto_e_removido(self):
        r = self.v(texto="Falem comigo em joao@mail.com ou (11) 98765-4321, CPF 123.456.789-09.")
        self.assertTrue(r.ok)
        for sensivel in ("joao@mail.com", "98765", "123.456.789-09"):
            self.assertNotIn(sensivel, r.registro["texto"])
        self.assertIn("dado_pessoal_removido_do_texto", r.avisos)

    def test_mesmo_autor_gera_mesmo_hash_e_sal_muda_o_hash(self):
        a, b = self.v(), self.v()
        self.assertEqual(a.registro["autor_hash"], b.registro["autor_hash"])
        outro = validar(relato(1), CATALOGO, "outro-sal")
        self.assertNotEqual(a.registro["autor_hash"], outro.registro["autor_hash"])


class TestDecisao(unittest.TestCase):
    def test_prioridade(self):
        casos = [
            ({"tipo": "elogio", "nota": 5, "fotos": 0}, "baixa"),
            ({"tipo": "barreira", "nota": 1, "fotos": 0}, "alta"),
            ({"tipo": "barreira", "nota": 2, "fotos": 0}, "alta"),
            ({"tipo": "barreira", "nota": 3, "fotos": 0}, "media"),
            ({"tipo": "barreira", "nota": 3, "fotos": 2}, "alta"),   # evidência em foto escala a prioridade
            ({"tipo": "barreira", "nota": 5, "fotos": 0}, "baixa"),  # barreira com nota 5: provável erro de preenchimento
        ]
        for relato_, esperado in casos:
            with self.subTest(**relato_):
                self.assertEqual(prioridade(relato_), esperado)

    def _com_prioridade(self, n: int, **campos):
        r = validar(relato(n, **campos), CATALOGO, "sal").registro
        r["prioridade"] = prioridade(r)
        return r

    def test_alerta_so_com_tres_barreiras_do_mesmo_lugar_e_necessidade(self):
        dois = [self._com_prioridade(i) for i in (1, 2)]
        self.assertEqual(gerar_alertas(dois, CATALOGO), [])
        tres = dois + [self._com_prioridade(3)]
        alertas = gerar_alertas(tres, CATALOGO)
        self.assertEqual(len(alertas), 1)
        a = alertas[0]
        self.assertEqual((a["lugar_id"], a["necessidade"], a["severidade"], a["status"]), ("cafe-aurora", "mobility", "alta", "pendente_revisao"))
        self.assertEqual(len(a["evidencias"]), 3)

    def test_necessidades_diferentes_nao_somam(self):
        mistos = [self._com_prioridade(1), self._com_prioridade(2, necessidade="vision"), self._com_prioridade(3, necessidade="hearing")]
        self.assertEqual(gerar_alertas(mistos, CATALOGO), [])

    def test_elogio_nao_conta_para_alerta(self):
        itens = [self._com_prioridade(i, tipo="elogio", nota=5) for i in (1, 2, 3, 4)]
        self.assertEqual(gerar_alertas(itens, CATALOGO), [])

    def test_relatos_antigos_fora_da_janela_nao_contam(self):
        antigos = [self._com_prioridade(i, dia="2026-10-01") for i in (1, 2)]
        novo = [self._com_prioridade(3, dia="2026-11-16")]
        self.assertEqual(gerar_alertas(antigos + novo, CATALOGO), [])


if __name__ == "__main__":
    unittest.main()
