"""Logs e trilha de auditoria.

* `logs/rpa.log`: log legível, com data/hora, nível e mensagem.
* `logs/auditoria.jsonl`: um evento JSON por linha (quem/o quê/quando), para auditar uma execução.

Regra de ouro (LGPD): nenhum log recebe nome, e-mail ou texto livre do relato. Só ids, contagens e códigos de erro.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

FUSO = timezone(timedelta(hours=-3))  # Brasília
_CAMPOS_PROIBIDOS = {"autor_nome", "autor_email", "texto", "email", "nome"}


def agora() -> datetime:
    return datetime.now(FUSO).replace(microsecond=0)


class Auditoria:
    """Grava eventos de auditoria em JSON Lines, descartando qualquer campo pessoal por segurança."""

    def __init__(self, pasta: Path, execucao_id: str):
        pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo = pasta / "auditoria.jsonl"
        self.execucao_id = execucao_id

    def evento(self, evento: str, **dados) -> None:
        limpo = {k: v for k, v in dados.items() if k not in _CAMPOS_PROIBIDOS}
        linha = {"ts": agora().isoformat(), "execucao": self.execucao_id, "evento": evento, **limpo}
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def criar_logger(pasta: Path, nome: str = "rpa_relatos") -> logging.Logger:
    pasta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"{nome}.{pasta}")
    if logger.handlers:  # já configurado (evita linhas duplicadas quando o robô roda duas vezes no mesmo processo)
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%dT%H:%M:%S-03:00")
    formato.converter = lambda *_: agora().timetuple()
    arquivo = logging.FileHandler(pasta / "rpa.log", encoding="utf-8")
    arquivo.setFormatter(formato)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formato)
    logger.addHandler(arquivo)
    logger.addHandler(console)
    return logger


def fechar_logger(logger: logging.Logger) -> None:
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
