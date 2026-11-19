"""Entrada e saída de arquivos, com tentativas, gravação atômica e leitura tolerante a linhas ruins."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")


class ArquivoInvalido(Exception):
    """Arquivo que não adianta tentar de novo: vazio ou com codificação quebrada."""


class CatalogoIndisponivel(Exception):
    """Nenhum arquivo de lugares válido foi encontrado."""


def com_tentativas(
    funcao: Callable[[], T],
    tentativas: int,
    espera_s: float,
    excecoes: tuple[type[BaseException], ...] = (OSError,),
    aviso: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Repete `funcao` quando ela levanta uma das `excecoes` (falha transitória, como arquivo travado por outro programa).
    Espera cresce a cada tentativa (espera, 2x, 4x...). Na última tentativa, a exceção sobe: nada de falha silenciosa."""
    for n in range(1, tentativas + 1):
        try:
            return funcao()
        except excecoes as erro:
            if n == tentativas:
                raise
            if aviso:
                aviso(n, erro)
            time.sleep(espera_s * (2 ** (n - 1)))
    raise AssertionError("inalcançável")  # pragma: no cover


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_jsonl(caminho: Path) -> Iterator[tuple[int, Any, bool]]:
    """Gera (número da linha, objeto, linha_valida). Linha com JSON quebrado vira (n, None, False) em vez de derrubar o lote."""
    if caminho.stat().st_size == 0:
        raise ArquivoInvalido("arquivo_vazio")
    try:
        with caminho.open("r", encoding="utf-8") as f:
            for n, linha in enumerate(f, start=1):
                if not linha.strip():
                    continue
                try:
                    yield n, json.loads(linha), True
                except json.JSONDecodeError:
                    yield n, None, False
    except UnicodeDecodeError as erro:
        raise ArquivoInvalido("codificacao_invalida") from erro


def escrever_json(caminho: Path, dados: Any) -> None:
    """Grava em arquivo temporário e troca no fim (os.replace é atômico): quem lê nunca vê arquivo pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)


def escrever_jsonl(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(l, ensure_ascii=False, sort_keys=True) + "\n" for l in linhas), encoding="utf-8")
    os.replace(tmp, caminho)


def ler_json(caminho: Path, padrao: Any) -> tuple[Any, bool]:
    """Devolve (dados, estava_corrompido). Arquivo ausente devolve o padrão sem erro; arquivo quebrado devolve o padrão e True."""
    if not caminho.exists():
        return padrao, False
    try:
        return json.loads(caminho.read_text(encoding="utf-8")), False
    except (json.JSONDecodeError, UnicodeDecodeError):
        return padrao, True


def carregar_catalogo(pasta: Path) -> tuple[dict[str, dict], str]:
    """Lê o catálogo de lugares do arquivo mais recente. Se ele estiver quebrado, cai para o anterior (recuperação).
    Devolve ({lugar_id: lugar}, nome_do_arquivo_usado)."""
    if not pasta.is_dir():
        raise CatalogoIndisponivel(f"pasta de lugares ausente: {pasta.name}")
    for arquivo in sorted(pasta.glob("lugares_*.jsonl"), reverse=True):
        try:
            lugares = {}
            for _, obj, ok in ler_jsonl(arquivo):
                if ok and isinstance(obj, dict) and obj.get("id"):
                    lugares[str(obj["id"])] = obj
            if lugares:
                return lugares, arquivo.name
        except (ArquivoInvalido, OSError):
            continue
    raise CatalogoIndisponivel("nenhum arquivo lugares_*.jsonl válido")
