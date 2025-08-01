import psycopg2

try:
    conn = psycopg2.connect(
        dbname="samara_db",
        user="samara_user",
        password="sua_senha",
        host="ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech",
        port="5432",
        connect_timeout=10
    )
    print("✅ Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print("❌ Erro na conexão:")
    print(e)