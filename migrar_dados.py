from app import app, db, Pessoa
import sqlite3

# 🧠 Configuração da conexão já está no app.py — vai herdar corretamente

# 🔃 Rodar dentro do contexto do Flask
with app.app_context():
    # Conecta ao banco SQLite antigo
    conexao = sqlite3.connect('banco.db')
    cursor = conexao.cursor()

    # Extrai os registros da tabela 'pessoas'
    cursor.execute("SELECT * FROM pessoas")
    dados = cursor.fetchall()
    conexao.close()

    print(f"🔎 Total de registros encontrados: {len(dados)}")

    # Insere no PostgreSQL cada registro lido
    for item in dados:
        nova_pessoa = Pessoa(
            id=item[0],
            nome=item[1],
            vulgo=item[2],
            foto=item[3],
            genitora=item[4],
            bairro=item[5],
            anotacoes=item[6],
            octopus=item[7],
            municipio=item[8]
        )
        db.session.add(nova_pessoa)

    db.session.commit()
    print("✅ Migração concluída com sucesso!")
