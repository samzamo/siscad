import sqlite3

def atualizar_tabela_usuarios():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'normal'")
        conn.commit()
        print("✅ Coluna 'tipo' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("ℹ️ A coluna 'tipo' já existe. Nenhuma alteração feita.")
    finally:
        conn.close()

atualizar_tabela_usuarios()
