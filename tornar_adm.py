import sqlite3

def tornar_samara_admin():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    # Altera o tipo para 'adm' no usuário SAMARA
    cursor.execute("UPDATE usuarios SET tipo = 'adm' WHERE username = 'SAMARA'")
    conn.commit()
    conn.close()
    
    print("✅ Usuário 'SAMARA' agora é administrador novamente!")

if __name__ == '__main__':
    tornar_samara_admin()
