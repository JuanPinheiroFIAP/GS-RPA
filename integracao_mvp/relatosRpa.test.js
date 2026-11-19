// Teste de contrato: o MVP consegue ler e usar o que o robô gravou em saida/.
// Rodar (Node 22+):  node --test integracao_mvp/relatosRpa.test.js   (depois de python -m rpa_relatos)
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { loadRpaData, placeNotice, reviewQueue } from './relatosRpa.js';

const saida = (nome) => fileURLToPath(new URL(`../saida/${nome}`, import.meta.url));
const fetchLocal = async (url) => {
  try {
    const texto = await readFile(url.startsWith('file:') ? fileURLToPath(url) : url, 'utf8');
    return { ok: true, status: 200, json: async () => JSON.parse(texto) };
  } catch {
    return { ok: false, status: 404, json: async () => ({}) };
  }
};
const base = fileURLToPath(new URL('../saida/', import.meta.url));

test('carrega os arquivos reais gerados pelo robô', async () => {
  const dados = await loadRpaData(base, fetchLocal);
  assert.ok(dados, 'saida/ do robô não encontrada: rode python -m rpa_relatos antes');
  assert.ok(Object.keys(dados.lugares).length >= 20);
  assert.ok(dados.alertas.length > 0);
});

test('lugar com alerta mostra aviso do nível alert, filtrado pela necessidade', async () => {
  const dados = await loadRpaData(base, fetchLocal);
  const alerta = dados.alertas[0];
  const aviso = placeNotice(dados, alerta.lugar_id, [alerta.necessidade]);
  assert.equal(aviso.level, 'alert');
  assert.equal(aviso.relatos, alerta.relatos_na_janela);
  const outra = ['mobility', 'vision', 'hearing', 'cognitive'].find((n) => !dados.lugares[alerta.lugar_id].por_necessidade[n]?.alerta);
  if (outra) assert.notEqual(placeNotice(dados, alerta.lugar_id, [outra])?.level, 'alert');
});

test('lugar desconhecido ou sem relatos não gera aviso', async () => {
  const dados = await loadRpaData(base, fetchLocal);
  assert.equal(placeNotice(dados, 'nao-existe', ['vision']), null);
  assert.equal(placeNotice(null, 'cafe-aurora', []), null);
});

test('fila de revisão vem ordenada da severidade mais alta para a menor', async () => {
  const dados = await loadRpaData(base, fetchLocal);
  const fila = reviewQueue(dados);
  const peso = { alta: 0, media: 1 };
  for (let i = 1; i < fila.length; i++) assert.ok(peso[fila[i - 1].severidade] <= peso[fila[i].severidade]);
});

test('se o robô não gerou arquivos, o MVP segue sem quebrar', async () => {
  assert.equal(await loadRpaData('./pasta-que-nao-existe/', fetchLocal), null);
  assert.equal(await loadRpaData('./x/', async () => { throw new Error('sem rede'); }), null);
});

test('os arquivos não carregam dado pessoal', async () => {
  for (const nome of ['relatos_validados.json', 'resumo_lugares.json', 'alertas_prioritarios.json']) {
    const texto = await readFile(saida(nome), 'utf8');
    assert.doesNotMatch(texto, /@|autor_email|autor_nome/, nome);
  }
});
