# gerar_planilha_fotos.py

import pandas as pd
from app import app, db, pessoa  # ajuste os imports conforme seu projeto

def gerar_planilha():
    with app.app_context():
        dados = []

        for p in pessoa.query.all():
            if p.foto and p.foto.startswith("http"):
                dados.append({
                    "ID": p.id,
                    "Nome": p.nome,
                    "Foto": p.foto
                })

        df = pd.DataFrame(dados)
        df.to_excel("fotos_salvas.xlsx", index=False)
        print("✅ Planilha gerada com sucesso: fotos_salvas.xlsx")

if __name__ == "__main__":
    gerar_planilha()
