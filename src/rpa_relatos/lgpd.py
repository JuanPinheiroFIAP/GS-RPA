"""Proteção de dados pessoais (LGPD): pseudonimização do autor e limpeza do texto livre."""
from __future__ import annotations

import hashlib
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_TELEFONE = re.compile(r"(\+?55\s?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

SAL_DESENVOLVIMENTO = "somente-desenvolvimento"


def hash_autor(email: str | None, sal: str) -> str | None:
    """SHA-256 com sal, truncado em 16 hex. Permite contar 'quantas pessoas diferentes' sem saber quem são.

    O sal real fica no ambiente (RPA_SAL_LGPD_SECRET). Sem ele, o hash usa um valor de desenvolvimento e o robô avisa.
    """
    if not email:
        return None
    base = f"{sal or SAL_DESENVOLVIMENTO}|{email.strip().lower()}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:16]


def limpar_texto(texto: str, tamanho_max: int) -> tuple[str, bool]:
    """Remove e-mail, telefone e CPF que a pessoa possa ter digitado no relato. Devolve (texto, houve_remocao)."""
    original = texto
    for padrao, marca in ((_EMAIL, "[e-mail removido]"), (_CPF, "[cpf removido]"), (_TELEFONE, "[telefone removido]")):
        texto = padrao.sub(marca, texto)
    texto = " ".join(texto.split())[:tamanho_max]
    return texto, texto != " ".join(original.split())[:tamanho_max]
