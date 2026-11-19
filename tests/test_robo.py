"""Cenários de SUCESSO e de FALHA do robô, de ponta a ponta, com pastas temporárias."""
from __future__ import annotations

import json
import unittest
from unittest import mock

from base import AmbienteRPA, relato
from rpa_relatos.robo import FATAL, OK, PARCIAL, executar


class TestSucesso(AmbienteRPA):
    def test_processa_valida_e_grava_saidas_para_o_mvp(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(i) for i in (1, 2, 3)] + [relato(4, tipo="elogio", nota=5)])
        self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 4)
        alertas = self.saida("alertas_prioritarios.json")["alertas"]
        self.assertEqual([a["alerta_id"] for a in alertas], ["cafe-aurora|mobility"])
        resumo = self.saida("resumo_lugares.json")["lugares"]
        self.assertEqual(resumo["cafe-aurora"]["por_necessidade"]["mobility"]["relatos"], 4)
        self.assertTrue(resumo["cafe-aurora"]["tem_alerta"])
        self.assertEqual(resumo["cine-lumiar"]["total_relatos"], 0)

    def test_dois_lotes_so_o_novo_entra_e_reexecutar_nao_duplica(self):
        self.escrever_relatos("relatos_2026-11-15.jsonl", [relato(i, dia="2026-11-15") for i in (1, 2)])
        self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 2)

        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(i) for i in (1, 2, 3)])  # lote 2
        executar(self.cfg)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 5)
        self.assertEqual(self.saida("relatorio_execucao.json")["arquivos"]["ignorados_ja_processados"], 1)

        antes = (self.cfg.saida / "relatos_validados.json").read_bytes()
        executar(self.cfg)  # nada novo: mesma saída, byte a byte
        self.assertEqual((self.cfg.saida / "relatos_validados.json").read_bytes(), antes)
        rel = self.saida("relatorio_execucao.json")
        self.assertEqual((rel["arquivos"]["processados"], rel["relatos_aceitos_nesta_execucao"], rel["alertas_novos"]), (0, 0, 0))

    def test_limite_de_arquivos_simula_lotes(self):
        for dia in ("2026-11-14", "2026-11-15", "2026-11-16"):
            self.escrever_relatos(f"relatos_{dia}.jsonl", [relato(1, dia=dia)])
        executar(self.cfg, max_arquivos=2)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 2)
        executar(self.cfg, max_arquivos=2)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 3)

    def test_arquivo_reeditado_substitui_o_anterior_sem_fantasmas(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(i) for i in (1, 2, 3)])
        executar(self.cfg)
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1)])
        executar(self.cfg)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 1)
        self.assertEqual(self.saida("alertas_prioritarios.json")["total"], 0)

    def test_lgpd_nenhuma_saida_nem_log_tem_nome_ou_email(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(i) for i in (1, 2, 3)])
        executar(self.cfg)
        tudo = self.texto_de_todos_os_logs() + "".join(p.read_text(encoding="utf-8") for p in self.cfg.saida.glob("*"))
        for sensivel in ("Pessoa Sintetica", "example.com", "autor_email", "autor_nome"):
            self.assertNotIn(sensivel, tudo)

    def test_auditoria_tem_data_hora_e_contagens(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1), relato(2, nota=9)])
        executar(self.cfg)
        eventos = [json.loads(l) for l in (self.cfg.logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["evento"] for e in eventos][0], "inicio")
        fim = eventos[-1]
        self.assertEqual((fim["evento"], fim["linhas_lidas"], fim["relatos_aceitos_nesta_execucao"]), ("fim", 2, 1))
        self.assertTrue(all("ts" in e and "execucao" in e for e in eventos))


class TestFalhas(AmbienteRPA):
    def test_linhas_ruins_vao_para_quarentena_e_o_resto_segue(self):
        arquivo = self.cfg.pasta_relatos / "relatos_2026-11-16.jsonl"
        linhas = [json.dumps(relato(1)), "{isto nao e json", json.dumps(relato(2, nota="N/A")), json.dumps(relato(3)), json.dumps(relato(3)), "[1, 2]"]
        arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        self.assertEqual(executar(self.cfg), OK)
        rel = self.saida("relatorio_execucao.json")
        self.assertEqual(rel["relatos_aceitos_nesta_execucao"], 2)
        self.assertEqual(rel["rejeitados_por_motivo"], {"duplicado": 1, "linha_json_invalida": 1, "nota_nao_numerica": 1, "registro_nao_e_objeto": 1})
        quarentena = [json.loads(l) for l in (self.cfg.saida / "quarentena.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(quarentena), 4)
        self.assertTrue(all(set(q) == {"arquivo", "linha", "relato_id", "motivo"} for q in quarentena))

    def test_arquivo_vazio_ou_com_codificacao_quebrada_nao_para_os_outros(self):
        (self.cfg.pasta_relatos / "relatos_2026-11-14.jsonl").write_bytes(b"")
        (self.cfg.pasta_relatos / "relatos_2026-11-15.jsonl").write_bytes(b"\xff\xfe\x00\x80 lixo")
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1)])
        self.assertEqual(executar(self.cfg), PARCIAL)  # falha parcial NUNCA vira sucesso silencioso
        rel = self.saida("relatorio_execucao.json")
        self.assertEqual(rel["status"], "parcial")
        self.assertEqual({f["motivo"] for f in rel["arquivos"]["com_falha"]}, {"arquivo_vazio", "codificacao_invalida"})
        self.assertEqual(self.saida("relatos_validados.json")["total"], 1)

    def test_arquivo_que_falhou_e_reprocessado_quando_for_corrigido(self):
        arquivo = self.cfg.pasta_relatos / "relatos_2026-11-16.jsonl"
        arquivo.write_bytes(b"")
        self.assertEqual(executar(self.cfg), PARCIAL)
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1)])
        self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 1)

    def test_catalogo_mais_recente_quebrado_cai_para_o_anterior(self):
        (self.cfg.pasta_lugares / "lugares_2026-11-17.jsonl").write_text("{quebrado\n", encoding="utf-8")
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1)])
        self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatorio_execucao.json")["catalogo"]["arquivo"], "lugares_2026-11-16.jsonl")

    def test_sem_catalogo_e_falha_fatal_e_registrada(self):
        (self.cfg.pasta_lugares / "lugares_2026-11-16.jsonl").unlink()
        self.assertEqual(executar(self.cfg), FATAL)
        self.assertIn("catalogo_indisponivel", (self.cfg.logs / "auditoria.jsonl").read_text(encoding="utf-8"))

    def test_pasta_de_relatos_ausente_e_falha_fatal(self):
        self.cfg.pasta_relatos.rmdir()
        self.assertEqual(executar(self.cfg), FATAL)

    def test_estado_corrompido_e_reconstruido(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1), relato(2)])
        executar(self.cfg)
        (self.cfg.estado / "base_relatos.json").write_text("{corrompido", encoding="utf-8")
        self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 2)

    def test_leitura_transitoria_com_falha_e_repetida(self):
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(1)])
        real = __import__("rpa_relatos.robo", fromlist=["sha256_arquivo"]).sha256_arquivo
        chamadas = {"n": 0}

        def instavel(caminho):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise PermissionError("arquivo travado por outro programa")
            return real(caminho)

        with mock.patch("rpa_relatos.robo.sha256_arquivo", instavel):
            self.assertEqual(executar(self.cfg), OK)
        self.assertEqual(self.saida("relatos_validados.json")["total"], 1)
        self.assertIn("Tentativa 1", self.texto_de_todos_os_logs())

    def test_webhook_fora_do_ar_nao_derruba_e_guarda_pendencia(self):
        import dataclasses
        import urllib.error

        cfg = dataclasses.replace(self.cfg, webhook_url="http://webhook.invalido.test/x")
        self.escrever_relatos("relatos_2026-11-16.jsonl", [relato(i) for i in (1, 2, 3)])
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sem rede")):
            self.assertEqual(executar(cfg), OK)
        pendentes = (cfg.saida / "notificacoes_pendentes.jsonl").read_text(encoding="utf-8")
        self.assertIn("cafe-aurora|mobility", pendentes)
        self.assertNotIn("webhook.invalido", self.texto_de_todos_os_logs())  # a URL é segredo: nunca no log


if __name__ == "__main__":
    unittest.main()
