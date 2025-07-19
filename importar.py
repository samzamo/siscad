import csv
import sqlite3
import os
import unicodedata

# 🔤 Função para limpar texto (maiúsculo + sem acento)
def limpar_texto(texto):
    texto = texto.upper().strip()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

# 📂 Configurações
CAMINHO_CSV = 'planilha/nomes.csv'      # ajuste se necessário
PASTA_IMAGENS = 'static/IMAGEM'
BANCO_DADOS = 'banco.db'

# 🔗 Conectar ao banco
conn = sqlite3.connect(BANCO_DADOS)
cursor = conn.cursor()

# 📥 Ler a planilha com separador por ponto e vírgula
with open(CAMINHO_CSV, newline='', encoding='utf-8') as arquivo:
    leitor = csv.DictReader(arquivo, delimiter=';')  # ← ajuste importante!
    print("🔍 Cabeçalhos detectados:", leitor.fieldnames)

    for linha in leitor:
        try:
            # Captura campos mesmo se vier com caractere invisível
            nome = limpar_texto(linha.get('NOME') or linha.get('\ufeffNOME'))
            apelido = limpar_texto(linha.get('APELIDO') or '')
            genitora = limpar_texto(linha.get('GENITORA') or '')
            foto = linha.get('FOTO', '').strip()

            # Verifica existência da imagem
            caminho_foto = os.path.join(PASTA_IMAGENS, foto)
            if not os.path.exists(caminho_foto):
                print(f"⚠️ Imagem não encontrada: {foto}")
                foto = ''

            # Inserir no banco (id é autogerado)
            cursor.execute('''
                INSERT INTO pessoas (nome, vulgo, foto, genitora)
                VALUES (?, ?, ?, ?)
            ''', (nome, apelido, foto, genitora))

            print(f"✅ Inserido: {nome} ({apelido})")

        except Exception as e:
            print(f"❌ Erro ao processar linha: {linha}")
            print(f"🔧 Detalhe: {e}")

# 🧾 Finaliza
conn.commit()
conn.close()
print("\n🎉 Importação concluída com sucesso!")
