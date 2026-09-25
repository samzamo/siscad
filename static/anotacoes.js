// static/anotacoes.js
// Modal "+" de anotações (Data + Tipo + Contexto), exibidas como balões
// com botões de editar/excluir. Usado em duas telas:
//
//   modo "local"    -> Cadastro de alvo (cadastro_alvo.html). A pessoa
//                       ainda não tem id, então as anotações ficam só na
//                       memória do navegador e são enviadas junto do
//                       formulário principal (campo oculto JSON) na hora
//                       de salvar o cadastro.
//   modo "servidor" -> Modal "Alterar dados" (pesquisar_alvo.html). A
//                       pessoa já existe, então cada anotação é salva na
//                       hora, direto no banco, via /anotacoes/<id>.
//
// Depende de funções já existentes em opcoes.js (buscarOpcoes, enviarJson,
// preencherSelect) -- por isso opcoes.js precisa ser carregado ANTES deste
// arquivo na página.

let _anotConfig = null;   // { modo, pessoaId?, containerId, hiddenInputId?, itensLocais? }
let _anotEditandoId = null; // id (servidor) ou _localId (local) da anotação em edição; null = criando

function configurarAnotacoes(config) {
  _anotConfig = Object.assign({ itensLocais: [] }, config);
  if (_anotConfig.modo === 'servidor') {
    carregarAnotacoesServidor();
  } else {
    renderizarAnotacoes(_anotConfig.itensLocais);
  }
}

async function carregarOpcoesTipoAnotacao() {
  const select = document.getElementById('anot-tipo');
  if (!select) return;
  const valorAtual = select.value;
  const lista = await buscarOpcoes('crime');
  preencherSelect(select, lista, valorAtual);
}

function abrirModalAnotacao(anotacaoExistente) {
  carregarOpcoesTipoAnotacao();

  // A DATA começa sempre em branco ao criar uma nova anotação -- nunca
  // pré-preenchida com o dia de hoje (era esse o bug antigo).
  document.getElementById('anot-data').value = anotacaoExistente ? (anotacaoExistente.data || '') : '';
  document.getElementById('anot-contexto').value = anotacaoExistente ? (anotacaoExistente.contexto || '') : '';
  document.getElementById('anot-tipo').value = anotacaoExistente ? (anotacaoExistente.tipo || '') : '';

  _anotEditandoId = anotacaoExistente
    ? (_anotConfig.modo === 'local' ? anotacaoExistente._localId : anotacaoExistente.id)
    : null;

  document.getElementById('anot-modal-titulo').textContent =
    anotacaoExistente ? 'Editar anotação' : 'Nova anotação';
  document.getElementById('modal-anotacao').style.display = 'flex';
}

function fecharModalAnotacao() {
  document.getElementById('modal-anotacao').style.display = 'none';
  _anotEditandoId = null;
}

async function salvarAnotacaoModal() {
  const data = document.getElementById('anot-data').value;
  const tipo = document.getElementById('anot-tipo').value;
  const contexto = document.getElementById('anot-contexto').value.trim();

  if (!contexto) {
    alert('Escreva o contexto da anotação.');
    return;
  }

  if (_anotConfig.modo === 'local') {
    if (_anotEditandoId !== null) {
      const item = _anotConfig.itensLocais.find(i => i._localId === _anotEditandoId);
      if (item) Object.assign(item, { data, tipo, contexto });
    } else {
      _anotConfig.itensLocais.push({ _localId: Date.now() + Math.random(), data, tipo, contexto });
    }
    renderizarAnotacoes(_anotConfig.itensLocais);
    salvarAnotacoesNoCampoOculto();
    fecharModalAnotacao();
    return;
  }

  const corpo = { data, tipo, contexto };
  const url = _anotEditandoId ? `/anotacoes/${_anotEditandoId}` : `/anotacoes/${_anotConfig.pessoaId}`;
  const metodo = _anotEditandoId ? 'PUT' : 'POST';
  const { ok, dados } = await enviarJson(url, metodo, corpo);
  if (!ok) {
    alert(dados.erro || 'Não foi possível salvar a anotação.');
    return;
  }
  fecharModalAnotacao();
  carregarAnotacoesServidor();
}

async function carregarAnotacoesServidor() {
  try {
    const resp = await fetch(`/anotacoes/${_anotConfig.pessoaId}`);
    const lista = resp.ok ? await resp.json() : [];
    renderizarAnotacoes(lista);
  } catch (e) {
    renderizarAnotacoes([]);
  }
}

function _escaparHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto || '';
  return div.innerHTML;
}

function renderizarAnotacoes(lista) {
  if (_anotConfig.modo === 'servidor') {
    _anotConfig.itensAtuais = lista;
  }

  const container = document.getElementById(_anotConfig.containerId);
  if (!container) return;
  container.innerHTML = '';

  if (!lista.length) {
    container.innerHTML = '<p class="anotacoes-vazio">Nenhuma anotação ainda. Clique em "+" para adicionar.</p>';
    return;
  }

  lista.forEach(item => {
    const balao = document.createElement('div');
    balao.className = 'anotacao-balao';
    const dataFormatada = item.data ? item.data.split('-').reverse().join('/') : '';
    balao.innerHTML = `
      <div class="anotacao-cabecalho">
        <span class="anotacao-tags">
          ${dataFormatada ? `<span class="anotacao-data">${dataFormatada}</span>` : ''}
          ${item.tipo ? `<span class="anotacao-tipo">${_escaparHtml(item.tipo)}</span>` : ''}
        </span>
        <span class="anotacao-acoes">
          <button type="button" title="Editar anotação">✏️</button>
          <button type="button" title="Excluir anotação">🗑️</button>
        </span>
      </div>
      <div class="anotacao-contexto">${_escaparHtml(item.contexto)}</div>
    `;
    const [btnEditar, btnExcluir] = balao.querySelectorAll('.anotacao-acoes button');
    btnEditar.addEventListener('click', () => abrirModalAnotacao(item));
    btnExcluir.addEventListener('click', () => excluirAnotacao(item));
    container.appendChild(balao);
  });
}

async function excluirAnotacao(item) {
  if (!confirm('Excluir esta anotação?')) return;

  if (_anotConfig.modo === 'local') {
    _anotConfig.itensLocais = _anotConfig.itensLocais.filter(i => i._localId !== item._localId);
    renderizarAnotacoes(_anotConfig.itensLocais);
    salvarAnotacoesNoCampoOculto();
    return;
  }

  const { ok, dados } = await enviarJson(`/anotacoes/${item.id}`, 'DELETE');
  if (!ok) {
    alert(dados.erro || 'Não foi possível excluir.');
    return;
  }
  carregarAnotacoesServidor();
}

function salvarAnotacoesNoCampoOculto() {
  const hidden = document.getElementById(_anotConfig.hiddenInputId);
  if (!hidden) return;
  hidden.value = JSON.stringify(
    _anotConfig.itensLocais.map(i => ({ data: i.data, tipo: i.tipo, contexto: i.contexto }))
  );
}
