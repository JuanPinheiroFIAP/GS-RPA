"""Monta o relatório técnico em PDF (docs/Relatorio_GS_RPA.pdf) a partir do README, dos logs reais e das imagens.

    python scripts/gerar_relatorio.py        (precisa do Microsoft Edge ou Chrome instalado, para imprimir em PDF)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium",
]


def ler(p: str) -> str:
    return (RAIZ / p).read_text(encoding="utf-8")


def trecho_log(inicio: str, fim: str, max_linhas: int = 18) -> str:
    linhas = ler("tests/evidencias/demo_execucao.txt").splitlines()
    i = next(n for n, l in enumerate(linhas) if inicio in l)
    j = next(n for n, l in enumerate(linhas) if n > i and fim in l)
    return "\n".join(l[26:] if re.match(r"^\d{4}-", l) else l for l in linhas[i : j + 1][:max_linhas])


def principal() -> None:
    rel = json.loads(ler("saida/relatorio_execucao.json"))
    falha = json.loads(ler("logs/cenario_falha/relatorio_execucao.json"))
    audit = [json.loads(l) for l in ler("logs/auditoria.jsonl").splitlines()][:6]
    testes = ler("tests/evidencias/testes_unitarios.txt").strip().splitlines()[-3:]
    node = [l for l in ler("tests/evidencias/teste_integracao_mvp.txt").splitlines() if l.startswith(("✔", "ℹ tests", "ℹ pass", "ℹ fail"))]
    quar: dict[str, int] = {}
    for l in ler("saida/quarentena.jsonl").splitlines():
        m = json.loads(l)["motivo"]
        quar[m] = quar.get(m, 0) + 1
    tabela_quar = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in sorted(quar.items(), key=lambda x: -x[1]))
    pre = lambda t: f"<pre>{escape(t)}</pre>"
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório Técnico GS RPA - Inclui+</title>
<style>
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font: 10.5pt/1.5 Arial, Helvetica, sans-serif; color:#111827; }}
h1 {{ font-size: 20pt; margin:0 0 4pt; }} h2 {{ font-size: 13pt; margin: 18pt 0 5pt; border-bottom: 2px solid #1d4ed8; padding-bottom:2pt; page-break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 10pt 0 3pt; }} .cap {{ color:#4b5563; font-size:9.5pt; }}
table {{ border-collapse: collapse; width:100%; margin: 5pt 0; font-size: 9.5pt; }} th,td {{ border:1px solid #cbd5e1; padding: 3pt 5pt; text-align:left; vertical-align:top; }} th {{ background:#eff6ff; }}
pre {{ background:#f3f4f6; border:1px solid #d1d5db; padding:6pt; font-size:7.8pt; line-height:1.35; white-space:pre-wrap; word-break:break-word; page-break-inside: avoid; }}
code {{ background:#f3f4f6; padding:0 2pt; font-size:9pt; }} img {{ max-width:100%; border:1px solid #d1d5db; page-break-inside: avoid; }}
.capa {{ border-left: 6px solid #1d4ed8; padding-left: 12pt; margin-bottom: 10pt; }}
</style></head><body>
<div class="capa"><h1>Relatório Técnico: robô de triagem de relatos do Inclui+</h1>
<div class="cap">FIAP · Global Solution 2026.2 · CitizenTech · Engenharia de Software 4º ano (turma 4ESPW) · Robotic Process Automation (Bruno Diniz e Cibele Ribeiro)</div></div>

<h2>1. Integrantes</h2>
<table><tr><th>Nome completo</th><th>RM</th></tr>
<tr><td>Kaiky Alvaro de Miranda</td><td>RM98118</td></tr><tr><td>Bruno Eduardo Caputo Paulino</td><td>RM558303</td></tr>
<tr><td>Juan Pinheiro de França</td><td>RM552202</td></tr><tr><td>Lucas Rodrigues da Silva</td><td>RM98344</td></tr></table>

<h2>2. CitizenTech e problema resolvido</h2>
<p><b>Inclui+</b>: guia de lugares acessíveis em São Paulo, com nota separada por necessidade (mobilidade, visão, audição e cognição), fotos como evidência e um assistente em linguagem natural.
Cidadão: pessoas com deficiência, acompanhantes e pessoas idosas. Problema: "acessível" não diz nada, e a pessoa só descobre a barreira quando chega à porta.</p>
<p>Os relatos de quem visitou o local mantêm as notas honestas, mas precisam ser conferidos: tem nota inválida, lugar inexistente, relato duplicado, arquivo quebrado, e um relato de barreira se perde no meio de dezenas de elogios.
Hoje isso é manual e demora; a pessoa com deficiência continua indo a um local que o app diz ser acessível. <b>Código e documentação:</b> repositório do GS RPA (link na seção 14); produto: <a href="https://github.com/kaikyalvaro1708/inclui-gs">github.com/kaikyalvaro1708/inclui-gs</a>.</p>

<h2>3. Objetivo da automação e benefício para o cidadão</h2>
<p>Triar sozinho, todo dia, os relatos novos: validar, corrigir o que for possível, barrar o que estiver errado (com motivo), priorizar as barreiras, detectar lugares com barreira recorrente e
entregar ao MVP dados limpos, sem dados pessoais, e uma fila de revisão para a equipe. <b>Benefício:</b> o intervalo entre "alguém relatou a barreira" e "a nota do local foi revisada" cai de dias para a mesma execução diária;
a pessoa vê uma nota mais confiável e o aviso "relatos recentes de barreira" antes de sair de casa. O robô nunca altera nota sozinho: uma pessoa decide (IA responsável, pessoa no circuito).</p>

<h2>4. Descrição do processo e desenho do fluxo</h2>
<p>Processo completo (PDD) em <code>docs/PDD.md</code>. Fluxo em BPMN 2.0 (arquivo <code>docs/fluxo_bpmn.bpmn</code>, editável no bpmn.io):</p>
<img src="../assets/fluxo_bpmn.png" alt="Fluxo BPMN do robô">
<table><tr><th>#</th><th>Etapa</th></tr>
<tr><td>1</td><td>Carregar o catálogo de lugares (se o mais novo estiver corrompido, usa o anterior)</td></tr>
<tr><td>2</td><td>Listar os arquivos de relatos e calcular o SHA-256 de cada um: o que já foi processado é ignorado</td></tr>
<tr><td>3</td><td>Ler cada arquivo novo ou alterado (com tentativas); arquivo ruim é registrado e pulado</td></tr>
<tr><td>4</td><td>Para cada linha: validar, corrigir ou mandar para a quarentena; proteger dados pessoais</td></tr>
<tr><td>5</td><td>Definir a prioridade e gerar os alertas de barreira recorrente e o resumo por lugar</td></tr>
<tr><td>6</td><td>Gravar as saídas de forma atômica, avisar alertas novos e devolver o código de saída</td></tr></table>

<h2>5. Tecnologias utilizadas e justificativa</h2>
<table><tr><th>Tecnologia</th><th>Por quê</th></tr>
<tr><td>Python 3.12, só biblioteca padrão</td><td>O processo é leitura de arquivos, regras e JSON, o formato que o pipeline de Big Data já entrega. Sem dependências, qualquer avaliador roda com um comando. Versionado e testável no Git.</td></tr>
<tr><td>JSON e JSON Lines</td><td>Contrato com o pipeline (entrada) e com o MVP (saída), legível por pessoas e por código.</td></tr>
<tr><td>unittest e node:test</td><td>26 testes do robô e 6 de contrato com o MVP, sem instalar nada.</td></tr>
<tr><td>JavaScript (ES module)</td><td>Módulo <code>relatosRpa.js</code> no mesmo estilo do MVP, que é um site estático sem backend.</td></tr>
<tr><td>BPMN 2.0</td><td>Padrão aberto para o fluxo; gerado por script para o desenho e o arquivo editável nunca divergirem.</td></tr>
<tr><td>Webhook Discord/Slack (opcional)</td><td>Aviso de alerta novo, com tentativas e pendência em arquivo se estiver fora do ar.</td></tr></table>
<p>Não foi usada ferramenta de tela (UiPath, Power Automate): onde existe arquivo estruturado e API, um robô de tela seria mais lento, frágil e difícil de auditar.</p>

<h2>6. Regras de negócio, decisões e processamento</h2>
<table><tr><th>Regra</th><th>Decisão</th></tr>
<tr><td>Validação (estrutura de decisão por linha)</td><td>id, data, lugar no catálogo, necessidade, tipo, nota 1 a 5. Corrige <code>" Vision"</code>, nota <code>"4"</code> e data sem fuso; o resto vai para a quarentena com motivo fixo.</td></tr>
<tr><td>Duplicidade</td><td>Mesmo <code>relato_id</code>: fica o primeiro, o repetido vai para a quarentena.</td></tr>
<tr><td>Prioridade</td><td>Elogio: baixa. Barreira nota 1-2: alta. Nota 3: média (alta com 2 ou mais fotos). Nota 4-5: baixa (provável erro de preenchimento).</td></tr>
<tr><td>Alerta de barreira recorrente</td><td>3 ou mais relatos média/alta do mesmo lugar e da mesma necessidade em 7 dias. Severidade alta com 3 ou mais de prioridade alta. Status inicial <code>pendente_revisao</code>.</td></tr>
<tr><td>Incremental e idempotente</td><td>Hash por arquivo. Arquivo novo entra; já processado é ignorado; reeditado substitui só o que era dele. Reexecutar gera a mesma saída, byte a byte.</td></tr></table>
<p><b>Resultado nos dados reais</b> (7 arquivos de 12 a 19/11/2026, gerados pelo pipeline de Big Data): {rel['base_total'] + sum(quar.values())} linhas, <b>{rel['base_total']} relatos aceitos</b> e {sum(quar.values())} na quarentena;
prioridades {rel['prioridades']['alta']} alta, {rel['prioridades']['media']} média e {rel['prioridades']['baixa']} baixa; <b>{rel['alertas_total']} alertas</b> de barreira recorrente.</p>
<table><tr><th>Motivo da quarentena</th><th>Linhas</th></tr>{tabela_quar}</table>
<p class="cap">Os relatos são simulados e documentados (o MVP não tem backend e dados reais de pessoas com deficiência são sensíveis). Conclusões sobre os relatos são ilustrativas, não evidência.</p>

<h2>7. Tratamento de exceções e recuperação</h2>
<table><tr><th>Falha prevista</th><th>Recuperação ou registro</th></tr>
<tr><td>Arquivo travado (leitura transitória)</td><td>Até 3 tentativas com espera crescente; cada tentativa vai para o log.</td></tr>
<tr><td>Arquivo vazio ou codificação quebrada</td><td>Registra, pula só esse arquivo, processa o resto e sai com código 1 (parcial). Quando o arquivo for corrigido, é processado na execução seguinte.</td></tr>
<tr><td>Linha com JSON quebrado</td><td>Quarentena; o resto do arquivo segue.</td></tr>
<tr><td>Catálogo mais novo corrompido</td><td>Usa o anterior e registra qual usou.</td></tr>
<tr><td>Sem catálogo ou sem pasta de relatos</td><td>Falha fatal registrada (código 2).</td></tr>
<tr><td>Estado interno corrompido</td><td>Reconstrói a partir dos arquivos de entrada.</td></tr>
<tr><td>Webhook fora do ar (API externa)</td><td>3 tentativas; depois grava em <code>notificacoes_pendentes.jsonl</code> e segue.</td></tr>
<tr><td>Erro inesperado</td><td>Rede de segurança final: log com a pilha, auditoria e código 2. Nenhuma falha é silenciosa.</td></tr></table>
<h3>Evidência: cenário de falha (arquivo vazio, arquivo binário, linha quebrada, catálogo corrompido)</h3>
{pre(trecho_log("CENÁRIO 4", "[código de saída", 40))}

<h2>8. Logs e evidências de auditoria</h2>
<p><code>logs/rpa.log</code> (legível) e <code>logs/auditoria.jsonl</code> (um evento JSON por passo, com data/hora, execução, itens processados, sucessos e falhas). Nenhum log recebe nome, e-mail ou texto de relato.</p>
<h3>Cenário de sucesso, lote 1 e lote 2 (log real)</h3>
{pre(trecho_log("CENÁRIO 1", "[código de saída", 40))}
{pre(trecho_log("CENÁRIO 2", "[código de saída", 40))}
<h3>Reexecução sem nada novo (não duplica)</h3>
{pre(trecho_log("CENÁRIO 3", "[código de saída", 40))}
<h3>Trilha de auditoria (primeiros eventos)</h3>
{pre(chr(10).join(json.dumps(e, ensure_ascii=False) for e in audit))}
<h3>Relatório da execução com falhas (<code>relatorio_execucao.json</code>)</h3>
{pre(json.dumps({k: falha[k] for k in ('status','arquivos','linhas_lidas','rejeitados_por_motivo','correcoes_automaticas','avisos','alertas_total')}, ensure_ascii=False, indent=1))}

<h2>9. Integração com o MVP</h2>
<p>O robô grava em <code>saida/</code> um contrato JSON versionado: <code>resumo_lugares.json</code> e <code>alertas_prioritarios.json</code> (consumidos pelo MVP), <code>relatos_validados.json</code> (também pode alimentar a camada Bronze do Big Data),
<code>quarentena.jsonl</code> e <code>relatorio_execucao.json</code>. O MVP é um site estático, então consome os JSON publicados junto do site pelo módulo <code>relatosRpa.js</code>
(<code>loadRpaData</code>, <code>placeNotice</code>, <code>reviewQueue</code>). Se os arquivos não existirem, o site segue normal. A cadeia completa é: Airflow (Big Data) → <code>chegada/</code> → robô RPA → <code>saida/</code> → MVP e painel.</p>
<img src="../assets/painel_fila_revisao.png" alt="Painel de revisão com a fila de alertas">
<p class="cap">Painel de revisão (<code>integracao_mvp/painel.html</code>) lendo os arquivos gerados pelo robô: 241 relatos validados, 16 alertas, a fila ordenada por severidade e o aviso que o cartão do local mostra.</p>
{pre(chr(10).join(node))}

<h2>10. Testes realizados</h2>
<table><tr><th>Tipo</th><th>Cenários</th></tr>
<tr><td>Sucesso</td><td>Processa e grava as saídas; dois lotes (só o novo entra); reexecução byte a byte igual; limite de arquivos por execução; arquivo reeditado sem relato fantasma; auditoria com data/hora e contagens.</td></tr>
<tr><td>Decisão</td><td>Prioridade (6 casos); alerta só com 3 relatos; necessidades diferentes não somam; elogio não conta; relatos fora da janela de 7 dias não contam; correção versus rejeição; e-mail inválido não derruba o relato.</td></tr>
<tr><td>Falha</td><td>Linhas quebradas e duplicadas; arquivo vazio e binário (código 1); arquivo corrigido depois é reprocessado; catálogo corrompido (fallback); sem catálogo e sem pasta (código 2); estado corrompido; leitura transitória com nova tentativa; webhook fora do ar.</td></tr></table>
{pre(chr(10).join(testes))}
<p>Execução: <code>PYTHONPATH=src python -m unittest discover -s tests -v</code> (26 testes) e <code>node --test integracao_mvp/relatosRpa.test.js</code> (6 testes). Saídas completas em <code>tests/evidencias/</code>.</p>

<h2>11. Segurança e LGPD</h2>
<ul><li><b>Credenciais fora do código:</b> o sal do hash e o webhook vêm de variáveis de ambiente; <code>.env</code> está no <code>.gitignore</code>; o webhook nunca aparece em log (há teste).</li>
<li><b>Minimização e pseudonimização:</b> a saída não tem nome nem e-mail, só <code>autor_hash</code> (SHA-256 com sal, 16 caracteres), que permite contar autores distintos sem identificar ninguém.</li>
<li><b>Texto livre:</b> e-mail, telefone e CPF digitados no relato são removidos antes de gravar.</li>
<li><b>Logs:</b> só ids, contagens e códigos de erro; a auditoria descarta por código campos pessoais; testes automáticos falham se nome ou e-mail aparecerem em log ou saída.</li>
<li><b>Gravação atômica</b> das saídas e <b>pessoa no circuito</b>: o robô levanta alertas, não decide notas.</li>
<li><b>Dados simulados</b> e documentados; autores sintéticos com domínio reservado <code>example.com</code>.</li></ul>
<p><b>ODS:</b> 10 (redução das desigualdades, meta 10.2), 11 (cidades inclusivas, metas 11.2 e 11.7), 9 (infraestrutura e inovação) e 3 (acesso a serviços de saúde sem barreira).</p>

<h2>12. Limitações e próximos passos</h2>
<ul><li>Os relatos são simulados; com usuários reais, o robô lê a mesma pasta sem mudança de código.</li>
<li>O limite de 3 relatos em 7 dias é uma regra inicial, ajustável em <code>config.py</code>; deve ser calibrada com dados reais.</li>
<li>O MVP hoje não tem backend: a integração é por arquivos publicados com o site. Com backend, o mesmo contrato pode virar API.</li></ul>

<h2>13. Como reproduzir</h2>
{pre("export PYTHONPATH=src   # PowerShell: $env:PYTHONPATH = 'src'\npython scripts/demo.py                      # 4 cenários: sucesso, lotes, reexecução, falhas\npython -m unittest discover -s tests -v     # 26 testes\nnode --test integracao_mvp/relatosRpa.test.js\npython -m http.server 8000                  # painel em http://localhost:8000/integracao_mvp/painel.html")}

<h2>14. Links</h2>
<table><tr><th>Item</th><th>Link</th></tr>
<tr><td>Repositório GitHub do GS RPA (público)</td><td>https://github.com/JuanPinheiroFIAP/GS-RPA</td></tr>
<tr><td>Vídeo demonstrativo (até 3 min)</td><td><b>[preencher com a URL do vídeo]</b></td></tr>
<tr><td>Repositório do MVP</td><td>https://github.com/kaikyalvaro1708/inclui-gs</td></tr>
<tr><td>MVP publicado</td><td>https://d3ls3zp8wqbtsw.cloudfront.net</td></tr></table>
</body></html>"""
    destino = RAIZ / "docs" / "relatorio_tecnico.html"
    destino.write_text(html, encoding="utf-8")
    navegador = next((n for n in NAVEGADORES if Path(n).exists()), None)
    if not navegador:
        sys.exit("Edge/Chrome não encontrado: abra docs/relatorio_tecnico.html e imprima em PDF.")
    pdf = RAIZ / "docs" / "Relatorio_GS_RPA.pdf"
    subprocess.run([navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", destino.as_uri()], check=True, capture_output=True)
    print("gerado:", pdf)


if __name__ == "__main__":
    principal()
