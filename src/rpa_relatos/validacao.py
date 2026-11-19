"""Regras de validação de um relato (estrutura de decisão aplicada a cada item da coleção).

Cada relato sai da validação de um de dois jeitos:
* aceito (possivelmente com correções registradas, como normalizar " Vision" para "vision");
* rejeitado, com um motivo de código fixo, e vai para a quarentena (nunca é descartado em silêncio).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import NECESSIDADES, NOTA_MAX, NOTA_MIN, TIPOS, TAMANHO_MAX_TEXTO
from .lgpd import hash_autor, limpar_texto
from .logs import FUSO

_EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Códigos de rejeição (a lista completa aparece no relatório de execução)
MOTIVOS = (
    "linha_json_invalida",
    "registro_nao_e_objeto",
    "relato_id_ausente",
    "sem_data_hora",
    "data_invalida",
    "lugar_inexistente",
    "necessidade_invalida",
    "tipo_invalido",
    "nota_nao_numerica",
    "nota_fora_da_faixa",
    "duplicado",
)


@dataclass
class Resultado:
    ok: bool
    registro: dict[str, Any] | None = None
    motivo: str | None = None
    correcoes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _nota(valor: Any) -> tuple[int | None, str | None, bool]:
    """Devolve (nota, motivo_de_rejeicao, foi_corrigida). Aceita '4' (texto numérico) e corrige."""
    if isinstance(valor, bool):
        return None, "nota_nao_numerica", False
    if isinstance(valor, (int, float)) and float(valor).is_integer():
        n, corrigida = int(valor), False
    elif isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
        n, corrigida = int(valor.strip()), True
    else:
        return None, "nota_nao_numerica", False
    if not NOTA_MIN <= n <= NOTA_MAX:
        return None, "nota_fora_da_faixa", False
    return n, None, corrigida


def validar(bruto: Any, lugares: dict[str, dict], sal_lgpd: str) -> Resultado:
    if not isinstance(bruto, dict):
        return Resultado(False, motivo="registro_nao_e_objeto")

    relato_id = str(bruto.get("relato_id") or "").strip()
    if not relato_id:
        return Resultado(False, motivo="relato_id_ausente")

    if not bruto.get("criado_em"):
        return Resultado(False, motivo="sem_data_hora")
    try:
        criado_em = datetime.fromisoformat(str(bruto["criado_em"]))
    except ValueError:
        return Resultado(False, motivo="data_invalida")

    lugar_id = str(bruto.get("lugar_id") or "").strip()
    if lugar_id not in lugares:
        return Resultado(False, motivo="lugar_inexistente")

    correcoes: list[str] = []
    avisos: list[str] = []

    if criado_em.tzinfo is None:  # sem fuso: assume Brasília, o fuso do produto
        criado_em = criado_em.replace(tzinfo=FUSO)
        correcoes.append("fuso_assumido_brasilia")

    necessidade_bruta = bruto.get("necessidade")
    necessidade = necessidade_bruta.strip().lower() if isinstance(necessidade_bruta, str) else ""
    if necessidade not in NECESSIDADES:
        return Resultado(False, motivo="necessidade_invalida")
    if necessidade != necessidade_bruta:
        correcoes.append("necessidade_normalizada")

    tipo = str(bruto.get("tipo") or "").strip().lower()
    if tipo not in TIPOS:
        return Resultado(False, motivo="tipo_invalido")

    nota, motivo, corrigida = _nota(bruto.get("nota"))
    if motivo:
        return Resultado(False, motivo=motivo)
    if corrigida:
        correcoes.append("nota_convertida_para_inteiro")

    email = bruto.get("autor_email")
    if email is not None and not _EMAIL_OK.match(str(email).strip()):
        avisos.append("email_invalido_autor_descartado")  # o relato vale; só não dá para identificar a pessoa
        email = None

    texto, removeu = limpar_texto(str(bruto.get("texto") or ""), TAMANHO_MAX_TEXTO)
    if removeu:
        avisos.append("dado_pessoal_removido_do_texto")

    fotos = bruto.get("fotos")
    fotos = fotos if isinstance(fotos, int) and not isinstance(fotos, bool) and fotos >= 0 else 0

    # Registro pronto para o MVP: sem nome, sem e-mail. O autor vira um hash com sal.
    registro = {
        "relato_id": relato_id,
        "criado_em": criado_em.isoformat(),
        "lugar_id": lugar_id,
        "necessidade": necessidade,
        "tipo": tipo,
        "nota": nota,
        "fotos": fotos,
        "texto": texto,
        "autor_hash": hash_autor(email, sal_lgpd),
    }
    return Resultado(True, registro=registro, correcoes=correcoes, avisos=avisos)
