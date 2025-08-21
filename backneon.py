from sqlalchemy import create_engine
from sqlalchemy import text

# 🔐 Conexão com o banco Neon
user = "neondb_owner"
password = "npg_otRGwQ76mkhz"
host = "ep-super-mode-aflk10pk-pooler.c-2.us-west-2.aws.neon.tech"
db = "neondb"

url = f"postgresql://{user}:{password}@{host}/{db}?sslmode=require"
engine = create_engine(url)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name;
    """))
    tabelas = result.fetchall()
    for schema, table in tabelas:
        print(f"📁 {schema}.{table}")