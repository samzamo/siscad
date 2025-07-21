import psycopg2
import pandas as pd
import shutil
import datetime
import os

def exportar_dados_para_planilha():
    data = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    nome_arquivo = f'backup_dados_{data}.xlsx'

    # Conexão com banco no Render
    conn = psycopg2.connect(
        host="dpg-d1u76qur433s73eedafg-a.oregon-postgres.render.com",
        database="siscad",
        user="siscad_user",
        password="V1q2FuX6g6f2hAwgjznkFTU0XO4RUHKE"
    )

    # Exporta tabelas como DataFrame
    df_alvos = pd.read_sql("SELECT * FROM pessoa", conn)
    df_usuarios = pd.read_sql("SELECT * FROM usuario", conn)
    conn.close()

    # Cria planilha com duas abas
    with pd.ExcelWriter(nome_arquivo) as writer:
        df_usuarios.to_excel(writer, sheet_name="usuarios", index=False)
        df_alvos.to_excel(writer, sheet_name="alvos", index=False)

    print(f"✅ Planilha gerada: {nome_arquivo}")

def exportar_imagens_zip():
    data = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    origem = 'static/IMAGEM'
    destino = f'backup_imagens_{data}'

    # Cria arquivo ZIP da pasta de imagens
    shutil.make_archive(destino, 'zip', origem)
    print(f"✅ Imagens zipadas: {destino}.zip")

if __name__ == '__main__':
    exportar_dados_para_planilha()
    exportar_imagens_zip()