// static/importar-mandado.js
// Lógica da tela "Importar Mandado (PDF)".

let _mandadoExtraido = {};
let _geocodeAtual = null; // { endereco, lat, lon } -- usado pra gerar link curto do Maps

document.addEventListener('DOMContentLoaded', function () {
  const dropzone = document.getElementById('dropzone');
  const inputPdf = document.getElementById('inputPdf');
  const status = document.getElementById('statusExtracao');
  const overlay = document.getElementById('modalMandado');
  const fechar = document.getElementById('fecharModalMandado');

  dropzone.addEventListener('click', () => inputPdf.click());
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('arrastando'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('arrastando'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('arrastando');
    if (e.dataTransfer.files.length) {
      inputPdf.files = e.dataTransfer.files;
      processarArquivo();
    }
  });
  inputPdf.addEventListener('change', processarArquivo);

  fechar.addEventListener('click', () => overlay.classList.remove('aberto'));
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.classList.remove('aberto'); });

  function processarArquivo() {
    const arquivo = inputPdf.files[0];
    if (!arquivo) return;

    const progresso = document.getElementById('progressoExtracao');
    const barra = document.getElementById('progressoBarra');
    const legenda = document.getElementById('progressoLegenda');

    status.textContent = '';
    status.className = 'status-extracao';

    barra.classList.remove('indeterminada');
    barra.style.width = '0%';
    legenda.textContent = 'Enviando PDF...';
    progresso.classList.add('mostrando');

    const dados = new FormData();
    dados.append('arquivo', arquivo);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/mandado/extrair_pdf');

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        barra.style.width = pct + '%';
        if (pct >= 100) {
          legenda.textContent = 'Extraindo dados do PDF...';
          barra.classList.add('indeterminada');
        }
      }
    });

    xhr.addEventListener('load', () => {
      progresso.classList.remove('mostrando');
      barra.classList.remove('indeterminada');
      barra.style.width = '0%';

      let resp;
      try {
        resp = JSON.parse(xhr.responseText);
      } catch (e) {
        status.textContent = 'Erro de conexão ao enviar o PDF.';
        status.className = 'status-extracao erro';
        return;
      }

      if (!resp.ok) {
        status.textContent = resp.erro || 'Não consegui ler os dados desse PDF.';
        status.className = 'status-extracao erro';
        return;
      }
      status.textContent = '✅ Dados extraídos! Revise antes de cadastrar.';
      status.className = 'status-extracao ok';
      _mandadoExtraido = resp.dados;
      preencherModal(resp.dados);
      overlay.classList.add('aberto');
    });

    xhr.addEventListener('error', () => {
      progresso.classList.remove('mostrando');
      barra.classList.remove('indeterminada');
      barra.style.width = '0%';
      status.textContent = 'Erro de conexão ao enviar o PDF.';
      status.className = 'status-extracao erro';
    });

    xhr.send(dados);
  }
});

function vulgoFallback(d) {
  // Sem alcunha no mandado -> usa o 2º nome + bairro como vulgo, pra
  // ajudar a identificar/pesquisar o alvo mesmo sem apelido conhecido.
  const partesNome = (d.nome || '').trim().split(/\s+/).filter(Boolean);
  const segundoNome = partesNome.length > 1 ? partesNome[1] : '';
  const bairro = (d.bairro || '').trim();
  return [segundoNome, bairro].filter(Boolean).join(' ');
}

function preencherModal(d) {
  document.getElementById('nome').value = d.nome || '';
  document.getElementById('vulgo').value = d.alcunha || vulgoFallback(d);
  document.getElementById('genitora').value = d.genitora || '';
  document.getElementById('octopus').value = d.endereco_bruto || '';
  document.getElementById('data_nascimento').value = d.data_nascimento || '';

  document.getElementById('mandado_numero').value = d.numero_documento || '';
  document.getElementById('mandado_data').value = d.data_mandado || '';
  document.getElementById('mandado_tipificacao').value = d.tipificacao || '';
  document.getElementById('mandado_comarca').value = d.comarca || '';
  document.getElementById('mandado_validade').value = d.validade || '';
  document.getElementById('mandado_endereco').value = d.endereco_bruto || '';

  // Município/bairro pré-selecionados (já vêm no mesmo formato dos <select>)
  const municipioSelect = document.getElementById('municipio');
  const bairroSelect = document.getElementById('bairro');
  municipioSelect.dataset.atual = d.municipio_normalizado || '';
  bairroSelect.dataset.atual = d.bairro_normalizado || '';

  inicializarCombosDinamicos({
    faccaoId: 'faccao',
    municipioId: 'municipio',
    bairroId: 'bairro',
  });

  // Anotações estruturadas com o que veio do PDF (documento, filiação, mandado)
  const itens = [];
  let _seq = 0;
  const _novoId = () => Date.now() + Math.random() + (_seq++);
  const doc = [];
  if (d.cpf) doc.push('CPF: ' + d.cpf);
  if (d.rg) doc.push('RG: ' + d.rg);
  if (d.data_nascimento) doc.push('Nascimento: ' + d.data_nascimento);
  if (d.natural_de) doc.push('Natural de: ' + d.natural_de);
  if (d.sexo) doc.push('Sexo: ' + d.sexo);
  if (d.cor) doc.push('Cor: ' + d.cor);
  if (doc.length) itens.push({ _localId: _novoId(), tipo: 'Documento', data: '', contexto: doc.join(' · ') });

  if (d.genitor) itens.push({ _localId: _novoId(), tipo: 'Filiação', data: '', contexto: 'Pai: ' + d.genitor });

  const mandadoInfo = [];
  if (d.tipo_mandado) mandadoInfo.push(d.tipo_mandado);
  if (d.numero_documento) mandadoInfo.push('Nº ' + d.numero_documento);
  if (d.processo) mandadoInfo.push('Processo ' + d.processo);
  if (d.orgao_judicial) mandadoInfo.push(d.orgao_judicial);
  if (d.tipificacao) mandadoInfo.push('Tipificação: ' + d.tipificacao);
  if (d.prazo_minimo) mandadoInfo.push('Prazo mínimo: ' + d.prazo_minimo);
  if (d.validade) mandadoInfo.push('Validade: ' + d.validade);
  if (mandadoInfo.length) itens.push({ _localId: _novoId(), tipo: 'Mandado', data: '', contexto: mandadoInfo.join(' · ') });

  configurarAnotacoes({ modo: 'local', containerId: 'anotacoes-lista', hiddenInputId: 'anotacoes_json', itensLocais: itens });
  document.getElementById('anotacoes_json').value = JSON.stringify(itens.map(i => ({ data: i.data, tipo: i.tipo, contexto: i.contexto })));

  atualizarMapaEWhats();
}

function montarLinkGoogleMaps(endereco) {
  return 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(endereco);
}

function montarLinkGoogleMapsCurto(endereco) {
  // Se esse endereço já foi geocodificado (mesma consulta usada pra
  // desenhar o mapa), usa as coordenadas -- gera um link bem mais curto
  // do que a busca por texto completo. Sem chamada de rede extra.
  if (_geocodeAtual && _geocodeAtual.endereco === endereco) {
    return `https://maps.google.com/?q=${_geocodeAtual.lat},${_geocodeAtual.lon}`;
  }
  return montarLinkGoogleMaps(endereco);
}

function atualizarMapaEWhats() {
  const endereco = document.getElementById('mandado_endereco').value.trim();
  const linkMaps = document.getElementById('linkGoogleMaps');
  linkMaps.href = endereco ? montarLinkGoogleMapsCurto(endereco) : '#';

  if (!endereco) {
    document.getElementById('mapaPreview').classList.remove('mostrando');
    return;
  }

  // Geocodificação gratuita (Nominatim/OpenStreetMap, sem chave de API).
  fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(endereco))
    .then((r) => r.json())
    .then((resultados) => {
      const mapaPreview = document.getElementById('mapaPreview');
      if (!resultados || !resultados.length) {
        _geocodeAtual = null;
        mapaPreview.classList.remove('mostrando');
        return;
      }
      const { lat, lon } = resultados[0];
      _geocodeAtual = { endereco, lat, lon };
      linkMaps.href = montarLinkGoogleMapsCurto(endereco);
      const delta = 0.006;
      const bbox = [
        (parseFloat(lon) - delta).toFixed(6), (parseFloat(lat) - delta).toFixed(6),
        (parseFloat(lon) + delta).toFixed(6), (parseFloat(lat) + delta).toFixed(6),
      ].join('%2C');
      document.getElementById('mapaIframe').src =
        `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&marker=${lat}%2C${lon}&layer=mapnik`;
      mapaPreview.classList.add('mostrando');
    })
    .catch(() => {
      _geocodeAtual = null;
      document.getElementById('mapaPreview').classList.remove('mostrando');
    });
}

async function obterLinkCurto(url) {
  // Encurta via TinyURL (pelo backend, sem depender de CORS). Se falhar
  // ou demorar, devolve o link original -- a mensagem nunca quebra.
  try {
    const resp = await fetch('/mandado/encurtar_link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const dados = await resp.json();
    if (resp.ok && dados.ok && dados.url) return dados.url;
  } catch (e) {
    // sem conexão / rota indisponível -- segue com o link original
  }
  return url;
}

async function montarMensagemWhatsapp() {
  const nome = document.getElementById('nome').value.trim();
  const genitora = document.getElementById('genitora').value.trim();
  const nascimento = document.getElementById('data_nascimento').value.trim();
  const tipificacao = document.getElementById('mandado_tipificacao').value.trim();
  const dataMandado = document.getElementById('mandado_data').value.trim();
  const comarca = document.getElementById('mandado_comarca').value.trim();
  const numero = document.getElementById('mandado_numero').value.trim();
  const endereco = document.getElementById('mandado_endereco').value.trim();

  const linhas = ['🚨 *MANDADO*'];
  if (nome) linhas.push('*Nome:* ' + nome);
  if (genitora) linhas.push('*Genitora:* ' + genitora);
  if (nascimento) linhas.push('*Nascimento:* ' + nascimento);
  if (tipificacao) linhas.push('*Tipo de crime:* ' + tipificacao);
  if (dataMandado) linhas.push('*Data do mandado:* ' + dataMandado);
  if (comarca) linhas.push('*Comarca:* ' + comarca);
  if (numero) linhas.push('*Nº do mandado:* ' + numero);
  if (endereco) linhas.push('*Endereço:* ' + endereco);
  if (endereco) {
    const linkCurto = await obterLinkCurto(montarLinkGoogleMapsCurto(endereco));
    linhas.push('📍 ' + linkCurto);
  }

  return linhas.join('\n');
}

function copiarTextoFallback(texto) {
  // Fallback para quando a Clipboard API não está disponível (ex.: página servida
  // fora de HTTPS/localhost, ou navegador mais antigo).
  const textarea = document.createElement('textarea');
  textarea.value = texto;
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let sucesso = false;
  try {
    sucesso = document.execCommand('copy');
  } catch (e) {
    sucesso = false;
  }
  document.body.removeChild(textarea);
  return sucesso;
}

async function copiarMensagemWhats(botao) {
  if (botao) { botao.disabled = true; botao.dataset.textoOriginal = botao.textContent; botao.textContent = '⏳ Gerando link...'; }

  const texto = await montarMensagemWhatsapp();

  const restaurarBotao = () => {
    if (botao) { botao.disabled = false; botao.textContent = botao.dataset.textoOriginal; }
  };

  if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
    navigator.clipboard.writeText(texto)
      .then(() => alert('Mensagem copiada!'))
      .catch(() => {
        if (copiarTextoFallback(texto)) {
          alert('Mensagem copiada!');
        } else {
          alert('Não consegui copiar automaticamente. Selecione e copie manualmente:\n\n' + texto);
        }
      })
      .finally(restaurarBotao);
    return;
  }

  if (copiarTextoFallback(texto)) {
    alert('Mensagem copiada!');
  } else {
    alert('Não consegui copiar automaticamente. Selecione e copie manualmente:\n\n' + texto);
  }
  restaurarBotao();
}

