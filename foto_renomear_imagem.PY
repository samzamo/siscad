import pandas as pd
import os

# 🗂️ Caminhos personalizados
CAMINHO_EXCEL = r'C:\Users\SAM\Desktop\FOTOS.xlsx'
PASTA_IMAGENS = r'C:\Users\SAM\Desktop\IMAGEM'

# 🔍 Leitura do Excel
try:
    df = pd.read_excel(CAMINHO_EXCEL)
except Exception as e:
    print(f'❌ Erro ao ler o Excel:\n{e}')
    exit()

# 🔡 Normaliza os nomes das colunas
df.columns = df.columns.str.strip().str.lower()

# ✅ Verifica existência da coluna 'foto'
if 'foto' not in df.columns:
    print('❌ Coluna "foto" não encontrada na planilha.')
    print(f'🔍 Colunas detectadas: {df.columns.tolist()}')
    exit()

print('\n🚀 Iniciando renomeação das imagens...\n')

# 📄 Logs
renomeados = []
nao_encontrados = []
conflitos = []
ignorados = []

# 🔁 Renomeação com tratamento de nulos e proteção contra sobrescrita
for nome_desejado in df['foto']:
    # 🧠 Ignora valores vazios ou inválidos
    if pd.isna(nome_desejado):
        ignorados.append('Valor vazio ou inválido')
        print('⚠️ Valor vazio na coluna "foto" — ignorado')
        continue

    # Converte para string com segurança
    nome_desejado = str(nome_desejado).strip()
    nome_base = os.path.splitext(nome_desejado)[0]
    extensao = os.path.splitext(nome_desejado)[1]

    nome_antigo = os.path.join(PASTA_IMAGENS, f"{nome_base}_FOTO{extensao}")
    nome_novo = os.path.join(PASTA_IMAGENS, nome_desejado)

    if os.path.exists(nome_antigo):
        if not os.path.exists(nome_novo):
            os.rename(nome_antigo, nome_novo)
            renomeados.append(nome_desejado)
            print(f'✅ {os.path.basename(nome_antigo)} → {os.path.basename(nome_novo)}')
        else:
            conflitos.append(nome_desejado)
            print(f'⚠️ Arquivo destino já existe: {os.path.basename(nome_novo)} — ignorado')
    else:
        nao_encontrados.append(f"{nome_base}_FOTO{extensao}")
        print(f'⚠️ Arquivo não encontrado: {os.path.basename(nome_antigo)}')

# 🏁 Relatório final
print('\n📋 Relatório:')
print(f'✅ Renomeados: {len(renomeados)}')
print(f'⚠️ Não encontrados: {len(nao_encontrados)}')
print(f'🚫 Conflitos (já existiam): {len(conflitos)}')
print(f'🕳️ Ignorados por valor nulo/inválido: {len(ignorados)}')
s
