"""Orquestração do robô: lê relatos novos, valida, decide, protege, grava para o MVP e audita.

Fluxo (ver docs/PDD.md e docs/fluxo_bpmn.bpmn):
  1. carrega o catálogo de lugares (com fallback para o arquivo anterior);
  2. para cada arquivo de relatos ainda não processado (hash SHA-256 no estado):
       para cada linha: valida -> aceita (com correções) ou manda para a quarentena;
  3. recalcula prioridade, alertas e o resumo por lugar;
  4. grava as saídas de forma atômica e avisa os alertas novos;
  5. devolve um código de saída: 0 ok, 1 parcial (algum arquivo falhou), 2 fatal.
"""
from __future__ import annotations

import json
import time
import urllib.error
from collections import Counter
from pathlib import Path
from typing import Any

from .arquivos import (
    ArquivoInvalido,
    CatalogoIndisponivel,
    carregar_catalogo,
    com_tentativas,
    escrever_json,
    escrever_jsonl,
    ler_json,
    ler_jsonl,
    sha256_arquivo,
)
from .config import Config
from .decisao import gerar_alertas, prioridade, resumo_por_lugar
from .lgpd import SAL_DESENVOLVIMENTO
from .logs import Auditoria, agora, criar_logger, fechar_logger
from .notifica import enviar_webhook, montar_mensagem
from .validacao import validar

OK, PARCIAL, FATAL = 0, 1, 2


def executar(cfg: Config, max_arquivos: int | None = None, reprocessar: bool = False) -> int:
    inicio = agora()
    t0 = time.monotonic()
    execucao_id = inicio.strftime("%Y%m%dT%H%M%S")
    log = criar_logger(cfg.logs)
    aud = Auditoria(cfg.logs, execucao_id)
    try:
        return _executar(cfg, log, aud, execucao_id, inicio, t0, max_arquivos, reprocessar)
    except Exception as erro:  # rede de segurança final: toda falha inesperada fica registrada e vira código de saída
        log.exception("Falha inesperada no robô: %s", type(erro).__name__)
        aud.evento("falha_inesperada", erro=type(erro).__name__)
        return FATAL
    finally:
        fechar_logger(log)


def _executar(cfg, log, aud, execucao_id, inicio, t0, max_arquivos, reprocessar) -> int:
    log.info("Início da execução %s", execucao_id)
    aud.evento("inicio", entrada=str(cfg.entrada.name), reprocessar=reprocessar)
    if not cfg.sal_lgpd:
        log.warning("RPA_SAL_LGPD_SECRET ausente: usando sal de desenvolvimento (defina o sal real em produção)")
        aud.evento("aviso_sal_lgpd_ausente")

    # 1. Catálogo ---------------------------------------------------------------------------------------------
    try:
        lugares, arquivo_catalogo = carregar_catalogo(cfg.pasta_lugares)
    except CatalogoIndisponivel as erro:
        log.error("Sem catálogo de lugares, nada a validar: %s", erro)
        aud.evento("falha_fatal", motivo="catalogo_indisponivel")
        return FATAL
    log.info("Catálogo carregado: %d lugares (%s)", len(lugares), arquivo_catalogo)
    aud.evento("catalogo_carregado", lugares=len(lugares), arquivo=arquivo_catalogo)

    if not cfg.pasta_relatos.is_dir():
        log.error("Pasta de entrada de relatos ausente: %s", cfg.pasta_relatos.name)
        aud.evento("falha_fatal", motivo="pasta_relatos_ausente")
        return FATAL

    # 2. Estado e base consolidada ------------------------------------------------------------------------------
    estado_arq, base_arq, quar_arq = cfg.estado / "arquivos.json", cfg.estado / "base_relatos.json", cfg.estado / "quarentena.json"
    estado, c1 = ler_json(estado_arq, {"arquivos": {}, "alertas_avisados": []})
    base, c2 = ler_json(base_arq, {})
    quarentena, c3 = ler_json(quar_arq, {})
    if c1 or c2 or c3 or reprocessar:
        if c1 or c2 or c3:
            log.warning("Estado interno corrompido: reconstruindo a partir dos arquivos de entrada")
            aud.evento("estado_corrompido_reconstruido")
        estado, base, quarentena = {"arquivos": {}, "alertas_avisados": []}, {}, {}

    arquivos = sorted(cfg.pasta_relatos.glob("relatos_*.jsonl"))
    contadores: Counter[str] = Counter(arquivos_encontrados=len(arquivos))
    rejeicoes: Counter[str] = Counter()
    correcoes: Counter[str] = Counter()
    avisos: Counter[str] = Counter()
    falhas: list[dict[str, str]] = []
    if not arquivos:
        log.warning("Nenhum arquivo relatos_*.jsonl na entrada: nada novo a processar")

    processados_agora = 0
    for arquivo in arquivos:
        try:
            digest = com_tentativas(
                lambda a=arquivo: sha256_arquivo(a), cfg.tentativas, cfg.espera_tentativa_s,
                aviso=lambda n, e, a=arquivo: log.warning("Tentativa %d de ler %s falhou (%s)", n, a.name, type(e).__name__),
            )
        except OSError as erro:
            _falha_arquivo(log, aud, falhas, contadores, arquivo.name, type(erro).__name__)
            continue

        if estado["arquivos"].get(arquivo.name) == digest:
            contadores["arquivos_ignorados_ja_processados"] += 1
            log.info("Ignorado (já processado, mesmo conteúdo): %s", arquivo.name)
            continue
        if max_arquivos is not None and processados_agora >= max_arquivos:
            log.info("Limite de %d arquivo(s) por execução atingido: %s fica para a próxima", max_arquivos, arquivo.name)
            continue

        try:
            novos, rej_arquivo = _processar_arquivo(cfg, log, arquivo, lugares, base, contadores, rejeicoes, correcoes, avisos)
        except (ArquivoInvalido, OSError) as erro:
            motivo = str(erro) if isinstance(erro, ArquivoInvalido) else type(erro).__name__
            _falha_arquivo(log, aud, falhas, contadores, arquivo.name, motivo)
            continue

        base.update(novos)
        quarentena[arquivo.name] = rej_arquivo
        estado["arquivos"][arquivo.name] = digest
        processados_agora += 1
        contadores["arquivos_processados"] += 1
        log.info("Processado %s: %d aceitos, %d na quarentena", arquivo.name, len(novos), len(rej_arquivo))
        aud.evento("arquivo_processado", arquivo=arquivo.name, aceitos=len(novos), quarentena=len(rej_arquivo))

    # 3. Decisão (sobre a base inteira, para o resultado não depender da ordem dos lotes) -----------------------------
    relatos = []
    for r in base.values():
        item = {k: v for k, v in r.items() if k != "origem"}
        item["prioridade"] = prioridade(item)
        relatos.append(item)
    relatos.sort(key=lambda r: (r["criado_em"], r["relato_id"]))
    alertas = gerar_alertas(relatos, lugares)
    resumo = resumo_por_lugar(relatos, lugares, alertas)
    prioridades = Counter(r["prioridade"] for r in relatos)

    # 4. Saídas para o MVP --------------------------------------------------------------------------------------
    dados_ate = relatos[-1]["criado_em"] if relatos else None
    escrever_json(cfg.saida / "relatos_validados.json", {"versao": 1, "dados_ate": dados_ate, "total": len(relatos), "relatos": relatos})
    escrever_json(cfg.saida / "alertas_prioritarios.json", {"versao": 1, "dados_ate": dados_ate, "total": len(alertas), "alertas": alertas})
    escrever_json(cfg.saida / "resumo_lugares.json", {"versao": 1, "dados_ate": dados_ate, "lugares": resumo})
    linhas_quarentena = [item for nome in sorted(quarentena) for item in quarentena[nome]]
    escrever_jsonl(cfg.saida / "quarentena.jsonl", linhas_quarentena)
    log.info("Saídas gravadas em %s: %d relatos, %d alertas, %d na quarentena", cfg.saida.name, len(relatos), len(alertas), len(linhas_quarentena))

    # 5. Notificação dos alertas novos -------------------------------------------------------------------------
    novos_alertas = [a for a in alertas if a["alerta_id"] not in estado["alertas_avisados"]]
    if novos_alertas:
        _avisar(cfg, log, aud, novos_alertas)
        estado["alertas_avisados"] = sorted({*estado["alertas_avisados"], *(a["alerta_id"] for a in novos_alertas)})

    escrever_json(estado_arq, estado)
    escrever_json(base_arq, base)
    escrever_json(quar_arq, quarentena)

    # 6. Relatório da execução ---------------------------------------------------------------------------------
    status = "parcial" if falhas else "ok"
    relatorio = {
        "execucao": execucao_id,
        "inicio": inicio.isoformat(),
        "fim": agora().isoformat(),
        "duracao_s": round(time.monotonic() - t0, 2),
        "status": status,
        "arquivos": {
            "encontrados": contadores["arquivos_encontrados"],
            "processados": contadores["arquivos_processados"],
            "ignorados_ja_processados": contadores["arquivos_ignorados_ja_processados"],
            "com_falha": falhas,
        },
        "linhas_lidas": contadores["linhas_lidas"],
        "relatos_aceitos_nesta_execucao": contadores["relatos_aceitos"],
        "rejeitados_por_motivo": dict(sorted(rejeicoes.items())),
        "correcoes_automaticas": dict(sorted(correcoes.items())),
        "avisos": dict(sorted(avisos.items())),
        "base_total": len(relatos),
        "prioridades": dict(sorted(prioridades.items())),
        "alertas_total": len(alertas),
        "alertas_novos": len(novos_alertas),
        "catalogo": {"arquivo": arquivo_catalogo, "lugares": len(lugares)},
    }
    escrever_json(cfg.saida / "relatorio_execucao.json", relatorio)
    aud.evento("fim", status=status, **{k: relatorio[k] for k in ("linhas_lidas", "relatos_aceitos_nesta_execucao", "alertas_novos", "duracao_s")})
    log.info("Fim da execução %s: status=%s, %d linhas lidas, %d aceitos, %d rejeitados, %d alertas novos",
             execucao_id, status, contadores["linhas_lidas"], contadores["relatos_aceitos"], sum(rejeicoes.values()), len(novos_alertas))
    return PARCIAL if falhas else OK


def _processar_arquivo(cfg, log, arquivo: Path, lugares, base, contadores, rejeicoes, correcoes, avisos):
    """Valida todas as linhas de um arquivo. Só devolve (e só altera contadores) se o arquivo inteiro for legível."""
    novos: dict[str, dict] = {}
    rej: list[dict[str, Any]] = []
    c_linhas, c_rej, c_cor, c_avi = 0, Counter(), Counter(), Counter()
    vistos_no_arquivo: set[str] = set()
    for n, obj, linha_ok in ler_jsonl(arquivo):
        c_linhas += 1
        if not linha_ok:
            c_rej["linha_json_invalida"] += 1
            rej.append({"arquivo": arquivo.name, "linha": n, "relato_id": None, "motivo": "linha_json_invalida"})
            continue
        res = validar(obj, lugares, cfg.sal_lgpd)
        rid = res.registro["relato_id"] if res.ok else (str(obj.get("relato_id") or "") if isinstance(obj, dict) else "")
        if res.ok:
            existente = base.get(rid)
            if rid in vistos_no_arquivo or (existente and existente.get("origem") != arquivo.name):
                res.ok, res.motivo = False, "duplicado"  # mesmo id duas vezes: fica a primeira, a repetida vai para a quarentena
        if not res.ok:
            c_rej[res.motivo] += 1
            rej.append({"arquivo": arquivo.name, "linha": n, "relato_id": rid or None, "motivo": res.motivo})
            continue
        vistos_no_arquivo.add(rid)
        res.registro["origem"] = arquivo.name
        novos[rid] = res.registro
        c_cor.update(res.correcoes)
        c_avi.update(res.avisos)
    # remove da base o que veio deste arquivo numa versão anterior (arquivo reeditado), para não sobrar relato fantasma
    for rid in [k for k, v in base.items() if v.get("origem") == arquivo.name and k not in novos]:
        del base[rid]
    contadores["linhas_lidas"] += c_linhas
    contadores["relatos_aceitos"] += len(novos)
    rejeicoes.update(c_rej)
    correcoes.update(c_cor)
    avisos.update(c_avi)
    return novos, rej


def _falha_arquivo(log, aud, falhas, contadores, nome: str, motivo: str) -> None:
    log.error("Falha ao processar %s (%s): arquivo pulado, o restante do lote segue", nome, motivo)
    aud.evento("arquivo_com_falha", arquivo=nome, motivo=motivo)
    falhas.append({"arquivo": nome, "motivo": motivo})
    contadores["arquivos_com_falha"] += 1


def _avisar(cfg: Config, log, aud, alertas_novos: list[dict]) -> None:
    mensagem = montar_mensagem(alertas_novos)
    for linha in mensagem.splitlines():
        log.info("[ALERTA] %s", linha)
    aud.evento("alertas_novos", total=len(alertas_novos), ids=[a["alerta_id"] for a in alertas_novos])
    if not cfg.webhook_url:
        return
    try:
        enviar_webhook(cfg.webhook_url, mensagem, cfg.tentativas, cfg.espera_tentativa_s)
        aud.evento("webhook_enviado", total=len(alertas_novos))
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        log.warning("Webhook fora do ar (%s): alertas ficam em notificacoes_pendentes.jsonl", type(erro).__name__)
        aud.evento("webhook_falhou", erro=type(erro).__name__)
        pendentes = cfg.saida / "notificacoes_pendentes.jsonl"
        antigos = [] if not pendentes.exists() else [json.loads(l) for l in pendentes.read_text(encoding="utf-8").splitlines() if l.strip()]
        escrever_jsonl(pendentes, antigos + [{"alerta_id": a["alerta_id"], "mensagem": mensagem} for a in alertas_novos])
