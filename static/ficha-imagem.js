// static/ficha-imagem.js
// Gera a "ficha" de um alvo em duas formas prontas pra WhatsApp:
//   - texto formatado (FichaImagem.montarTexto)
//   - imagem PNG com foto + dados + anotações (FichaImagem.gerarBlobPng)
// Usado em exportar_alvo.html e no botão "Copiar imagem" da pesquisa.
// Puro client-side -- não gasta nada do servidor.

const FichaImagem = (function () {
  const FONTE = '-apple-system, "Segoe UI", Roboto, Arial, sans-serif';

  function carregarImagemComTimeout(url, timeoutMs) {
    return new Promise(function (resolve) {
      if (!url) { resolve(null); return; }
      const img = new Image();
      let resolvido = false;
      const finalizar = function (valor) { if (!resolvido) { resolvido = true; resolve(valor); } };
      img.crossOrigin = 'anonymous';
      img.onload = function () { finalizar(img); };
      img.onerror = function () { finalizar(null); };
      img.src = url;
      setTimeout(function () { finalizar(null); }, timeoutMs);
    });
  }

  function quebrarTexto(ctx, texto, maxWidth) {
    const paragrafos = (texto || '').split('\n');
    const linhas = [];
    paragrafos.forEach(function (p) {
      if (!p.trim()) { linhas.push(''); return; }
      const palavras = p.split(' ');
      let atual = '';
      palavras.forEach(function (palavra) {
        const teste = atual ? atual + ' ' + palavra : palavra;
        if (ctx.measureText(teste).width > maxWidth && atual) {
          linhas.push(atual);
          atual = palavra;
        } else {
          atual = teste;
        }
      });
      if (atual) linhas.push(atual);
    });
    return linhas;
  }

  function retanguloArredondado(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // dados = { id, nome, vulgo, genitora, faccao, municipio, bairro,
  //           endereco, octopusasint, anotacoes, foto, geradoEm }
  async function gerarCanvas(dados, incluirFoto) {
    const CORES = {
      navy: '#16324a', bg: '#f7f9fb', border: '#dbe2ea', texto: '#2b2f36',
      mutado: '#6b7280', sucesso: '#1f8a4c', perigo: '#a5301f',
      sucessoBg: '#e4f5ea', perigoBg: '#fdecea',
    };
    const W = 1000, PAD = 46, FOTO_W = 260, FOTO_H = 330;
    const colX = PAD + FOTO_W + 34;
    const colW = W - colX - PAD;

    const medidor = document.createElement('canvas').getContext('2d');
    medidor.font = '15px ' + FONTE;
    const linhasAnot = quebrarTexto(medidor, dados.anotacoes || 'Sem anotações registradas.', W - PAD * 2 - 32);

    const ALT_HEADER = 100;
    const ALT_TOPO = FOTO_H + 30;
    const ALT_ANOT_TITULO = 46;
    const ALT_LINHA_ANOT = 21;
    const ALT_ANOT_BOX = 28 + linhasAnot.length * ALT_LINHA_ANOT;
    const H = ALT_HEADER + PAD + ALT_TOPO + ALT_ANOT_TITULO + ALT_ANOT_BOX + 60 + PAD;

    const img = incluirFoto ? await carregarImagemComTimeout(dados.foto, 3000) : null;

    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = CORES.navy;
    ctx.fillRect(0, 0, W, ALT_HEADER);
    ctx.fillStyle = '#9db3c4';
    ctx.font = '600 12px ' + FONTE;
    ctx.textAlign = 'center';
    ctx.fillText('SISCAD · RELATÓRIO DE ALVO', W / 2, 38);
    ctx.fillStyle = '#ffffff';
    ctx.font = '600 24px ' + FONTE;
    ctx.fillText('Ficha Cadastral', W / 2, 68);
    ctx.textAlign = 'left';

    const y = ALT_HEADER + PAD;

    retanguloArredondado(ctx, PAD, y, FOTO_W, FOTO_H, 10);
    ctx.save();
    ctx.clip();
    if (img) {
      const escala = Math.max(FOTO_W / img.width, FOTO_H / img.height);
      const iw = img.width * escala, ih = img.height * escala;
      ctx.drawImage(img, PAD + (FOTO_W - iw) / 2, y + (FOTO_H - ih) / 2, iw, ih);
    } else {
      ctx.fillStyle = CORES.bg;
      ctx.fillRect(PAD, y, FOTO_W, FOTO_H);
      ctx.fillStyle = CORES.mutado;
      ctx.font = '13px ' + FONTE;
      ctx.textAlign = 'center';
      ctx.fillText('Sem foto', PAD + FOTO_W / 2, y + FOTO_H / 2);
      ctx.textAlign = 'left';
    }
    ctx.restore();
    ctx.strokeStyle = CORES.border;
    ctx.lineWidth = 1;
    retanguloArredondado(ctx, PAD, y, FOTO_W, FOTO_H, 10);
    ctx.stroke();

    let dy = y + 6;
    ctx.fillStyle = CORES.navy;
    ctx.font = '700 24px ' + FONTE;
    ctx.fillText(dados.nome, colX, dy + 24);
    dy += 34;
    if (dados.vulgo) {
      ctx.fillStyle = CORES.mutado;
      ctx.font = '16px ' + FONTE;
      ctx.fillText(dados.vulgo, colX, dy + 16);
      dy += 30;
    }
    dy += 10;

    const camposDados = [
      ['Genitora', dados.genitora],
      ['Facção', dados.faccao],
      ['Município', dados.municipio],
      ['Bairro', dados.bairro],
      ['Endereço', dados.endereco],
    ].filter(function (par) { return par[1]; });

    ctx.font = '14px ' + FONTE;
    camposDados.forEach(function (par) {
      ctx.strokeStyle = CORES.border;
      ctx.beginPath();
      ctx.moveTo(colX, dy + 26);
      ctx.lineTo(colX + colW, dy + 26);
      ctx.stroke();
      ctx.fillStyle = CORES.mutado;
      ctx.font = '600 13px ' + FONTE;
      ctx.fillText(par[0], colX, dy + 18);
      ctx.fillStyle = CORES.texto;
      ctx.font = '13px ' + FONTE;
      ctx.textAlign = 'right';
      ctx.fillText(String(par[1]), colX + colW, dy + 18);
      ctx.textAlign = 'left';
      dy += 32;
    });

    if (dados.octopusasint) {
      const sim = dados.octopusasint === 'SIM';
      ctx.fillStyle = CORES.mutado;
      ctx.font = '600 13px ' + FONTE;
      ctx.fillText('Octopus Asint', colX, dy + 18);
      const textoBadge = sim ? 'SIM' : dados.octopusasint;
      ctx.font = '600 12px ' + FONTE;
      const largBadge = ctx.measureText(textoBadge).width + 20;
      const xBadge = colX + colW - largBadge;
      ctx.fillStyle = sim ? CORES.sucessoBg : CORES.perigoBg;
      retanguloArredondado(ctx, xBadge, dy, largBadge, 22, 11);
      ctx.fill();
      ctx.fillStyle = sim ? CORES.sucesso : CORES.perigo;
      ctx.textAlign = 'center';
      ctx.fillText(textoBadge, xBadge + largBadge / 2, dy + 15);
      ctx.textAlign = 'left';
    }

    let yAnot = ALT_HEADER + PAD + ALT_TOPO;
    ctx.fillStyle = CORES.mutado;
    ctx.font = '600 13px ' + FONTE;
    ctx.fillText('ANOTAÇÕES', PAD, yAnot + 14);
    yAnot += ALT_ANOT_TITULO;

    ctx.fillStyle = CORES.bg;
    retanguloArredondado(ctx, PAD, yAnot, W - PAD * 2, ALT_ANOT_BOX, 8);
    ctx.fill();
    ctx.strokeStyle = CORES.border;
    retanguloArredondado(ctx, PAD, yAnot, W - PAD * 2, ALT_ANOT_BOX, 8);
    ctx.stroke();

    ctx.fillStyle = CORES.texto;
    ctx.font = '15px ' + FONTE;
    let ly = yAnot + 30;
    linhasAnot.forEach(function (linha) {
      ctx.fillText(linha, PAD + 16, ly);
      ly += ALT_LINHA_ANOT;
    });

    ctx.fillStyle = CORES.mutado;
    ctx.font = '11px ' + FONTE;
    ctx.textAlign = 'center';
    ctx.fillText(
      'Relatório gerado em ' + dados.geradoEm + ' · ID do cadastro: ' + dados.id,
      W / 2, yAnot + ALT_ANOT_BOX + 30
    );
    ctx.textAlign = 'left';

    return canvas;
  }

  function canvasParaBlobPng(canvas) {
    return new Promise(function (resolve, reject) {
      try {
        canvas.toBlob(function (blob) {
          blob ? resolve(blob) : reject(new Error('canvas vazio'));
        }, 'image/png');
      } catch (e) { reject(e); }
    });
  }

  async function gerarBlobPng(dados) {
    try {
      const canvas = await gerarCanvas(dados, true);
      return await canvasParaBlobPng(canvas);
    } catch (e) {
      // Foto "sujou" o canvas (sem CORS) ou outro erro -- gera de novo
      // sem ela, pra garantir que os dados e anotações sempre saiam.
      const canvas = await gerarCanvas(dados, false);
      return await canvasParaBlobPng(canvas);
    }
  }

  // Gera o blob só da FOTO (sem nome, sem dados, sem moldura) -- usado no
  // botão "Copiar imagem", já que o texto (com todos os dados) já sai
  // separado pelo "Copiar texto".
  async function gerarBlobFoto(url) {
    const img = await carregarImagemComTimeout(url, 4000);
    if (!img) return null;
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return await canvasParaBlobPng(canvas);
  }

  function montarTexto(dados) {
    const linhas = ['👤 *' + dados.nome + '*'];
    linhas.push('');
    if (dados.vulgo) linhas.push('🏷️ Vulgo: ' + dados.vulgo);
    linhas.push('');
    if (dados.genitora) linhas.push('👩 Genitora: ' + dados.genitora);
    linhas.push('');
    if (dados.faccao) linhas.push('🚩 Facção: ' + dados.faccao);
    linhas.push('');
    if (dados.municipio) linhas.push('🏙️ Município: ' + dados.municipio);
    if (dados.bairro) linhas.push('🏘️ Bairro: ' + dados.bairro);
    if (dados.endereco) linhas.push('📍 Endereço: ' + dados.endereco);
    if (dados.octopusasint) linhas.push('🐙 Sistema: ' + dados.octopusasint);
    linhas.push('');
    linhas.push('📝 Anotações:');
    linhas.push(dados.anotacoes && dados.anotacoes.trim() ? dados.anotacoes : 'Sem anotações registradas.');
    linhas.push('');
    linhas.push('🕒 Ficha gerada pelo SISCAD em ' + dados.geradoEm);
    return linhas.join('\n');
  }

  function nomeArquivo(nome, prefixo) {
    const limpo = (nome || 'alvo')
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    return (prefixo || 'ficha') + '_' + (limpo || 'alvo') + '.png';
  }

  function baixarBlob(blob, nome) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nome;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }

  return { gerarBlobPng: gerarBlobPng, gerarBlobFoto: gerarBlobFoto, montarTexto: montarTexto, nomeArquivo: nomeArquivo, baixarBlob: baixarBlob };
})();
