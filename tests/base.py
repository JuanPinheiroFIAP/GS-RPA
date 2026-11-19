"""Apoio dos testes: monta uma pasta de entrada temporária com catálogo e relatos sob medida."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rpa_relatos.config import Config  # noqa: E402

LUGARES = [
    {"id": "cafe-aurora", "name": "Café Aurora", "neighborhood": "Bela Vista"},
    {"id": "cine-lumiar", "name": "Cine Lumiar", "neighborhood": "Pinheiros"},
]


def relato(i: int, dia: str = "2026-11-16", **campos) -> dict:
    base = {
        "relato_id": f"{dia}-{i:03d}",
        "criado_em": f"{dia}T1{i % 10}:00:00-03:00",
        "usuario_id": f"u{i:03d}",
        "autor_nome": "Pessoa Sintetica",
        "autor_email": f"pessoa{i}@example.com",
        "lugar_id": "cafe-aurora",
        "necessidade": "mobility",
        "tipo": "barreira",
        "nota": 1,
        "fotos": 0,
        "texto": "Degrau na entrada e nenhuma rampa.",
    }
    base.update(campos)
    return base


class AmbienteRPA(unittest.TestCase):
    """Cada teste ganha pastas temporárias isoladas (entrada, saída, estado e logs)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rpa_teste_"))
        (self.tmp / "entrada" / "relatos").mkdir(parents=True)
        (self.tmp / "entrada" / "lugares").mkdir(parents=True)
        self.cfg = Config(
            entrada=self.tmp / "entrada", saida=self.tmp / "saida", estado=self.tmp / "estado", logs=self.tmp / "logs",
            sal_lgpd="sal-de-teste", webhook_url="", tentativas=2, espera_tentativa_s=0.0,
        )
        self.escrever_lugares("lugares_2026-11-16.jsonl", LUGARES)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def escrever_lugares(self, nome: str, lugares: list[dict]):
        self.escrever_linhas(self.cfg.pasta_lugares / nome, lugares)

    def escrever_relatos(self, nome: str, relatos: list[dict]):
        self.escrever_linhas(self.cfg.pasta_relatos / nome, relatos)

    @staticmethod
    def escrever_linhas(caminho: Path, itens: list):
        caminho.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in itens), encoding="utf-8")

    def saida(self, nome: str):
        return json.loads((self.cfg.saida / nome).read_text(encoding="utf-8"))

    def texto_de_todos_os_logs(self) -> str:
        return "".join(p.read_text(encoding="utf-8") for p in self.cfg.logs.glob("*"))
