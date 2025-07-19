import csv
import sqlite3
import os
import unicodedata

def limpar_texto(texto):
    if not texto:
        return ''
    texto = texto.upper().strip()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

# 📂 Caminhos
CAMINHO_CSV = r'C:/Users/SAM/Desktop/meu_site/planilha/nomes.csv'  # ajuste conforme necessário
BANCO_DADOS = 'banco.db'

# ✅ Verifica se o CSV existe
if not os.path.exists(CAMINHO_CSV):
    print(f"⚠️ Arquivo CSV não encontrado: {CAMINHO_CSV}")
    exit()

# 🔗 Conecta ao banco
conn = sqlite3.connect(BANCO_DADOS)
cursor = conn.cursor()

# 📋 Garante que as colunas existem
novos_campos = {
    'municipio': 'TEXT',
    'bairro': 'TEXT',
    'anotacoes': 'TEXT',
    'octopus': 'TEXT'
}
cursor.execute("PRAGMA table_info(pessoas)")
colunas_existentes = [c[1] for c in cursor.fetchall()]
for campo, tipo in novos_campos.items():
    if campo not in colunas_existentes:
        cursor.execute(f"ALTER TABLE pessoas ADD COLUMN {campo} {tipo}")
        print(f"✅ Coluna '{campo}' adicionada.")
    else:
        print(f"ℹ️ Coluna '{campo}' já existe.")

# 📥 Processa o CSV
with open(CAMINHO_CSV, newline='', encoding='utf-8') as arquivo:
    leitor = csv.DictReader(arquivo, delimiter=';')
    print(f"\n🔍 Cabeçalhos detectados: {leitor.fieldnames}\n")

    for linha in leitor:
        try:
            nome = limpar_texto(linha.get('NOME') or linha.get('\ufeffNOME'))
            apelido = limpar_texto(linha.get('APELIDO'))
            municipio = limpar_texto(linha.get('MUNICIPIO'))
            bairro = limpar_texto(linha.get('BAIRRO'))
            anotacoes = linha.get('ANOTACOES', '').strip()
            octopus = limpar_texto(linha.get('OCTOPUS'))

            # 🔍 Localiza por nome
            cursor.execute("SELECT id FROM pessoas WHERE nome = ?", (nome,))
            resultado = cursor.fetchone()

            if resultado:
                pessoa_id = resultado[0]
                cursor.execute('''
                    UPDATE pessoas SET 
                        municipio = ?, bairro = ?, anotacoes = ?, octopus = ?
                    WHERE id = ?
                ''', (municipio, bairro, anotacoes, octopus, pessoa_id))
                print(f"🔄 Atualizado: {nome} ({apelido})")
            else:
                print(f"⚠️ Registro não encontrado: {nome} / {apelido}")

        except Exception as e:
            print(f"❌ Erro ao processar linha: {linha}")
            print(f"🔧 Detalhe: {e}")

# 🧾 Finaliza
conn.commit()
conn.close()
print("\n🎉 Atualização concluída com sucesso!")
