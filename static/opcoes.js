// static/opcoes.js
// Comboboxes dinâmicos de Facção / Município / Bairro (SISCAD).
// Usado tanto na tela de Cadastro quanto no modal de Editar (pesquisar_alvo).
//
// Cada opção vem do servidor como { valor, id }. Itens PADRÃO do sistema
// (CV, PCC, FORTALEZA, a lista de bairros já existente) vêm com id = null
// e não podem ser editados/excluídos por aqui -- só os itens adicionados
// pelo usuário (via botão "+") têm id e ficam editáveis/excluíveis.

function normalizarOpcao(v) {
  return (v || "").toString()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .trim().toUpperCase();
}

async function buscarOpcoes(tipo, municipio) {
  let url = `/opcoes/${tipo}`;
  if (tipo === "bairro") {
    if (!municipio) return [];
    url += `?municipio=${encodeURIComponent(municipio)}`;
  }
  try {
    const resp = await fetch(url);
    if (!resp.ok) return [];
    return await resp.json(); // [{ valor, id }, ...]
  } catch (e) {
    console.error("Erro ao buscar opções:", e);
    return [];
  }
}

async function enviarJson(url, method, corpo) {
  try {
    const resp = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    let dados = {};
    try {
      dados = await resp.json();
    } catch (e) {
      dados = { erro: `Erro inesperado do servidor (status ${resp.status}). Veja o terminal do app.py.` };
    }
    return { ok: resp.ok, dados };
  } catch (e) {
    return { ok: false, dados: { erro: "Erro de conexão (verifique se o servidor está rodando)." } };
  }
}

// Preenche um <select> a partir da lista [{valor, id}], mantendo o valor
// atual selecionado (mesmo que ele não esteja na lista oficial -- nesse
// caso, adiciona como item extra sem id, marcado com o `sufixoExtra`, pra
// não perder dado já cadastrado).
function preencherSelect(select, lista, valorParaManter, sufixoExtra) {
  if (!select) return;
  const placeholder = select.querySelector('option[value=""]');
  select.innerHTML = "";
  if (placeholder) select.appendChild(placeholder);

  lista.forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.valor;
    opt.textContent = item.valor;
    if (item.id !== null && item.id !== undefined) {
      opt.dataset.id = item.id;
    }
    select.appendChild(opt);
  });

  if (valorParaManter) {
    const bateu = lista.some(item => normalizarOpcao(item.valor) === normalizarOpcao(valorParaManter));
    if (bateu) {
      const opt = [...select.options].find(
        o => normalizarOpcao(o.value) === normalizarOpcao(valorParaManter)
      );
      if (opt) select.value = opt.value;
    } else {
      const extra = document.createElement("option");
      extra.value = valorParaManter;
      extra.textContent = valorParaManter + (sufixoExtra || "");
      select.appendChild(extra);
      select.value = valorParaManter;
    }
  }
}

// Carrega Facção, Município e Bairro a partir do servidor, preservando o
// valor já selecionado/cadastrado. Chame no DOMContentLoaded (ou ao abrir
// o modal) passando os ids dos <select> de cada campo presentes na página.
async function inicializarCombosDinamicos(config) {
  const sufixo = config.sufixoExtra || "";

  if (config.faccaoId) {
    const faccaoSelect = document.getElementById(config.faccaoId);
    const atual = faccaoSelect ? (faccaoSelect.value || faccaoSelect.dataset.atual || "") : "";
    const lista = await buscarOpcoes("faccao");
    preencherSelect(faccaoSelect, lista, atual, sufixo);
  }

  if (config.municipioId) {
    const municipioSelect = document.getElementById(config.municipioId);
    const atualMunicipio = municipioSelect
      ? (municipioSelect.value || municipioSelect.dataset.atual || "")
      : "";
    const listaMunicipios = await buscarOpcoes("municipio");
    preencherSelect(municipioSelect, listaMunicipios, atualMunicipio, sufixo);

    if (config.bairroId) {
      const bairroSelect = document.getElementById(config.bairroId);
      const atualBairro = bairroSelect
        ? (bairroSelect.value || bairroSelect.dataset.atual || "")
        : "";
      const municipioFinal = municipioSelect ? municipioSelect.value : "";
      const listaBairros = await buscarOpcoes("bairro", municipioFinal);
      preencherSelect(bairroSelect, listaBairros, atualBairro, sufixo);

      // Troca de município -> recarrega os bairros (sem manter o antigo,
      // já que ele pertence ao município anterior).
      municipioSelect.addEventListener("change", async function () {
        const lista = await buscarOpcoes("bairro", this.value);
        preencherSelect(bairroSelect, lista, null);
      });
    }
  }
}

// Botão "+": pede o novo valor, confere duplicidade (local e no servidor)
// e adiciona no <select> correspondente.
//   tipo              -> 'faccao' | 'municipio' | 'bairro'
//   selectId          -> id do <select> a atualizar
//   municipioSelectId -> (só para tipo 'bairro') id do <select> de município
function abrirNovaOpcao(tipo, selectId, municipioSelectId) {
  let municipio = "";
  if (tipo === "bairro") {
    const municipioSelect = document.getElementById(municipioSelectId || "municipio");
    municipio = municipioSelect ? municipioSelect.value : "";
    if (!municipio) {
      alert("Selecione o município antes de adicionar um bairro.");
      return;
    }
  }

  const rotulo = tipo === "faccao" ? "Nova facção:"
    : tipo === "municipio" ? "Novo município:"
    : "Novo bairro:";

  const valor = prompt(rotulo);
  if (valor === null) return; // cancelou
  const valorLimpo = valor.trim();
  if (!valorLimpo) return;

  const select = document.getElementById(selectId);
  const jaExisteLocal = select && [...select.options].some(
    o => o.value && normalizarOpcao(o.value) === normalizarOpcao(valorLimpo)
  );
  if (jaExisteLocal) {
    alert(`"${valorLimpo}" já está na lista.`);
    return;
  }

  const corpo = { valor: valorLimpo };
  if (tipo === "bairro") corpo.municipio = municipio;

  enviarJson(`/opcoes/${tipo}`, "POST", corpo).then(({ ok, dados }) => {
    if (!ok) {
      alert(dados.erro || "Não foi possível adicionar essa opção.");
      return;
    }
    const opt = document.createElement("option");
    opt.value = dados.valor;
    opt.textContent = dados.valor;
    if (dados.id) opt.dataset.id = dados.id;
    select.appendChild(opt);
    select.value = dados.valor;
    select.dispatchEvent(new Event("change"));
  });
}

// Botão "✏️": edita o item SELECIONADO no momento (só funciona se ele foi
// adicionado pelo usuário -- itens padrão não têm id e não são editáveis).
function editarOpcaoSelecionada(tipo, selectId) {
  const select = document.getElementById(selectId);
  const opcaoSelecionada = select ? select.selectedOptions[0] : null;
  if (!opcaoSelecionada || !opcaoSelecionada.value) {
    alert("Selecione um item na lista para editar.");
    return;
  }
  const id = opcaoSelecionada.dataset.id;
  if (!id) {
    alert("Esse item é padrão do sistema e não pode ser editado por aqui.");
    return;
  }

  const novoValor = prompt("Editar valor:", opcaoSelecionada.value);
  if (novoValor === null) return;
  const valorLimpo = novoValor.trim();
  if (!valorLimpo) return;

  const jaExisteLocal = [...select.options].some(
    o => o !== opcaoSelecionada && o.value && normalizarOpcao(o.value) === normalizarOpcao(valorLimpo)
  );
  if (jaExisteLocal) {
    alert(`"${valorLimpo}" já está na lista.`);
    return;
  }

  enviarJson(`/opcoes/${tipo}/${id}`, "PUT", { valor: valorLimpo }).then(({ ok, dados }) => {
    if (!ok) {
      alert(dados.erro || "Não foi possível editar essa opção.");
      return;
    }
    opcaoSelecionada.value = dados.valor;
    opcaoSelecionada.textContent = dados.valor;
    select.value = dados.valor;
    select.dispatchEvent(new Event("change"));
  });
}

// Botão "🗑️": exclui o item SELECIONADO no momento da lista (só itens
// adicionados pelo usuário). Não afeta cadastros que já usam esse valor --
// eles continuam com o dado normalmente, só some da lista de opções.
function excluirOpcaoSelecionada(tipo, selectId) {
  const select = document.getElementById(selectId);
  const opcaoSelecionada = select ? select.selectedOptions[0] : null;
  if (!opcaoSelecionada || !opcaoSelecionada.value) {
    alert("Selecione um item na lista para excluir.");
    return;
  }
  const id = opcaoSelecionada.dataset.id;
  if (!id) {
    alert("Esse item é padrão do sistema e não pode ser excluído por aqui.");
    return;
  }

  const confirmado = confirm(
    `Excluir "${opcaoSelecionada.value}" da lista?\n\nCadastros que já usam esse valor não serão alterados -- só sai da lista de opções para novos cadastros/edições.`
  );
  if (!confirmado) return;

  enviarJson(`/opcoes/${tipo}/${id}`, "DELETE").then(({ ok, dados }) => {
    if (!ok) {
      alert(dados.erro || "Não foi possível excluir essa opção.");
      return;
    }
    opcaoSelecionada.remove();
    select.value = "";
    select.dispatchEvent(new Event("change"));
  });
}
