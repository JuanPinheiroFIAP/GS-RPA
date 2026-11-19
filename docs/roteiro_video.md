# Roteiro do vídeo (até 3 minutos)

Gravar a tela com o terminal na raiz do repositório e o navegador com `integracao_mvp/painel.html` aberto (`python -m http.server 8000`).
Antes de gravar: `python scripts/demo.py > /dev/null` uma vez para ter logs de exemplo; para a gravação, apague `estado/` e `saida/`.

| Tempo | O que mostrar | O que falar |
| --- | --- | --- |
| 0:00 a 0:25 | Slide ou README: o Inclui+ e o problema | "O Inclui+ diz à pessoa com deficiência se um lugar é acessível para a necessidade dela. A prova são os relatos de quem visitou. Conferi-los à mão leva de 40 a 60 minutos por dia, e um relato grave se perde no meio. O robô faz essa triagem." |
| 0:25 a 0:50 | `docs/fluxo_bpmn.svg` | "O robô lê os relatos que o pipeline de Big Data deixa em `chegada/`, valida cada linha, decide a prioridade, protege dados pessoais e entrega JSON para o MVP." |
| 0:50 a 1:30 | Terminal: `python -m rpa_relatos --max-arquivos 3` e depois `python -m rpa_relatos` | "Lote 1: 3 arquivos, 101 relatos aceitos, 10 na quarentena. Lote 2: ele reconhece os 3 já processados pelo hash e só lê os novos. Se rodar de novo, nada duplica." Mostrar `saida/quarentena.jsonl` com os motivos. |
| 1:30 a 2:05 | Painel no navegador | "**Regra de decisão:** 3 ou mais relatos de barreira do mesmo lugar e da mesma necessidade em 7 dias viram alerta. Aqui o Cinema do Largo tem 6 para mobilidade. **Integração com o MVP:** este é o aviso que o cartão do local mostra. O robô não muda a nota: quem decide é a equipe." Trocar o local e a necessidade no seletor. |
| 2:05 a 2:40 | Terminal: `python scripts/demo.py` (cenário 4) ou só o trecho final | "**Falhas:** arquivo vazio, arquivo binário e linha quebrada. O robô registra cada uma, pula só o arquivo ruim, processa o resto e sai com código 1, para o agendador saber que foi parcial. Catálogo corrompido: cai para o anterior." Mostrar `logs/auditoria.jsonl` e `rpa.log`. |
| 2:40 a 3:00 | `PYTHONPATH=src python -m unittest discover -s tests` e a verificação de LGPD | "26 testes de sucesso, decisão e falha. Na saída não há nome nem e-mail: o autor é um hash com sal. ODS 10 e 11: a barreira relatada vira revisão no mesmo dia." |
