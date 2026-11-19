"""Regras de negócio: prioridade de cada relato e alertas por lugar.

O robô NÃO muda a nota de um lugar sozinho. Ele só prioriza e levanta alertas com evidência, e uma pessoa da equipe
decide (pessoa no circuito, princípio de IA responsável do desafio). Todo alerta nasce com status `pendente_revisao`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable

from .config import (
    FOTOS_PARA_ESCALAR,
    JANELA_RECORRENCIA_DIAS,
    LIMIAR_RECORRENCIA,
    NECESSIDADES,
    NOTA_ALTA_PRIORIDADE,
    NOTA_MEDIA_PRIORIDADE,
)


def prioridade(relato: dict[str, Any]) -> str:
    """Decisão por relato: alta, media ou baixa."""
    if relato["tipo"] == "elogio":
        return "baixa"
    if relato["nota"] <= NOTA_ALTA_PRIORIDADE:
        return "alta"
    if relato["nota"] == NOTA_MEDIA_PRIORIDADE:
        return "alta" if relato["fotos"] >= FOTOS_PARA_ESCALAR else "media"
    return "baixa"  # barreira declarada, mas com nota 4 ou 5: provável erro de preenchimento, não vira alerta


def gerar_alertas(relatos: Iterable[dict[str, Any]], lugares: dict[str, dict]) -> list[dict[str, Any]]:
    """Alerta de barreira recorrente: >= LIMIAR barreiras (prioridade média/alta) do mesmo lugar e necessidade
    dentro de JANELA dias, contados a partir do relato mais recente daquele grupo (determinístico, sem usar o relógio)."""
    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in relatos:
        if r["prioridade"] in ("alta", "media"):
            grupos[(r["lugar_id"], r["necessidade"])].append(r)

    alertas = []
    for (lugar_id, necessidade), itens in sorted(grupos.items()):
        itens.sort(key=lambda r: r["criado_em"])
        fim = datetime.fromisoformat(itens[-1]["criado_em"])
        janela = [r for r in itens if datetime.fromisoformat(r["criado_em"]) >= fim - timedelta(days=JANELA_RECORRENCIA_DIAS)]
        if len(janela) < LIMIAR_RECORRENCIA:
            continue
        altas = sum(1 for r in janela if r["prioridade"] == "alta")
        alertas.append(
            {
                "alerta_id": f"{lugar_id}|{necessidade}",
                "tipo": "barreira_recorrente",
                "severidade": "alta" if altas >= 3 else "media",
                "lugar_id": lugar_id,
                "lugar_nome": lugares[lugar_id].get("name", lugar_id),
                "necessidade": necessidade,
                "relatos_na_janela": len(janela),
                "relatos_prioridade_alta": altas,
                "janela_dias": JANELA_RECORRENCIA_DIAS,
                "ultimo_relato_em": itens[-1]["criado_em"],
                "evidencias": [r["relato_id"] for r in janela],
                "recomendacao": "Revisar a nota do lugar para esta necessidade e confirmar o recurso por foto ou contato.",
                "status": "pendente_revisao",
            }
        )
    alertas.sort(key=lambda a: (a["severidade"] != "alta", -a["relatos_na_janela"], a["alerta_id"]))
    return alertas


def resumo_por_lugar(relatos: Iterable[dict[str, Any]], lugares: dict[str, dict], alertas: list[dict]) -> dict[str, Any]:
    """Visão que o MVP consome: por lugar, por necessidade, quantos relatos, nota média e se há alerta aberto."""
    com_alerta = defaultdict(set)
    for a in alertas:
        com_alerta[a["lugar_id"]].add(a["necessidade"])

    acumulado: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"relatos": 0, "soma": 0, "barreiras": 0, "elogios": 0}))
    ultima: dict[str, str] = {}
    for r in relatos:
        a = acumulado[r["lugar_id"]][r["necessidade"]]
        a["relatos"] += 1
        a["soma"] += r["nota"]
        a["barreiras" if r["tipo"] == "barreira" else "elogios"] += 1
        ultima[r["lugar_id"]] = max(ultima.get(r["lugar_id"], ""), r["criado_em"])

    saida = {}
    for lugar_id in sorted(lugares):
        por_need = {}
        for need in NECESSIDADES:
            a = acumulado.get(lugar_id, {}).get(need)
            if not a:
                continue
            por_need[need] = {
                "relatos": a["relatos"],
                "nota_media": round(a["soma"] / a["relatos"], 2),
                "barreiras": a["barreiras"],
                "elogios": a["elogios"],
                "alerta": need in com_alerta.get(lugar_id, set()),
            }
        total = sum(v["relatos"] for v in por_need.values())
        saida[lugar_id] = {
            "nome": lugares[lugar_id].get("name", lugar_id),
            "bairro": lugares[lugar_id].get("neighborhood", ""),
            "total_relatos": total,
            "tem_alerta": bool(com_alerta.get(lugar_id)),
            "ultimo_relato_em": ultima.get(lugar_id),
            "por_necessidade": por_need,
        }
    return saida
