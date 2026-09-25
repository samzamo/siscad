# criar_tabela_opcoes.py
#
# Cria a tabela nova "opcao_cadastro" no banco (usada pelo botão "+" dos
# comboboxes de Facção/Município/Bairro). Roda uma vez só.
#
# NÃO altera nem apaga nenhuma tabela existente -- db.create_all() só cria
# o que ainda não existe.
#
# Como usar:
#   python criar_tabela_opcoes.py

from app import app, db

with app.app_context():
    db.create_all()
    print("✅ Tabela 'opcao_cadastro' pronta (criada agora ou já existia).")
