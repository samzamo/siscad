import psycopg2
from openpyxl import Workbook

# 🔗 Conexão com banco PostgreSQL no Neon
DATABASE_URL = (
    'postgresql://neondb_owner:npg_fCVgz9kF0RBD@ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech/neondb'
    '?sslmode=require&connect_timeout=20'
)

# 🔌 Conectar ao banco
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 🔍 Buscar dados da tabela pessoa
cur.execute("SELECT id, nome, foto FROM pessoa")
pessoas = cur.fetchall()

# 📄 Criar planilha Excel
wb = Workbook()
ws = wb.active
ws.title = "Pessoas"

# 📝 Cabeçalhos
ws.append(["ID", "Nome", "Foto"])

# ➕ Adicionar dados
for id_, nome, foto in pessoas:
    ws.append([id_, nome, foto])

# 💾 Salvar arquivo
wb.save("pessoas.xlsx")

# ✅ Finalizar conexão
cur.close()
conn.close()

print("📄 Planilha 'pessoas.xlsx' gerada com sucesso!")
