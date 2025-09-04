import psycopg2

conn = psycopg2.connect(
    host="ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech",
    database="neondb",
    user="neondb_owner",
    password="npg_fCVgz9kF0RBD",
    sslmode="require"
)
cur = conn.cursor()
cur.execute("UPDATE pessoa SET foto = foto_backup;")
conn.commit()
conn.close()

print("✔️ Coluna 'foto' atualizada com os valores de 'foto_backup'.")