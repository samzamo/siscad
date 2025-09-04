import cloudinary
import cloudinary.api
import psycopg2
from openpyxl import Workbook

# 🔗 Configuração Cloudinary
cloudinary.config(
    cloud_name='dygav0zig',
    api_key='356954525268762',
    api_secret='9KXP41yJPdXDj78aK_S6CKl_9-I'
)

# ☁️ Buscar arquivos reais da pasta IMAGEM no Cloudinary
print("🔍 Buscando arquivos reais na pasta IMAGEM do Cloudinary...")
recursos = cloudinary.api.resources(type="upload", prefix="IMAGEM/", max_results=1000)

# 🧠 Criar dicionário com ID → extensão
cloud_extensoes = {}
for recurso in recursos['resources']:
    public_id = recurso['public_id'].strip()
    partes = public_id.split('/')
    if len(partes) == 2 and partes[0].upper() == "IMAGEM":
        id_str = ''.join(filter(str.isdigit, partes[1]))
        if id_str.isdigit():
            id_int = int(id_str)
            extensao = recurso['format'].lower()
            cloud_extensoes[id_int] = extensao

# 🔌 Conexão com Neon
conn = psycopg2.connect(
    host="ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech",
    database="neondb",
    user="neondb_owner",
    password="npg_fCVgz9kF0RBD",
    sslmode="require",
    connect_timeout=20
)
cur = conn.cursor()
cur.execute("SELECT id, nome FROM pessoa")
pessoas = cur.fetchall()
conn.close()

# 📊 Criar planilhas
wb_ok = Workbook()
ws_ok = wb_ok.active
ws_ok.title = "Atualizados"
ws_ok.append(["ID", "Nome", "Extensão"])

wb_fail = Workbook()
ws_fail = wb_fail.active
ws_fail.title = "Não Atualizados"
ws_fail.append(["ID", "Nome", "Extensão"])

# 🔄 Separar os que têm imagem e os que não têm
for id_, nome in pessoas:
    extensao = cloud_extensoes.get(id_)
    if extensao:
        ws_ok.append([id_, nome, extensao])
    else:
        ws_fail.append([id_, nome, ""])

# 💾 Salvar planilhas
wb_ok.save("atualizados.xlsx")
wb_fail.save("nao_atualizados.xlsx")

print("✅ Planilhas geradas com sucesso:")
print("📁 atualizados.xlsx → com os que têm imagem e extensão real")
print("📁 nao_atualizados.xlsx → com os que não têm imagem ou extensão ausente")
