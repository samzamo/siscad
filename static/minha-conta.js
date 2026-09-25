document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('btnMinhaConta');
  var overlay = document.getElementById('modalConta');
  if (!btn || !overlay) return;

  var fechar = document.getElementById('fecharModalConta');
  var form = document.getElementById('formConta');
  var msg = document.getElementById('modalContaMsg');
  var inputEmail = document.getElementById('inputEmail');

  function setMsg(texto, tipo) {
    msg.textContent = texto || '';
    msg.className = 'siscad-modal-msg' + (tipo ? ' ' + tipo : '');
  }

  function abrirModal() {
    setMsg('');
    form.reset();
    overlay.classList.add('aberto');
    fetch('/api/minha_conta')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) inputEmail.value = d.email || '';
      })
      .catch(function () {});
  }

  function fecharModal() {
    overlay.classList.remove('aberto');
  }

  btn.addEventListener('click', abrirModal);
  fechar.addEventListener('click', fecharModal);
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) fecharModal();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay.classList.contains('aberto')) fecharModal();
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var nova = form.nova_senha.value;
    var conf = form.confirmar_senha.value;

    if (nova || conf) {
      if (nova !== conf) {
        setMsg('As senhas novas não coincidem.', 'erro');
        return;
      }
      if (nova.length < 6) {
        setMsg('A nova senha deve ter pelo menos 6 caracteres.', 'erro');
        return;
      }
    }

    var dados = new FormData(form);
    var submitBtn = form.querySelector('.siscad-modal-submit');
    submitBtn.disabled = true;
    setMsg('Salvando...', '');

    fetch('/conta/atualizar', { method: 'POST', body: dados })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        submitBtn.disabled = false;
        if (d.ok) {
          setMsg('Dados atualizados com sucesso!', 'sucesso');
          form.senha_atual.value = '';
          form.nova_senha.value = '';
          form.confirmar_senha.value = '';
          setTimeout(fecharModal, 1200);
        } else {
          setMsg(d.erro || 'Erro ao atualizar.', 'erro');
        }
      })
      .catch(function () {
        submitBtn.disabled = false;
        setMsg('Erro de conexão. Tente novamente.', 'erro');
      });
  });
});
