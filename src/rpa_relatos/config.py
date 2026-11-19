"""Configuração do robô. Tudo que muda entre ambientes vem de variável de ambiente, nunca do código."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

NECESSIDADES = ("mobility", "vision", "hearing", "cognitive")
TIPOS = ("barreira", "elogio")

# Regras de negócio (documentadas em docs/PDD.md)
NOTA_MIN, NOTA_MAX = 1, 5
NOTA_ALTA_PRIORIDADE = 2      # barreira com nota <= 2  -> prioridade alta
NOTA_MEDIA_PRIORIDADE = 3     # barreira com nota == 3  -> prioridade média
FOTOS_PARA_ESCALAR = 2        # barreira nota 3 com >= 2 fotos sobe para alta (evidência forte)
LIMIAR_RECORRENCIA = 3        # barreiras (média/alta) do mesmo lugar+necessidade na janela
JANELA_RECORRENCIA_DIAS = 7
TAMANHO_MAX_TEXTO = 280


def _caminho(nome_var: str, padrao: Path) -> Path:
    valor = os.environ.get(nome_var, "").strip()
    return Path(valor).expanduser().resolve() if valor else padrao


@dataclass(frozen=True)
class Config:
    """Pastas e opções de uma execução. `Config()` lê o ambiente; os testes passam pastas temporárias."""

    entrada: Path = field(default_factory=lambda: _caminho("RPA_ENTRADA", RAIZ / "dados" / "entrada"))
    saida: Path = field(default_factory=lambda: _caminho("RPA_SAIDA", RAIZ / "saida"))
    estado: Path = field(default_factory=lambda: _caminho("RPA_ESTADO", RAIZ / "estado"))
    logs: Path = field(default_factory=lambda: _caminho("RPA_LOGS", RAIZ / "logs"))
    # Segredos e integrações opcionais: vêm só do ambiente (ver .env.example).
    sal_lgpd: str = field(default_factory=lambda: os.environ.get("RPA_SAL_LGPD_SECRET", ""))
    webhook_url: str = field(default_factory=lambda: os.environ.get("RPA_WEBHOOK_URL_SECRET", ""))
    tentativas: int = 3
    espera_tentativa_s: float = 0.5

    @property
    def pasta_relatos(self) -> Path:
        return self.entrada / "relatos"

    @property
    def pasta_lugares(self) -> Path:
        return self.entrada / "lugares"
