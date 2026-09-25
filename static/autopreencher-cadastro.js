// static/autopreencher-cadastro.js
// Botão "CAD. TEX." no Cadastro de Alvo: cola um texto solto (bilhete,
// mensagem, denúncia, ficha, etc.) e tenta identificar cada campo do
// formulário procurando rótulos conhecidos (Nome, Vulgo/Alcunha, Genitora,
// Facção, Município, Bairro, Endereço, Octopus Asint). Tudo roda no
// navegador, sem enviar nada pro servidor -- zero custo extra.
//
// Extras desta versão:
//  - Se o texto tiver mais de um endereço, usa o PRIMEIRO para preencher
//    Município/Bairro/Endereço e joga os demais em Anotações.
//  - Tenta pegar também o número da casa (rótulo "Número:"), que antes
//    era descartado -- só junta ao endereço quando o "Número:" vem logo
//    depois de um "Endereço:"/"Logradouro:" (evita confundir com número
//    de RG/documento, que usa o mesmo rótulo em fichas civis).
//  - Se achar referência a procedimento (IPL, Inquérito, Processo, APF,
//    TCO, B.O.) e/ou artigos de lei, joga isso em Anotações também.

function limparTextoJs(texto) {
  return (texto || '').toString()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toUpperCase().trim();
}

function sleepAutopreencher(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

// Cada campo pode ter mais de um "apelido" de rótulo (ex: Vulgo/Alcunha).
// O valor é lido do fim do rótulo até o próximo rótulo reconhecido (ou até
// o fim do texto), então funciona tanto com um campo por linha quanto com
// tudo num parágrafo só.
const _CAMPOS_AUTOPREENCHER = [
  { campo: 'nome', regex: /\bnome(?:\s+completo)?\s*[:\-–]/gi },
  { campo: 'vulgo', regex: /\b(?:vulgo|alcunha|apelido)\s*[:\-–]/gi },
  { campo: 'genitora', regex: /\b(?:genitora|m[ãa]e)\s*[:\-–]/gi },
  { campo: 'faccao', regex: /\bfac[çc][ãa]o\s*[:\-–]/gi },
  { campo: 'municipio', regex: /\b(?:munic[ií]pio|cidade)\s*[:\-–]/gi },
  { campo: 'bairro', regex: /\bbairro\s*[:\-–]/gi },
  { campo: 'endereco', regex: /\b(?:endere[çc]o|logradouro)\s*[:\-–]/gi },
  { campo: 'octopusasint', regex: /\boctopus\s*asint\s*[:\-–]/gi },
  // "Número" também é capturado como campo (não só como limite) para dar
  // pra reaproveitar o valor quando ele pertence a um endereço. Ver a
  // etapa de "anexar número ao endereço" abaixo para saber como evitamos
  // pegar número de RG/documento por engano.
  { campo: 'numero', regex: /\bn(?:[uú]mero|[ºo°]\.?)\s*[:\-–]/gi },
];

// Rótulos que aparecem em fichas/boletins (SIP e afins) mas não preenchem
// nenhum campo do cadastro -- servem só de "cerca", pra um campo que
// queremos não vazar pro texto do campo vizinho (ex: sem isso, "Mãe"
// vazaria pro "Pai", "Bairro" vazaria pro "Telefone" etc).
const _ROTULOS_LIMITE = [
  /\bn[ºo]\s*sip\s*[:\-–]/gi,
  /\bsexo\s*[:\-–]/gi,
  /\bdata\s+de\s+nasc(?:imento)?\s*[:\-–]/gi,
  /\bn[ºo]\s*da\s*identifica[çc][ãa]o\s*criminal\s*[:\-–]/gi,
  /\bpai\s*[:\-–]/gi,
  /\bpa[íi]s\s*[:\-–]/gi,
  /\buf\s*[:\-–]/gi,
  /\brg\s*[:\-–]/gi,
  /\bemissor\s*[:\-–]/gi,
  /\bcpf\s*[:\-–]/gi,
  /\bestado\s+civil\s*[:\-–]/gi,
  /\bgrau\s+de\s+instru[çc][ãa]o\s*[:\-–]/gi,
  /\bprofiss[ãa]o\s*[:\-–]/gi,
  /\btipo\s*(?:doc)?\.?\s*[:\-–]/gi,
  /\bcompl(?:emento)?\.?\s*[:\-–]/gi,
  /\btelefone\s*[:\-–]/gi,
  /\bcep\s*[:\-–]/gi,
  /\bponto\s+de\s+refer[êe]ncia\s*[:\-–]/gi,
  // Rótulos de fichas civis (RG, certidões, características físicas)
  /\bcabelos?\s*cor\s*[:\-–]/gi,
  /\bcutis\s*[:\-–]/gi,
  /\bolhos\s*cor\s*[:\-–]/gi,
  /\bnum\.?\s*pis\s*[:\-–]/gi,
  /\bt[íi]tulo\s*[:\-–]/gi,
  /\bzona\s*[:\-–]/gi,
  /\bse[çc][ãa]o\s*[:\-–]/gi,
  /\bnmr[\-\s]?doc\s*[:\-–]/gi,
  /\borg\.?\s*exped\.?\s*doc\s*[:\-–]/gi,
  /\blivro\s*[:\-–]/gi,
  /\bfolha\s*[:\-–]/gi,
  /\bdata\s+documento\s*[:\-–]/gi,
  /^\s*(?:Filia[çc][ãa]o|Documentos|Nacionalidade\s*\/\s*Naturalidade|Informa[çc][õo]es\s+Adicionais|[UÚ]ltimo\s+Endere[çc]o|Informa[çc][õo]es\s+Criminais|Dados\s+Pessoais|Caracter[íi]sticas\s+F[íi]sicas|Endere[çc]o)\s*$/gim,
];

// Referências a procedimento (IPL, Inquérito, Processo, APF, TCO, B.O.).
// Exige um número logo depois pra não pegar qualquer menção solta da
// palavra (ex: "processo de mudança" não tem número, não é procedimento).
const _REGEX_PROCEDIMENTO = /\b(?:ipl|inqu[ée]rito(?:\s+policial)?|processo|apf|tco|boletim\s+de\s+ocorr[êe]ncia)\.?\s*(?:n[ºo°]\.?)?\s*[:\-–]?\s*(\d[\d\.\/\-]{0,20})/gi;

// Artigos de lei / código penal citados no texto (ex: "art. 33 da Lei
// 11.343/06", "arts. 121 e 129 do CP") e menções soltas a leis (ex:
// "Lei 11.340/06"). Exige número logo após "art"/"lei" pra evitar falso
// positivo com palavras comuns.
const _REGEX_ARTIGOS = [
  /\bart(?:igo)?s?\.?\s*\d+[º°]?(?:\s*(?:,|e)\s*\d+[º°]?)*\s*(?:,?\s*(?:c\/?c\.?|combinado\s+com\s+(?:o\s+)?art(?:igo)?s?\.?\s*\d+[º°]?))?\s*(?:,?\s*(?:da|do)\s+(?:lei\s*(?:n[ºo°]\.?)?\s*[\d\.\/\-]+|c[óo]digo\s+penal\b|cp\b))?/gi,
  /\blei\s*(?:n[ºo°]\.?)?\s*[\d\.]+\/\d{2,4}\b/gi,
];

function _extrairComRegexUnica(texto, regex) {
  const encontrados = [];
  let m;
  regex.lastIndex = 0;
  while ((m = regex.exec(texto)) !== null) {
    const valor = m[0].replace(/\s+/g, ' ').trim().replace(/[;,.\-–]+$/, '');
    if (valor && !encontrados.some(function (e) { return e.toLowerCase() === valor.toLowerCase(); })) {
      encontrados.push(valor);
    }
  }
  return encontrados;
}

function extrairProcedimentos(texto) {
  return _extrairComRegexUnica(texto, _REGEX_PROCEDIMENTO);
}

function extrairArtigos(texto) {
  const encontrados = [];
  _REGEX_ARTIGOS.forEach(function (regex) {
    _extrairComRegexUnica(texto, regex).forEach(function (v) {
      if (!encontrados.some(function (e) { return e.toLowerCase() === v.toLowerCase(); })) encontrados.push(v);
    });
  });
  return encontrados;
}

function extrairCamposDoTexto(texto) {
  if (!texto) return {};

  const ocorrencias = [];
  _CAMPOS_AUTOPREENCHER.forEach(function (item) {
    let m;
    item.regex.lastIndex = 0;
    while ((m = item.regex.exec(texto)) !== null) {
      ocorrencias.push({ campo: item.campo, inicio: m.index, fim: m.index + m[0].length });
    }
  });
  _ROTULOS_LIMITE.forEach(function (regex) {
    let m;
    regex.lastIndex = 0;
    while ((m = regex.exec(texto)) !== null) {
      ocorrencias.push({ campo: null, inicio: m.index, fim: m.index + m[0].length });
    }
  });
  ocorrencias.sort(function (a, b) { return a.inicio - b.inicio; });

  // Calcula o valor de cada rótulo (do fim dele até o próximo rótulo).
  ocorrencias.forEach(function (oc, i) {
    const proximaInicio = i + 1 < ocorrencias.length ? ocorrencias[i + 1].inicio : texto.length;
    let valor = texto.slice(oc.fim, proximaInicio);
    valor = valor.replace(/\s+/g, ' ').trim().replace(/^[;,.\-–]+|[;,.\-–]+$/g, '').trim();
    oc.valor = valor;
  });

  // "Número" só vira número de endereço quando o rótulo anterior
  // imediato é "Endereço:"/"Logradouro:" -- caso contrário (ex: depois de
  // "RG:", "Cor dos cabelos:" etc, em fichas civis) é número de
  // documento/outra coisa, e continua servindo só de cerca.
  ocorrencias.forEach(function (oc, i) {
    if (oc.campo !== 'numero' || !oc.valor) return;
    const anterior = ocorrencias[i - 1];
    if (!anterior || anterior.campo !== 'endereco' || !anterior.valor) return;
    const numLimpo = oc.valor.split(/[,;\n]/)[0].trim();
    if (!numLimpo) return;
    const jaTemNumero = new RegExp('(^|\\D)' + numLimpo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(\\D|$)').test(anterior.valor);
    if (!jaTemNumero) {
      anterior.valor = anterior.valor.replace(/[.,;]+$/, '') + ', nº ' + numLimpo;
    }
  });

  // Campos "simples": último valor vence (nome, vulgo, genitora, facção,
  // octopus asint). Município/Bairro/Endereço são tratados à parte, em
  // blocos, logo abaixo.
  const resultado = {};
  ocorrencias.forEach(function (oc) {
    if (oc.campo && oc.campo !== 'numero' && oc.campo !== 'municipio' && oc.campo !== 'bairro' && oc.campo !== 'endereco' && oc.valor) {
      resultado[oc.campo] = oc.valor;
    }
  });

  // ---- Endereço(s) em blocos ----
  // Cada "Endereço:"/"Logradouro:" encontrado abre um bloco; o
  // Município/Bairro que aparecem depois dele (e antes do próximo
  // endereço) pertencem a esse bloco. Isso separa naturalmente, por
  // exemplo, o Município da naturalidade (que vem antes de qualquer
  // "Endereço:") do Município de cada endereço.
  const enderecoOcs = ocorrencias.filter(function (oc) { return oc.campo === 'endereco'; });
  const municipioOcs = ocorrencias.filter(function (oc) { return oc.campo === 'municipio'; });
  const bairroOcs = ocorrencias.filter(function (oc) { return oc.campo === 'bairro'; });

  let blocos = [];
  if (enderecoOcs.length > 0) {
    blocos = enderecoOcs.map(function (end, i) {
      const fimBloco = i + 1 < enderecoOcs.length ? enderecoOcs[i + 1].inicio : Infinity;
      const municipio = municipioOcs.find(function (m) { return m.inicio > end.inicio && m.inicio < fimBloco; });
      const bairro = bairroOcs.find(function (b) { return b.inicio > end.inicio && b.inicio < fimBloco; });
      return { endereco: end.valor || '', municipio: municipio ? municipio.valor : '', bairro: bairro ? bairro.valor : '' };
    });
  } else if (municipioOcs.length || bairroOcs.length) {
    // Sem "Endereço:"/"Logradouro:" explícito no texto -- mantém o
    // comportamento antigo (última ocorrência de cada um).
    blocos = [{
      endereco: '',
      municipio: municipioOcs.length ? municipioOcs[municipioOcs.length - 1].valor : '',
      bairro: bairroOcs.length ? bairroOcs[bairroOcs.length - 1].valor : '',
    }];
  }

  if (blocos.length) {
    // Prioridade pro primeiro endereço encontrado, pra preencher os
    // campos do formulário.
    if (blocos[0].municipio) resultado.municipio = blocos[0].municipio;
    if (blocos[0].bairro) resultado.bairro = blocos[0].bairro;
    if (blocos[0].endereco) resultado.endereco = blocos[0].endereco;

    // Os demais endereços (se houver) vão pra anotações.
    const extras = blocos.slice(1).filter(function (b) { return b.endereco || b.municipio || b.bairro; });
    if (extras.length) {
      resultado.enderecosExtras = extras.map(function (b) {
        const partes = [];
        if (b.endereco) partes.push(b.endereco);
        if (b.bairro) partes.push('Bairro ' + b.bairro);
        if (b.municipio) partes.push(b.municipio);
        return partes.join(' - ');
      });
    }
  }

  // Nome sem rótulo (comum em fichas que começam com o nome sozinho na
  // 1ª linha, sem "Nome:") -- usa a 1ª linha não vazia como último recurso.
  if (!resultado.nome) {
    const primeiraLinha = texto.split('\n').map(function (l) { return l.trim(); }).find(Boolean);
    if (primeiraLinha && primeiraLinha.length <= 80 && !/[:{}]/.test(primeiraLinha)) {
      resultado.nome = primeiraLinha;
    }
  }

  // ---- Procedimento / artigos (busca no texto inteiro) ----
  const procedimentos = extrairProcedimentos(texto);
  const artigos = extrairArtigos(texto);
  if (procedimentos.length || artigos.length) {
    const partes = [];
    if (procedimentos.length) partes.push('Procedimento: ' + procedimentos.join('; '));
    if (artigos.length) partes.push('Artigo(s): ' + artigos.join('; '));
    resultado.procedimentoNota = partes.join('. ');
  }

  return resultado;
}

// Adiciona uma anotação nova reaproveitando o mecanismo REAL do site: abre
// o modal de anotação (o mesmo do botão "+"), preenche Data e Contexto e
// aciona o mesmo "Salvar" que o usuário usaria manualmente. Assim não
// precisamos saber o formato interno de anotacoes.js -- o próprio site
// cuida de gravar e renderizar do jeito certo.
async function adicionarAnotacaoViaModal(contexto) {
  if (!contexto) return;
  if (typeof abrirModalAnotacao !== 'function' || typeof salvarAnotacaoModal !== 'function') return;

  abrirModalAnotacao();
  await sleepAutopreencher(60);

  const campoData = document.getElementById('anot-data');
  const campoContexto = document.getElementById('anot-contexto');
  if (campoData && !campoData.value) campoData.value = new Date().toISOString().slice(0, 10);
  if (campoContexto) campoContexto.value = contexto;

  salvarAnotacaoModal();
  await sleepAutopreencher(60);

  if (typeof fecharModalAnotacao === 'function') fecharModalAnotacao();
}

function abrirModalAutopreencher() {
  document.getElementById('modal-autopreencher').style.display = 'flex';
  document.getElementById('resultado-autopreencher').textContent = '';
  const barra = document.getElementById('barra-autopreencher-wrap');
  if (barra) barra.style.display = 'none';
  document.getElementById('texto-autopreencher').focus();
}

function fecharModalAutopreencher() {
  document.getElementById('modal-autopreencher').style.display = 'none';
}

function _atualizarProgressoAutopreencher(pct, texto) {
  const wrap = document.getElementById('barra-autopreencher-wrap');
  const barra = document.getElementById('barra-autopreencher');
  const label = document.getElementById('barra-autopreencher-label');
  if (!wrap || !barra || !label) return;
  wrap.style.display = 'block';
  barra.style.width = pct + '%';
  label.textContent = texto;
}

// Processa o texto colado com uma barrinha de progresso (só visual --
// a extração é local e rápida; os pequenos atrasos são só pra dar
// feedback de que algo está acontecendo, sem gastar recurso nenhum).
async function verificarTextoAutopreencher() {
  const texto = document.getElementById('texto-autopreencher').value;
  const resultado = document.getElementById('resultado-autopreencher');
  const btns = document.querySelectorAll('#modal-autopreencher button');
  btns.forEach(function (b) { b.disabled = true; });
  resultado.textContent = '';

  _atualizarProgressoAutopreencher(15, 'Lendo texto...');
  await sleepAutopreencher(120);

  _atualizarProgressoAutopreencher(40, 'Identificando campos...');
  await sleepAutopreencher(120);
  const dados = extrairCamposDoTexto(texto);

  _atualizarProgressoAutopreencher(65, 'Conferindo endereços...');
  await sleepAutopreencher(120);

  _atualizarProgressoAutopreencher(85, 'Conferindo procedimento e artigos...');
  await sleepAutopreencher(120);

  const encontrados = Object.keys(dados).filter(function (k) { return k !== 'enderecosExtras' && k !== 'procedimentoNota'; });
  if (!encontrados.length) {
    _atualizarProgressoAutopreencher(100, 'Concluído.');
    btns.forEach(function (b) { b.disabled = false; });
    resultado.textContent = 'Não reconheci nenhum campo nesse texto. Confira se os rótulos estão escritos por extenso (ex: "Nome:", "Bairro:").';
    resultado.style.color = '#a5301f';
    return;
  }

  if (dados.nome) document.getElementById('nome').value = dados.nome;
  if (dados.vulgo) document.getElementById('vulgo').value = dados.vulgo;
  if (dados.genitora) document.getElementById('genitora').value = dados.genitora;
  if (dados.endereco) document.getElementById('octopus').value = dados.endereco;

  if (dados.octopusasint) {
    const alvo = limparTextoJs(dados.octopusasint);
    const selectAsint = document.getElementById('octopusasint');
    if (alvo.startsWith('S')) selectAsint.value = 'SIM';
    else if (alvo.startsWith('N')) selectAsint.value = 'NAO';
  }

  // Facção/Município/Bairro são carregados do servidor -- ajusta o valor
  // "desejado" de cada um (via dataset.atual) e deixa o mecanismo já
  // existente (usado em todo o site) resolver: usa se já existir na
  // lista, ou mantém como extra (igual a um valor antigo que não está
  // mais na lista oficial).
  const faccaoSelect = document.getElementById('faccao');
  const municipioSelect = document.getElementById('municipio');
  const bairroSelect = document.getElementById('bairro');

  if (dados.faccao) faccaoSelect.dataset.atual = limparTextoJs(dados.faccao);
  if (dados.municipio) municipioSelect.dataset.atual = limparTextoJs(dados.municipio);
  if (dados.bairro) bairroSelect.dataset.atual = limparTextoJs(dados.bairro);

  if (dados.faccao || dados.municipio || dados.bairro) {
    await inicializarCombosDinamicos({
      faccaoId: 'faccao',
      municipioId: 'municipio',
      bairroId: 'bairro',
    });
  }

  _atualizarProgressoAutopreencher(95, 'Preenchendo formulário...');
  await sleepAutopreencher(100);

  // Endereços extras e procedimento/artigos viram anotações -- cada um
  // pelo mesmo caminho do botão "+" de Anotações, um de cada vez.
  if (dados.enderecosExtras && dados.enderecosExtras.length) {
    _atualizarProgressoAutopreencher(97, 'Adicionando endereço(s) extra em anotações...');
    await adicionarAnotacaoViaModal('Endereço(s) adicional(is): ' + dados.enderecosExtras.join(' | '));
  }
  if (dados.procedimentoNota) {
    _atualizarProgressoAutopreencher(99, 'Adicionando procedimento/artigos em anotações...');
    await adicionarAnotacaoViaModal(dados.procedimentoNota);
  }

  const nomesCampos = {
    nome: 'Nome', vulgo: 'Vulgo', genitora: 'Genitora', faccao: 'Facção',
    municipio: 'Município', bairro: 'Bairro', endereco: 'Endereço', octopusasint: 'Octopus Asint',
  };
  const avisosExtra = [];
  if (dados.enderecosExtras && dados.enderecosExtras.length) avisosExtra.push(dados.enderecosExtras.length + ' endereço(s) extra em anotações');
  if (dados.procedimentoNota) avisosExtra.push('procedimento/artigos em anotações');

  _atualizarProgressoAutopreencher(100, 'Concluído.');
  resultado.style.color = '#1f8a4c';
  resultado.textContent = '✅ Preenchido: ' + encontrados.map(function (c) { return nomesCampos[c] || c; }).join(', ') +
    (avisosExtra.length ? '. Também adicionei: ' + avisosExtra.join(', ') + '.' : '.');

  btns.forEach(function (b) { b.disabled = false; });
  setTimeout(fecharModalAutopreencher, 1100);
}
