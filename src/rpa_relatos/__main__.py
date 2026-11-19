"""Linha de comando:  python -m rpa_relatos [--entrada PASTA] [--max-arquivos N] [--reprocessar]"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from .config import Config
from .robo import executar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rpa_relatos", description="Robô de triagem de relatos do Inclui+")
    p.add_argument("--entrada", type=Path, help="pasta com relatos/ e lugares/ (padrão: dados/entrada ou RPA_ENTRADA)")
    p.add_argument("--saida", type=Path, help="pasta de saída consumida pelo MVP (padrão: saida/)")
    p.add_argument("--max-arquivos", type=int, help="processa no máximo N arquivos novos (simula lotes)")
    p.add_argument("--reprocessar", action="store_true", help="ignora o estado e processa tudo de novo")
    args = p.parse_args(argv)

    cfg = Config()
    mudancas = {k: v.resolve() for k, v in (("entrada", args.entrada), ("saida", args.saida)) if v}
    if mudancas:
        cfg = dataclasses.replace(cfg, **mudancas)
    return executar(cfg, max_arquivos=args.max_arquivos, reprocessar=args.reprocessar)


if __name__ == "__main__":
    sys.exit(main())
