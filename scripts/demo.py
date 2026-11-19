"""Demonstração completa para o vídeo e para as evidências do relatório.

    python scripts/demo.py

Roda, nesta ordem: (1) lote 1, (2) lote 2, (3) reexecução sem nada novo, (4) cenário de falha com arquivos ruins.
Apaga só as pastas geradas pelo próprio robô (saida/, estado/, logs/) antes de começar.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV_BASE = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "PYTHONIOENCODING": "utf-8"}


def robo(titulo: str, *args: str, **env: str) -> int:
    print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}", flush=True)
    r = subprocess.run([sys.executable, "-m", "rpa_relatos", *args], env={**ENV_BASE, **env}, cwd=RAIZ)
    print(f"[código de saída: {r.returncode}]", flush=True)
    return r.returncode


def main() -> None:
    for pasta in ("saida", "estado", "logs"):
        shutil.rmtree(RAIZ / pasta, ignore_errors=True)

    robo("CENÁRIO 1 - SUCESSO, LOTE 1 (3 primeiros arquivos)", "--max-arquivos", "3")
    robo("CENÁRIO 2 - SUCESSO, LOTE 2 (só os arquivos novos entram)")
    robo("CENÁRIO 3 - REEXECUÇÃO (nada novo: nada duplica)")

    with tempfile.TemporaryDirectory(prefix="rpa_falha_") as tmp:
        tmp = Path(tmp)
        shutil.copytree(RAIZ / "dados" / "entrada", tmp / "entrada")
        (tmp / "entrada" / "relatos" / "relatos_2026-11-18.jsonl").write_bytes(b"")  # arquivo vazio
        (tmp / "entrada" / "relatos" / "relatos_2026-11-20.jsonl").write_bytes(b"\xff\xfe lixo binario")
        quebrado = tmp / "entrada" / "relatos" / "relatos_2026-11-16.jsonl"
        quebrado.write_text(quebrado.read_text(encoding="utf-8") + "{linha quebrada sem fechar\n", encoding="utf-8")
        (tmp / "entrada" / "lugares" / "lugares_2026-11-20.jsonl").write_text("{catalogo quebrado\n", encoding="utf-8")
        robo(
            "CENÁRIO 4 - FALHAS (arquivo vazio, arquivo binário, linha quebrada, catálogo mais novo corrompido)",
            RPA_ENTRADA=str(tmp / "entrada"), RPA_SAIDA=str(tmp / "saida"), RPA_ESTADO=str(tmp / "estado"),
            RPA_LOGS=str(RAIZ / "logs" / "cenario_falha"),
        )
        shutil.copy(tmp / "saida" / "relatorio_execucao.json", RAIZ / "logs" / "cenario_falha" / "relatorio_execucao.json")


if __name__ == "__main__":
    main()
