/**
 * Consumo da saída do robô RPA pelo MVP Inclui+ (mesmo estilo dos módulos de `site/assets/js/data/`).
 *
 * Contrato (JSON, versão 1), gravado pelo robô em `saida/` e publicado junto do site em `site/assets/data/`:
 *   resumo_lugares.json       { dados_ate, lugares: { [lugar_id]: { nome, total_relatos, tem_alerta, por_necessidade: {...} } } }
 *   alertas_prioritarios.json { dados_ate, total, alertas: [ { lugar_id, necessidade, severidade, relatos_na_janela, ... } ] }
 *
 * Se os arquivos não existirem ou vierem quebrados, o MVP segue sem o aviso (degrada com elegância).
 */

export const NEED_LABEL = { mobility: 'mobilidade', vision: 'visão', hearing: 'audição', cognitive: 'cognição' };

const lerJson = async (url, fetchFn) => {
  const resposta = await fetchFn(url, { cache: 'no-cache' });
  if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
  return resposta.json();
};

/** Carrega os dois arquivos do robô. Devolve null (nunca lança) se algum faltar: o site não pode quebrar por causa do robô. */
export async function loadRpaData(baseUrl = './assets/data/', fetchFn = globalThis.fetch) {
  try {
    const [resumo, alertas] = await Promise.all([
      lerJson(`${baseUrl}resumo_lugares.json`, fetchFn),
      lerJson(`${baseUrl}alertas_prioritarios.json`, fetchFn),
    ]);
    if (!resumo?.lugares || !Array.isArray(alertas?.alertas)) return null;
    return { lugares: resumo.lugares, alertas: alertas.alertas, dadosAte: resumo.dados_ate ?? null };
  } catch {
    return null;
  }
}

/**
 * Aviso para o cartão do local, filtrado pelas necessidades da pessoa.
 * Devolve { level: 'alert' | 'info', message, relatos } ou null quando não há nada a dizer.
 */
export function placeNotice(data, placeId, needs = []) {
  const lugar = data?.lugares?.[placeId];
  if (!lugar || lugar.total_relatos === 0) return null;

  const alvo = needs.length ? needs : Object.keys(lugar.por_necessidade);
  const emAlerta = alvo.filter((n) => lugar.por_necessidade[n]?.alerta);
  if (emAlerta.length > 0) {
    const nomes = emAlerta.map((n) => NEED_LABEL[n]).join(' e ');
    const relatos = data.alertas
      .filter((a) => a.lugar_id === placeId && emAlerta.includes(a.necessidade))
      .reduce((soma, a) => soma + a.relatos_na_janela, 0);
    return {
      level: 'alert',
      relatos,
      message: `Atenção: ${relatos} relatos recentes de barreira para ${nomes}. A equipe está revisando a nota deste local.`,
    };
  }

  const relatosAlvo = alvo.reduce((soma, n) => soma + (lugar.por_necessidade[n]?.relatos ?? 0), 0);
  if (relatosAlvo === 0) return null;
  return { level: 'info', relatos: relatosAlvo, message: `${relatosAlvo} relatos de pessoas que visitaram o local.` };
}

/** Lugares com alerta aberto, do mais grave para o menos grave (para a fila de revisão da equipe). */
export function reviewQueue(data) {
  const peso = { alta: 0, media: 1 };
  return [...(data?.alertas ?? [])].sort(
    (a, b) => peso[a.severidade] - peso[b.severidade] || b.relatos_na_janela - a.relatos_na_janela,
  );
}
