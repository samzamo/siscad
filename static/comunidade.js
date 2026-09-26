// static/comunidade.js
// Ao sair do campo de endereço, geocodifica (OpenStreetMap/Nominatim,
// gratuito, sem chave) e manda pro backend achar em qual comunidade
// (AIS 18) aquele ponto cai. Tudo silencioso em caso de falha -- nunca
// trava o cadastro por causa disso.

async function _geocodificarEndereco(endereco) {
  try {
    const resp = await fetch(
      'https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(endereco)
    );
    const resultados = await resp.json();
    if (resultados && resultados.length) {
      return { lat: parseFloat(resultados[0].lat), lon: parseFloat(resultados[0].lon) };
    }
  } catch (e) { /* silencioso */ }
  return null;
}

async function _localizarComunidadePorLatLon(lat, lon) {
  try {
    const dados = new FormData();
    dados.append('lat', lat);
    dados.append('lon', lon);
    const resp = await fetch('/comunidade/localizar', { method: 'POST', body: dados });
    const json = await resp.json();
    return json.ok ? (json.comunidade || null) : null;
  } catch (e) { /* silencioso */ }
  return null;
}

/**
 * Liga a detecção automática de comunidade a um campo de endereço.
 * opcoes: { enderecoInputId, comunidadeHiddenId, displayId, bairroInputId }
 * bairroInputId (opcional): id do combobox de bairro -- quando o endereço
 * digitado não tem o bairro (ex.: "Rua das Acácias, 300"), soma o bairro
 * selecionado na busca pra geocodificar com mais precisão.
 */
function configurarAutoComunidade(opcoes) {
  const enderecoInput = document.getElementById(opcoes.enderecoInputId);
  const hiddenInput = document.getElementById(opcoes.comunidadeHiddenId);
  const display = opcoes.displayId ? document.getElementById(opcoes.displayId) : null;
  const bairroInput = opcoes.bairroInputId ? document.getElementById(opcoes.bairroInputId) : null;
  if (!enderecoInput || !hiddenInput) return;

  async function atualizar() {
    const endereco = enderecoInput.value.trim();
    if (!endereco) {
      hiddenInput.value = '';
      if (display) display.textContent = '';
      return;
    }
    if (display) display.textContent = '📍 Identificando comunidade...';

    const bairro = bairroInput ? bairroInput.value.trim() : '';
    const buscaComBairro = bairro ? `${endereco}, ${bairro}` : endereco;

    // Tenta com o bairro junto primeiro (mais preciso); se não achar, cai
    // pra busca só com o endereço digitado.
    let ponto = bairro ? await _geocodificarEndereco(buscaComBairro) : null;
    if (!ponto) ponto = await _geocodificarEndereco(endereco);

    if (!ponto) {
      if (display) display.textContent = '⚠️ Não consegui localizar esse endereço no mapa.';
      return;
    }
    const comunidade = await _localizarComunidadePorLatLon(ponto.lat, ponto.lon);
    hiddenInput.value = comunidade || '';
    if (display) {
      display.textContent = comunidade
        ? '📍 Comunidade: ' + comunidade
        : '📍 Endereço fora das comunidades mapeadas.';
    }
  }

  enderecoInput.addEventListener('blur', atualizar);
  if (bairroInput) bairroInput.addEventListener('change', atualizar);
}
