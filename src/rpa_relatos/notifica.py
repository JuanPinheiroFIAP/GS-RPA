"""Aviso de alertas novos por webhook (Discord ou Slack). Opcional e nunca derruba o robô.

Se o webhook não estiver configurado ou estiver fora do ar, o aviso vai para `saida/notificacoes_pendentes.jsonl`
e o robô segue (degrada com elegância). A URL do webhook é segredo: vem do ambiente e nunca aparece em log.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .arquivos import com_tentativas


def montar_mensagem(alertas_novos: list[dict]) -> str:
    linhas = [f"Inclui+ RPA: {len(alertas_novos)} alerta(s) novo(s) de barreira recorrente"]
    for a in alertas_novos[:10]:
        linhas.append(f"- {a['lugar_nome']} ({a['necessidade']}): {a['relatos_na_janela']} relatos, severidade {a['severidade']}")
    return "\n".join(linhas)


def enviar_webhook(url: str, mensagem: str, tentativas: int, espera_s: float, timeout_s: float = 8.0) -> None:
    corpo = json.dumps({"content": mensagem, "text": mensagem}).encode("utf-8")  # 'content' = Discord, 'text' = Slack

    def _post() -> None:
        req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (URL vem do ambiente, não de dado externo)
            resp.read()

    com_tentativas(_post, tentativas, espera_s, excecoes=(urllib.error.URLError, TimeoutError, OSError))
