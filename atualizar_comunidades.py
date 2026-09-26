# -*- coding: utf-8 -*-
"""
atualizar_comunidades.py
=========================
Preenche a coluna "comunidade" de quem já está cadastrado, usando o
endereço (coluna "octopus") + bairro/município já salvos -- o mesmo
jeito que o cadastro novo já faz sozinho.

Só mexe em quem AINDA NÃO tem comunidade preenchida (não sobrescreve
quem já tem). Pra reprocessar todo mundo, troque FORCAR_TODOS pra True
lá embaixo.

Usa o Nominatim (OpenStreetMap, gratuito) pra achar a lat/lon do
endereço, então respeita o limite deles de 1 requisição por segundo --
por isso é devagar num banco grande, mas roda uma vez só.

COMO USAR (terminal do VS Code, na pasta do projeto)
-----------------------------------------------------
    python atualizar_comunidades.py
"""

import time
import requests
from app import app, db, Pessoa, encontrar_comunidade

FORCAR_TODOS = False  # True = reprocessa até quem já tem comunidade

_LIXO_OCTOPUS = {'SIM', 'NAO', 'NÃO', 'NONE', 'EMPTY_STRING', '-', ''}


def _extrair_endereco(octopus):
    if not octopus:
        return ''
    texto = octopus.strip()
    if 'ENDEREÇO:' in texto.upper():  # formato antigo, multi-linha
        for linha in texto.split('\n'):
            if 'ENDEREÇO:' in linha.upper():
                texto = linha.split(':', 1)[-1].strip()
                break
    return '' if texto.upper() in _LIXO_OCTOPUS else texto


def _geocodificar(endereco):
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'format': 'json', 'limit': 1, 'q': endereco},
            headers={'User-Agent': 'SISCAD/1.0 (atualizacao-comunidades)'},
            timeout=8,
        )
        dados = resp.json()
        if dados:
            return float(dados[0]['lat']), float(dados[0]['lon'])
    except Exception:
        pass
    return None


def main():
    with app.app_context():
        query = Pessoa.query
        if not FORCAR_TODOS:
            query = query.filter((Pessoa.comunidade.is_(None)) | (Pessoa.comunidade == ''))
        pessoas = query.all()
        total = len(pessoas)
        print(f"🔎 {total} cadastro(s) pra verificar...\n")

        contagem = {'atualizados': 0, 'sem_endereco': 0, 'nao_localizado': 0, 'fora_comunidade': 0}

        for i, pessoa in enumerate(pessoas, start=1):
            prefixo = f"[{i}/{total}] {pessoa.nome or '(sem nome)'}"
            endereco = _extrair_endereco(pessoa.octopus)

            if not endereco:
                print(f"{prefixo} -- sem endereço utilizável, pulei.")
                contagem['sem_endereco'] += 1
                continue

            partes = [endereco] + [p for p in (pessoa.bairro, pessoa.municipio) if p]
            ponto = _geocodificar(', '.join(partes))
            time.sleep(1)  # limite gratuito do Nominatim: 1 requisição/segundo

            if not ponto and len(partes) > 1:
                ponto = _geocodificar(endereco)  # tenta de novo só com o endereço puro
                time.sleep(1)

            if not ponto:
                print(f"{prefixo} -- não localizei o endereço no mapa.")
                contagem['nao_localizado'] += 1
                continue

            comunidade = encontrar_comunidade(*ponto)
            if not comunidade:
                print(f"{prefixo} -- fora das comunidades mapeadas.")
                contagem['fora_comunidade'] += 1
                continue

            pessoa.comunidade = comunidade
            db.session.commit()
            contagem['atualizados'] += 1
            print(f"{prefixo} -- ✅ {comunidade}")

        print("\n──────────────────────────────")
        print(f"✅ Atualizados:             {contagem['atualizados']}")
        print(f"⚠️  Sem endereço:            {contagem['sem_endereco']}")
        print(f"⚠️  Endereço não localizado: {contagem['nao_localizado']}")
        print(f"⚠️  Fora de comunidades:     {contagem['fora_comunidade']}")
        print(f"📋 Total verificado:        {total}")


if __name__ == "__main__":
    main()
