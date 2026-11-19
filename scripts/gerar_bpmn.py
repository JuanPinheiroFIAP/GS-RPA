"""Gera docs/fluxo_bpmn.bpmn (BPMN 2.0 com diagrama, abre no bpmn.io) e docs/fluxo_bpmn.svg a partir de UMA descrição.

    python scripts/gerar_bpmn.py
"""
from __future__ import annotations

import textwrap
from html import escape
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

# id: (tipo, nome, cx, cy). Tipos: start, end, task, gw
NOS = {
    "Start": ("start", "Início: agendador ou comando", 60, 130),
    "T_catalogo": ("task", "Carregar catálogo de lugares (fallback para o arquivo anterior)", 200, 130),
    "G_catalogo": ("gw", "Catálogo válido?", 350, 130),
    "T_listar": ("task", "Listar relatos e calcular o hash de cada arquivo", 500, 130),
    "G_novo": ("gw", "Há arquivo novo ou alterado?", 650, 130),
    "T_ler": ("task", "Ler o próximo arquivo (com tentativas)", 800, 130),
    "G_legivel": ("gw", "Arquivo legível?", 950, 130),
    "T_validar": ("task", "PARA CADA linha: validar, corrigir e proteger dados pessoais", 1110, 130),
    "G_valido": ("gw", "Relato válido?", 1270, 130),
    "T_priorizar": ("task", "Aceitar e definir a prioridade (alta, média, baixa)", 1430, 130),
    "E_fatal": ("end", "Falha fatal registrada (código 2)", 350, 290),
    "T_falha": ("task", "Registrar falha do arquivo e seguir com o lote", 950, 290),
    "T_quarentena": ("task", "Enviar para a quarentena com o motivo", 1270, 290),
    "T_alertas": ("task", "Gerar alertas de barreira recorrente e o resumo por lugar", 650, 450),
    "T_gravar": ("task", "Gravar as saídas (atômico) e o relatório da execução", 830, 450),
    "T_notificar": ("task", "Avisar alertas novos (se o webhook cair, fica pendente em arquivo)", 1010, 450),
    "End_ok": ("end", "Fim: código 0 (ok) ou 1 (algum arquivo falhou)", 1190, 450),
}
TAM = {"start": (36, 36), "end": (36, 36), "task": (140, 76), "gw": (50, 50)}

# id: (origem, destino, rótulo, pontos intermediários)
FLUXOS = {
    "f1": ("Start", "T_catalogo", "", []),
    "f2": ("T_catalogo", "G_catalogo", "", []),
    "f3_sim": ("G_catalogo", "T_listar", "sim", []),
    "f3_nao": ("G_catalogo", "E_fatal", "não", []),
    "f4": ("T_listar", "G_novo", "", []),
    "f5_sim": ("G_novo", "T_ler", "sim", []),
    "f5_nao": ("G_novo", "T_alertas", "não (fim da fila)", []),
    "f6": ("T_ler", "G_legivel", "", []),
    "f7_sim": ("G_legivel", "T_validar", "sim", []),
    "f7_nao": ("G_legivel", "T_falha", "não (vazio, binário)", []),
    "f8": ("T_validar", "G_valido", "", []),
    "f9_sim": ("G_valido", "T_priorizar", "sim", []),
    "f9_nao": ("G_valido", "T_quarentena", "não", []),
    "f_volta": ("T_priorizar", "T_listar", "próxima linha, próximo arquivo", [(1430, 40), (500, 40)]),
    "f_volta_q": ("T_quarentena", "T_listar", "", [(1270, 370), (500, 370)]),
    "f_volta_falha": ("T_falha", "T_listar", "", [(950, 370), (500, 370)]),
    "f10": ("T_alertas", "T_gravar", "", []),
    "f11": ("T_gravar", "T_notificar", "", []),
    "f12": ("T_notificar", "End_ok", "", []),
}


def caixa(no: str):
    tipo, _, cx, cy = NOS[no]
    w, h = TAM[tipo]
    return cx - w / 2, cy - h / 2, w, h


def borda(no: str, alvo: tuple[float, float]):
    """Ponto da borda do nó na direção do alvo (só direções ortogonais, que é o que o desenho usa)."""
    x, y, w, h = caixa(no)
    cx, cy = x + w / 2, y + h / 2
    dx, dy = alvo[0] - cx, alvo[1] - cy
    if abs(dx) >= abs(dy):
        return (x + w if dx > 0 else x, cy)
    return (cx, y + h if dy > 0 else y)


def pontos(origem: str, destino: str, meio: list[tuple[float, float]]):
    centro = lambda n: (NOS[n][2], NOS[n][3])
    alvo_o = meio[0] if meio else centro(destino)
    alvo_d = meio[-1] if meio else centro(origem)
    p = [borda(origem, alvo_o), *meio, borda(destino, alvo_d)]
    return [(round(a), round(b)) for a, b in p]


def bpmn() -> str:
    saem: dict[str, list[str]] = {n: [] for n in NOS}
    entram: dict[str, list[str]] = {n: [] for n in NOS}
    for fid, (o, d, _, _) in FLUXOS.items():
        saem[o].append(fid)
        entram[d].append(fid)
    tags = {"start": "startEvent", "end": "endEvent", "task": "task", "gw": "exclusiveGateway"}
    linhas = []
    for nid, (tipo, nome, _, _) in NOS.items():
        io = "".join(f"<incoming>{f}</incoming>" for f in entram[nid]) + "".join(f"<outgoing>{f}</outgoing>" for f in saem[nid])
        linhas.append(f'    <{tags[tipo]} id="{nid}" name="{escape(nome)}">{io}</{tags[tipo]}>')
    for fid, (o, d, rot, _) in FLUXOS.items():
        nome = f' name="{escape(rot)}"' if rot else ""
        linhas.append(f'    <sequenceFlow id="{fid}"{nome} sourceRef="{o}" targetRef="{d}"/>')
    formas, setas = [], []
    for nid, (tipo, *_r) in NOS.items():
        x, y, w, h = caixa(nid)
        extra = ' isMarkerVisible="true"' if tipo == "gw" else ""
        formas.append(f'      <bpmndi:BPMNShape id="S_{nid}" bpmnElement="{nid}"{extra}><dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')
    for fid, (o, d, _, meio) in FLUXOS.items():
        wp = "".join(f'<di:waypoint x="{a}" y="{b}"/>' for a, b in pontos(o, d, meio))
        setas.append(f'      <bpmndi:BPMNEdge id="E_{fid}" bpmnElement="{fid}">{wp}</bpmndi:BPMNEdge>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- BPMN 2.0 do robô de triagem de relatos do Inclui+ (gerado por scripts/gerar_bpmn.py). Abre em bpmn.io ou Camunda Modeler. -->\n"
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"\n'
        '             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI"\n'
        '             id="Definitions_rpa" targetNamespace="https://github.com/kaikyalvaro1708/inclui-gs/rpa">\n'
        '  <process id="Proc_robo" name="Triagem de relatos do Inclui+" isExecutable="false">\n' + "\n".join(linhas) + "\n  </process>\n"
        '  <bpmndi:BPMNDiagram id="Diagrama_1"><bpmndi:BPMNPlane id="Plano_1" bpmnElement="Proc_robo">\n'
        + "\n".join(formas + setas) + "\n  </bpmndi:BPMNPlane></bpmndi:BPMNDiagram>\n</definitions>\n"
    )


def svg() -> str:
    L, A = 1500, 530
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {A}" width="{L}" height="{A}" font-family="Arial, Helvetica, sans-serif" font-size="12">',
        '<title>Fluxo BPMN do robô de triagem de relatos do Inclui+</title>',
        '<defs><marker id="seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#374151"/></marker></defs>',
        f'<rect width="{L}" height="{A}" fill="#ffffff"/>',
        '<text x="20" y="24" font-size="15" font-weight="bold" fill="#111827">Robô de triagem de relatos do Inclui+ (BPMN)</text>',
    ]
    for fid, (orig, dest, rot, meio) in FLUXOS.items():
        pts = pontos(orig, dest, meio)
        o.append(f'<polyline points="{" ".join(f"{a},{b}" for a, b in pts)}" fill="none" stroke="#374151" stroke-width="1.6" marker-end="url(#seta)"/>')
        if rot:
            (xa, ya), (xb, yb) = pts[0], pts[1]
            if meio and fid == "f_volta":
                lx, ly = 900, pts[1][1] - 6
            else:
                lx, ly = (xa + xb) / 2 + (6 if xa == xb else 0), (ya + yb) / 2 - (0 if xa == xb else 6)
            anc = "start" if xa == xb else "middle"
            o.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="{anc}" fill="#6b7280" font-size="11">{escape(rot)}</text>')
    for nid, (tipo, nome, cx, cy) in NOS.items():
        x, y, w, h = caixa(nid)
        if tipo == "task":
            o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.6"/>')
            partes = textwrap.wrap(nome, 22)[:4]
            for i, t in enumerate(partes):
                o.append(f'<text x="{cx}" y="{cy - (len(partes) - 1) * 7 + i * 14 + 4}" text-anchor="middle" fill="#111827">{escape(t)}</text>')
        elif tipo == "gw":
            o.append(f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="#fef9c3" stroke="#a16207" stroke-width="1.6"/><text x="{cx}" y="{cy + 5}" text-anchor="middle" font-weight="bold" fill="#a16207">X</text>')
            for i, t in enumerate(textwrap.wrap(nome, 18)):
                o.append(f'<text x="{cx}" y="{y - 22 + i * 13}" text-anchor="middle" fill="#111827">{escape(t)}</text>')
        else:
            cor, larg = ("#166534", 1.6) if tipo == "start" else ("#b42318", 3.5)
            o.append(f'<circle cx="{cx}" cy="{cy}" r="18" fill="#ffffff" stroke="{cor}" stroke-width="{larg}"/>')
            for i, t in enumerate(textwrap.wrap(nome, 24)):
                o.append(f'<text x="{cx}" y="{cy + 34 + i * 13}" text-anchor="middle" fill="#111827">{escape(t)}</text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    (DOCS / "fluxo_bpmn.bpmn").write_text(bpmn(), encoding="utf-8")
    (DOCS / "fluxo_bpmn.svg").write_text(svg(), encoding="utf-8")
    print("gerados:", DOCS / "fluxo_bpmn.bpmn", DOCS / "fluxo_bpmn.svg")
