import sqlite3

conn = sqlite3.connect('banco.db')
cursor = conn.cursor()

# Verifica se o usuário SAMARA existe
cursor.execute('SELECT id, username, ativo FROM usuarios WHERE username = "SAMARA"')
usuario = cursor.fetchone()

if usuario:
    cursor.execute('UPDATE usuarios SET ativo = 1 WHERE username = "SAMARA"')
    conn.commit()
    print(f"✅ Usuária {usuario[1]} ativada com sucesso!")
else:
    print("⚠️ Usuário 'SAMARA' não encontrado. Verifique se está cadastrado.")

conn.close()
