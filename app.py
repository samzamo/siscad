from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, date
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from markupsafe import Markup
import time
import json
import hashlib, os, unicodedata, socket
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import re
import requests
import pdfplumber
import xml.etree.ElementTree as ET


app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura_123'

# 🔗 Conexão com banco PostgreSQL no Neon
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql+psycopg2://neondb_owner:npg_fCVgz9kF0RBD@ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech/neondb'
    '?sslmode=require&connect_timeout=20'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

# ✅ Inicializa o banco e as migrações
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 🌥️ Configuração do Cloudinary
cloudinary.config( 
  cloud_name = 'dygav0zig', 
  api_key = '356954525268762', 
  api_secret = '9KXP41yJPdXDj78aK_S6CKl_9-I' 
)

# ✅ Função para normalizar texto (remove acentos e converte para minúsculas)
def normalizar(texto):
    if not texto:
        return ''
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    return texto.lower()

def limpar_texto(texto):
    texto = texto.upper()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

# ─────────────────────────────────────────────────────────────────────────
# Comunidades (AIS 18) -- carrega o KML uma única vez na memória e localiza
# a comunidade de um ponto (lat/lon) por geometria pura em Python, sem
# nenhuma biblioteca extra (nem shapely) e sem nenhum serviço pago.
# ─────────────────────────────────────────────────────────────────────────
_KML_NS = {'k': 'http://www.opengis.net/kml/2.2'}

def _carregar_comunidades_kml(caminho):
    comunidades = []
    try:
        tree = ET.parse(caminho)
    except Exception as e:
        print(f'⚠️ Não consegui ler o KML de comunidades: {e}')
        return comunidades

    for pm in tree.getroot().findall('.//k:Placemark', _KML_NS):
        nome_el = pm.find('k:name', _KML_NS)
        nome = (nome_el.text or '').strip() if nome_el is not None else ''
        if not nome:
            continue
        aneis = []
        for poly in pm.findall('.//k:Polygon', _KML_NS):
            coords_el = poly.find('.//k:outerBoundaryIs/k:LinearRing/k:coordinates', _KML_NS)
            if coords_el is None or not coords_el.text:
                continue
            anel = []
            for par in coords_el.text.strip().split():
                partes = par.split(',')
                if len(partes) >= 2:
                    try:
                        anel.append((float(partes[0]), float(partes[1])))  # (lon, lat)
                    except ValueError:
                        continue
            if len(anel) >= 3:
                aneis.append(anel)
        if aneis:
            comunidades.append({'nome': nome, 'nome_normalizado': limpar_texto(nome), 'aneis': aneis})
    return comunidades

def _ponto_no_anel(lon, lat, anel):
    dentro = False
    n = len(anel)
    x1, y1 = anel[0]
    for i in range(1, n + 1):
        x2, y2 = anel[i % n]
        if (y1 > lat) != (y2 > lat):
            x_intersecao = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < x_intersecao:
                dentro = not dentro
        x1, y1 = x2, y2
    return dentro

def encontrar_comunidade(lat, lon):
    for c in COMUNIDADES_AIS18:
        for anel in c['aneis']:
            if _ponto_no_anel(lon, lat, anel):
                return c['nome_normalizado']
    return None

COMUNIDADES_AIS18 = _carregar_comunidades_kml(os.path.join(os.path.dirname(__file__), 'dados', 'Comunidades.kml'))
print(f'🗺️  {len(COMUNIDADES_AIS18)} comunidades (AIS 18) carregadas do KML.')

# ─────────────────────────────────────────────────────────────────────────
# Busca fonética (por som, não só por grafia exata)
# Reduz cada palavra a um "esqueleto" que ignora as variações de escrita
# mais comuns em nomes/apelidos em português -- ex: FELIPE, PHELIPE, FILIPE
# e PHILIP viram todos o mesmo código, assim como LORA/LOIRA/LORAH e
# ALIN/AALINHO. Isso roda só com Python puro, sem serviço externo.
# ─────────────────────────────────────────────────────────────────────────
_VOGAIS = set('AEIOU')

def _codigo_fonetico_palavra(palavra):
    if not palavra:
        return ''
    p = limpar_texto(palavra)

    # Substituições de grafias com o mesmo som
    p = p.replace('PH', 'F')
    p = p.replace('TH', 'T')
    p = p.replace('CH', 'X')
    p = p.replace('CT', 'T')   # ex: victor/vitor, victoria/vitória
    p = p.replace('K', 'C')
    p = p.replace('W', 'V')
    p = p.replace('Y', 'I')
    p = re.sub(r'H', '', p)    # H isolado costuma ser mudo (jhonata/jonata, aalinho)
    if p.endswith('M'):
        p = p[:-1] + 'N'       # final -M soa como -N (yasmin/iasmim)

    # Colapsa letras repetidas seguidas (RR -> R, SS -> S...)
    sem_repeticao = []
    for letra in p:
        if not sem_repeticao or sem_repeticao[-1] != letra:
            sem_repeticao.append(letra)
    p = ''.join(sem_repeticao)
    if not p:
        return ''

    # Mantém a 1ª letra; nas seguintes, guarda só as consoantes -- é a
    # variação das vogais internas que mais muda a grafia (Felipe/Filipe,
    # Lora/Loira), então elas não entram no código depois da primeira letra.
    codigo = p[0]
    for letra in p[1:]:
        if letra not in _VOGAIS:
            codigo += letra
    return codigo


def calcular_fonetico(texto):
    """Código fonético de cada palavra do texto, na ordem, separado por
    espaço -- permite achar qualquer palavra dentro de um nome composto."""
    if not texto:
        return ''
    return ' '.join(_codigo_fonetico_palavra(p) for p in texto.split() if p)


def _condicao_fonetica(termo, *colunas):
    """Monta a condição SQL: cada palavra do termo buscado precisa bater
    com o INÍCIO de alguma palavra do código fonético guardado (usa regex
    nativo do Postgres, sem precisar de extensão nenhuma)."""
    palavras = [p for p in (termo or '').split() if p]
    if not palavras:
        return None

    condicoes_das_palavras = []
    for palavra in palavras:
        codigo = _codigo_fonetico_palavra(palavra)
        if not codigo:
            continue
        padrao = f'(^|\\s){re.escape(codigo)}'
        condicao_colunas = colunas[0].op('~')(padrao)
        for coluna in colunas[1:]:
            condicao_colunas = condicao_colunas | coluna.op('~')(padrao)
        condicoes_das_palavras.append(condicao_colunas)

    if not condicoes_das_palavras:
        return None

    resultado = condicoes_das_palavras[0]
    for cond in condicoes_das_palavras[1:]:
        resultado = resultado & cond
    return resultado

# ─────────────────────────────────────────────────────────────────────────
# "Nome parecido" (busca PADRÃO, mais rigorosa que a fonética acima)
# Só junta grafias que são praticamente a MESMA palavra escrita diferente
# (Felipe/Phelipe/Filipe, Karine/Karyne/Carine) -- ao contrário da fonética,
# não reduz tanto a palavra, então não confunde nomes de fato diferentes
# (ex: não junta Bruno com Bruna, nem Lora com Lorena).
# ─────────────────────────────────────────────────────────────────────────
def _forma_comparacao_palavra(palavra):
    if not palavra:
        return ''
    p = limpar_texto(palavra)
    p = p.replace('PH', 'F')
    p = p.replace('TH', 'T')
    p = p.replace('CH', 'X')
    p = p.replace('CT', 'T')
    p = p.replace('K', 'C')
    p = p.replace('W', 'V')
    p = p.replace('Y', 'I')
    p = re.sub(r'H', '', p)
    if p.endswith('M'):
        p = p[:-1] + 'N'
    p = p.replace('E', 'I')  # confusão E/I é comum na escrita em português

    sem_repeticao = []
    for letra in p:
        if not sem_repeticao or sem_repeticao[-1] != letra:
            sem_repeticao.append(letra)
    return ''.join(sem_repeticao)


def calcular_forma_comparacao(texto):
    if not texto:
        return ''
    return ' '.join(_forma_comparacao_palavra(p) for p in texto.split() if p)


def _condicao_nome_parecido(termo, *colunas):
    """Cada palavra do termo buscado precisa bater EXATAMENTE (início e fim
    de palavra) com alguma palavra da forma comparável guardada."""
    palavras = [p for p in (termo or '').split() if p]
    if not palavras:
        return None

    condicoes_das_palavras = []
    for palavra in palavras:
        forma = _forma_comparacao_palavra(palavra)
        if not forma:
            continue
        padrao = f'(^|\\s){re.escape(forma)}(\\s|$)'
        condicao_colunas = colunas[0].op('~')(padrao)
        for coluna in colunas[1:]:
            condicao_colunas = condicao_colunas | coluna.op('~')(padrao)
        condicoes_das_palavras.append(condicao_colunas)

    if not condicoes_das_palavras:
        return None

    resultado = condicoes_das_palavras[0]
    for cond in condicoes_das_palavras[1:]:
        resultado = resultado & cond
    return resultado

# ─────────────────────────────────────────────────────────────────────────
# Comboboxes dinâmicos (Facção / Município / Bairro)
# As listas abaixo são as opções "padrão", já usadas nos templates hoje.
# O botão "+" nas telas só grava no banco (tabela opcao_cadastro) os itens
# NOVOS que o usuário adicionar -- o que já existe aqui não precisa migrar.
# ─────────────────────────────────────────────────────────────────────────
FACCOES_PADRAO = ["CV", "PCC", "GDE", "MASSA", "TCP", "ADA", "SEM"]

MUNICIPIOS_PADRAO = [limpar_texto(m) for m in ["FORTALEZA", "CAUCAIA", "MARACANAÚ"]]

# Tipos de crime/ocorrência do combobox "TIPO" no modal de anotações.
# Começa vazio de propósito -- a lista cresce pelo botão "+" (igual
# facção/município/bairro), sem precisar mexer no código depois.
CRIMES_PADRAO = []

BAIRROS_PADRAO = {
    limpar_texto("FORTALEZA"): [limpar_texto(b) for b in [
        "Aerolândia", "Aeroporto", "Aldeota", "Alto Alegre", "Alto da Balança", "Álvaro Weyne",
        "Amadeu Furtado", "Ancuri", "Antônio Bezerra", "Antônio Diogo", "Autran Nunes",
        "Barra do Ceará", "Barroso", "Bela Vista", "Benfica", "Boa Vista", "Bom Futuro",
        "Bom Jardim", "Bonsucesso", "Cachoeirinha", "Cais do Porto", "Cajazeiras", "Cambeba",
        "Canindezinho", "Carlito Pamplona", "Centro", "Cidade 2000", "Cidade dos Funcionários",
        "Coaçu", "Cocó", "Conjunto Ceará", "Conjunto Esperança", "Conjunto Palmeiras",
        "Couto Fernandes", "Cristo Redentor", "Curió", "Damas", "De Lourdes", "Demócrito Rocha",
        "Dendê", "Dias Macedo", "Dionísio Torres", "Dom Lustosa", "Edson Queiroz",
        "Engenheiro Luciano Cavalcante", "Farias Brito", "Fátima", "Floresta", "Granja Lisboa",
        "Granja Portugal", "Guajiru", "Henrique Jorge", "Itaoca", "Itaperi", "Jacarecanga",
        "Jangurussu", "Jardim América", "Jardim Cearense", "Jardim das Oliveiras", "Jardim Guanabara",
        "Jardim Iracema", "João XXIII", "Joaquim Távora", "Jóquei Clube", "José Bonifácio",
        "José de Alencar", "Lagoa Redonda", "Manoel Dias Branco", "Manuel Sátiro", "Maraponga",
        "Meireles", "Messejana", "Mondubim", "Monte Castelo", "Montese", "Moura Brasil",
        "Mucuripe", "Novo Mondubim", "Olavo Oliveira", "Padre Andrade", "Pan Americano",
        "Papicu", "Parangaba", "Parque Araxá", "Parque Dois Irmãos", "Parque Genibaú",
        "Parque Iracema", "Parque Manibura", "Parque Presidente Vargas", "Parque Santa Maria",
        "Parque Santa Rosa", "Parque São José", "Parquelândia", "Parreão", "Passaré",
        "Patriolino Ribeiro", "Paupina", "Pedras", "Pici", "Pirambu", "Planalto Ayrton Senna",
        "Praia de Iracema", "Prefeito José Walter", "Presidente Kennedy", "Quintino Cunha",
        "Rodolfo Teófilo", "Sabiaguaba", "Salinas", "São Bento", "São Gerardo",
        "São João do Tauape", "Sapiranga", "Serrinha", "Siqueira", "Varjota", "Vicente Pinzon",
        "Vila Ellery", "Vila Peri", "Vila União", "Vila Velha",
    ]],
    limpar_texto("CAUCAIA"): [limpar_texto(b) for b in ["Jurema", "Tabapuá", "Parque Soledade"]],
    limpar_texto("MARACANAÚ"): [limpar_texto(b) for b in ["Jardim Jatobá", "Pajuçara", "Centro"]],
}


def _opcoes_padrao(tipo, municipio=None):
    if tipo == 'faccao':
        return list(FACCOES_PADRAO)
    if tipo == 'municipio':
        return list(MUNICIPIOS_PADRAO)
    if tipo == 'crime':
        return list(CRIMES_PADRAO)
    if tipo == 'bairro':
        alvo_norm = normalizar(municipio or '')
        for chave, lista in BAIRROS_PADRAO.items():
            if normalizar(chave) == alvo_norm:
                return list(lista)
        return []
    return []


@app.route('/opcoes/<tipo>', methods=['GET'])
def listar_opcoes(tipo):
    if 'usuario_logado' not in session:
        return jsonify([]), 401
    if tipo not in ('faccao', 'municipio', 'bairro', 'crime'):
        return jsonify([]), 400

    municipio = request.args.get('municipio', '')
    padrao = _opcoes_padrao(tipo, municipio)

    # Se a tabela opcao_cadastro ainda não existir (ex: esqueceu de rodar
    # criar_tabela_opcoes.py), não deixa o combobox inteiro quebrar --
    # mostra pelo menos as opções padrão e loga o erro real no terminal.
    try:
        query = OpcaoCadastro.query.filter_by(tipo=tipo)
        if tipo == 'bairro':
            query = query.filter_by(municipio=municipio)
        extras = query.order_by(OpcaoCadastro.valor).all()
    except Exception as e:
        db.session.rollback()
        print(f"[/opcoes/{tipo}] Aviso: não consegui ler a tabela opcao_cadastro "
              f"(rode 'python criar_tabela_opcoes.py' se ainda não rodou). Erro: {e}")
        extras = []

    vistos = set()
    resultado = []
    # Itens padrão: sem id -> o front-end sabe que não dá pra editar/excluir.
    for valor in padrao:
        chave = normalizar(valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append({'valor': valor, 'id': None})
    # Itens adicionados pelo usuário: com id -> editáveis/excluíveis.
    for o in extras:
        chave = normalizar(o.valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append({'valor': o.valor, 'id': o.id})

    return jsonify(resultado)


@app.route('/opcoes/<tipo>', methods=['POST'])
def adicionar_opcao(tipo):
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401
    if tipo not in ('faccao', 'municipio', 'bairro', 'crime'):
        return jsonify({'erro': 'Tipo inválido.'}), 400

    dados = request.get_json(silent=True) or {}
    valor = limpar_texto((dados.get('valor') or '').strip())
    municipio = limpar_texto((dados.get('municipio') or '').strip())

    if not valor:
        return jsonify({'erro': 'Digite um valor.'}), 400
    if tipo == 'bairro' and not municipio:
        return jsonify({'erro': 'Selecione o município antes de adicionar o bairro.'}), 400

    try:
        existentes = _opcoes_padrao(tipo, municipio)
        query = OpcaoCadastro.query.filter_by(tipo=tipo)
        if tipo == 'bairro':
            query = query.filter_by(municipio=municipio)
        existentes += [o.valor for o in query.all()]

        valor_norm = normalizar(valor)
        if any(normalizar(existente) == valor_norm for existente in existentes):
            return jsonify({'erro': f'"{valor}" já está na lista.'}), 409

        nova = OpcaoCadastro(
            tipo=tipo,
            municipio=municipio if tipo == 'bairro' else None,
            valor=valor,
        )
        db.session.add(nova)
        db.session.commit()
        return jsonify({'valor': nova.valor, 'id': nova.id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"[/opcoes/{tipo}] Erro ao adicionar opção: {e}")
        return jsonify({
            'erro': 'Não foi possível salvar no banco. A tabela opcao_cadastro '
                    'existe? Rode: python criar_tabela_opcoes.py'
        }), 500


@app.route('/opcoes/<tipo>/<int:opcao_id>', methods=['PUT'])
def editar_opcao(tipo, opcao_id):
    """Edita um item ADICIONADO pelo usuário (não afeta os padrões do
    sistema). Cadastros que já usam o valor antigo NÃO são alterados
    automaticamente -- só a lista de opções muda."""
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401
    if tipo not in ('faccao', 'municipio', 'bairro', 'crime'):
        return jsonify({'erro': 'Tipo inválido.'}), 400

    dados = request.get_json(silent=True) or {}
    valor = limpar_texto((dados.get('valor') or '').strip())
    if not valor:
        return jsonify({'erro': 'Digite um valor.'}), 400

    try:
        opcao = OpcaoCadastro.query.filter_by(id=opcao_id, tipo=tipo).first()
        if not opcao:
            return jsonify({'erro': 'Item não encontrado (itens padrão do sistema não podem ser editados aqui).'}), 404

        existentes = _opcoes_padrao(tipo, opcao.municipio)
        query = OpcaoCadastro.query.filter_by(tipo=tipo)
        if tipo == 'bairro':
            query = query.filter_by(municipio=opcao.municipio)
        existentes += [o.valor for o in query.all() if o.id != opcao.id]

        valor_norm = normalizar(valor)
        if any(normalizar(existente) == valor_norm for existente in existentes):
            return jsonify({'erro': f'"{valor}" já está na lista.'}), 409

        opcao.valor = valor
        db.session.commit()
        return jsonify({'valor': opcao.valor, 'id': opcao.id})
    except Exception as e:
        db.session.rollback()
        print(f"[/opcoes/{tipo}/{opcao_id}] Erro ao editar: {e}")
        return jsonify({'erro': 'Não foi possível salvar a edição no banco.'}), 500


@app.route('/opcoes/<tipo>/<int:opcao_id>', methods=['DELETE'])
def excluir_opcao(tipo, opcao_id):
    """Remove um item ADICIONADO pelo usuário da lista. Cadastros que já
    usam esse valor continuam com o dado normalmente -- só sai da lista de
    opções pra novos cadastros/edições."""
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401
    if tipo not in ('faccao', 'municipio', 'bairro', 'crime'):
        return jsonify({'erro': 'Tipo inválido.'}), 400

    try:
        opcao = OpcaoCadastro.query.filter_by(id=opcao_id, tipo=tipo).first()
        if not opcao:
            return jsonify({'erro': 'Item não encontrado (itens padrão do sistema não podem ser excluídos aqui).'}), 404
        db.session.delete(opcao)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        print(f"[/opcoes/{tipo}/{opcao_id}] Erro ao excluir: {e}")
        return jsonify({'erro': 'Não foi possível excluir no banco.'}), 500

def upload_image_to_cloudinary(file_storage, nome_alvo):
    public_id = f"{nome_alvo}_{int(time.time())}"
    result = cloudinary.uploader.upload(
        file_storage,
        public_id=public_id,
        overwrite=False
    )
    # Retorna a URL (pra exibir) e o public_id (pra poder excluir depois lá do Cloudinary)
    return result['secure_url'], result.get('public_id', public_id)

def extrair_public_id_cloudinary(url):
    """Extrai o public_id a partir da URL do Cloudinary. Serve de fallback
    para fotos que foram enviadas antes de guardarmos o public_id no banco
    -- sem isso não teríamos como excluí-las lá do Cloudinary depois."""
    if not url:
        return None
    m = re.search(r'/upload/(?:v\d+/)?(.+?)\.\w+$', url)
    return m.group(1) if m else None

# ✅ remover acento
def remover_acentos(texto):
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')

# ✅ resumo com destaque
def resumoComDestaque(anotacao, termo):
    if not termo or not anotacao:
        return anotacao[:120] + '...'

    termo_norm = remover_acentos(termo.lower())
    anotacao_norm = remover_acentos(anotacao.lower())

    index = anotacao_norm.find(termo_norm)
    if index == -1:
        return anotacao[:120] + '...'

    start = max(0, index - 40)
    end = min(len(anotacao), index + len(termo) + 40)
    trecho = anotacao[start:end]

    # Destaque o termo original no trecho
    regex = re.compile(re.escape(termo), re.IGNORECASE)
    trecho_destacado = regex.sub(
        lambda m: f'<span class="highlight">{m.group(0)}</span>', trecho
    )

    return Markup(trecho_destacado + '...')
# ✅Registra o filtro no Jinja
app.jinja_env.filters['resumoComDestaque'] = resumoComDestaque

def registrar_log(tipo, pessoa=None, usuario=None, detalhes=None):
    """Grava uma linha no histórico de atividades. Nunca derruba a
    requisição principal se algo der errado aqui."""
    try:
        if usuario is None and session.get('usuario_logado'):
            usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()
        db.session.add(AtividadeLog(
            usuario_id=usuario.id if usuario else None,
            usuario_nome=(usuario.username if usuario else session.get('usuario_logado')) or '—',
            tipo=tipo,
            pessoa_id=pessoa.id if pessoa else None,
            pessoa_nome=pessoa.nome if pessoa else None,
            detalhes=detalhes,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

def pode_ver_historico():
    if 'usuario_logado' not in session:
        return False
    if session['usuario_logado'].strip().upper() == 'SAMARA':
        return True
    # Não exige mais ser admin: a SAMARA escolhe quem vê, seja admin,
    # moderador ou usuário normal.
    usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()
    return bool(usuario and usuario.pode_ver_historico)

@app.context_processor
def injetar_usuario_logado():
    # Deixa usuario_logado/is_admin/is_moderador disponíveis em QUALQUER
    # template que inclua _nav.html, sem precisar passar isso manualmente
    # em cada render_template(). Não altera nenhuma rota existente.
    tipo = session.get('tipo', 'normal')
    return dict(
        usuario_logado=session.get('usuario_logado'),
        is_admin=session.get('is_admin', False),
        is_moderador=(tipo == 'moderador'),
        pode_ver_historico_menu=pode_ver_historico() if 'usuario_logado' in session else False,
    )


# ✅ destacar texto nas pesquisas 
def destacar_termos(texto, termos):
    if not texto:
        return ''
    
    texto_original = texto
    texto_normalizado = normalizar(texto)

    # Mapeia posições dos termos encontrados
    destaques = []
    for termo in termos:
        termo_norm = normalizar(termo)
        for match in re.finditer(re.escape(termo_norm), texto_normalizado, re.IGNORECASE):
            destaques.append((match.start(), match.end()))

    # Evita sobreposição e aplica destaque
    resultado = ""
    i = 0
    for start, end in sorted(destaques):
        if start < i:
            continue  # ignora sobreposição
        resultado += texto_original[i:start]
        resultado += "<mark>" + texto_original[start:end] + "</mark>"
        i = end
    resultado += texto_original[i:]

    return resultado

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=False)
    tipo = db.Column(db.String(10), default='normal')
    email = db.Column(db.String(255), nullable=True)
    pode_ver_historico = db.Column(db.Boolean, default=False)  # só a SAMARA concede isso a outros admins
    cadastros = db.relationship('Pessoa', backref='usuario', lazy=True)

class AtividadeLog(db.Model):
    __tablename__ = 'atividade_log'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    usuario_nome = db.Column(db.String(100))
    tipo = db.Column(db.String(20))  # 'login', 'cadastro_criado', 'cadastro_editado'
    pessoa_id = db.Column(db.Integer, nullable=True)
    pessoa_nome = db.Column(db.String(255))
    detalhes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Pessoa(db.Model):
    __tablename__ = 'pessoa'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String, nullable=False)
    vulgo = db.Column(db.String)
    genitora = db.Column(db.String)
    bairro = db.Column(db.String)
    municipio = db.Column(db.String)
    anotacoes = db.Column(db.Text)
    foto = db.Column(db.String)  # Agora armazena a URL da imagem no Cloudinary
    foto_public_id = db.Column(db.String)  # public_id da foto atual no Cloudinary (pra permitir exclusão depois)
    octopus = db.Column(db.String)
    faccao = db.Column(db.String(100), nullable=True)
    octopusasint = db.Column(db.String(3))  # ✅ Novo campo: "Sim" ou "Não"
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))  # 👈 novo campo
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow) # data da criação
    fonetico_nome = db.Column(db.String(255))   # "esqueleto" fonético do nome, para busca aproximada
    fonetico_vulgo = db.Column(db.String(255))  # idem, para o vulgo
    forma_nome = db.Column(db.String(255))      # forma p/ "nome parecido" (busca padrão, mais rigorosa)
    forma_vulgo = db.Column(db.String(255))     # idem, para o vulgo
    comunidade = db.Column(db.String(150), nullable=True)  # comunidade (AIS 18), detectada automaticamente pelo endereço

class FotoHistorico(db.Model):
    """Fotos antigas de um alvo (substituídas ao atualizar o cadastro).
    Ficam guardadas aqui só até serem excluídas manualmente pelo admin --
    momento em que também são removidas do Cloudinary. Isso evita que fotos
    trocadas fiquem ocupando espaço no Cloudinary sem servir para nada."""
    __tablename__ = 'foto_historico'
    id = db.Column(db.Integer, primary_key=True)
    pessoa_id = db.Column(db.Integer, db.ForeignKey('pessoa.id'), nullable=False)
    url = db.Column(db.String, nullable=False)
    public_id = db.Column(db.String, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    pessoa = db.relationship('Pessoa', backref=db.backref('fotos_antigas', lazy=True))

class Cadastro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(255))  # ou qualquer outro campo
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

class Mandado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String)
    genitora = db.Column(db.String)
    tipificacao = db.Column(db.String)
    data = db.Column(db.String)
    endereco = db.Column(db.String)
    status = db.Column(db.String(20), default='neutro')


def resumir_endereco_mandado(endereco):
    """Versão curta do endereço (só rua + bairro) pra listagem em
    /mandados -- o endereço completo continua salvo/usado no ícone do
    Google Maps. Mesma lógica de separação usada na extração do PDF
    (o bairro é o trecho logo antes do "CEP", não fixo na 2ª posição,
    por causa de complementos tipo "Nºs 751 OU 770" no meio)."""
    if not endereco:
        return ''
    partes = [p.strip() for p in endereco.split(',') if p.strip()]
    if not partes:
        return endereco
    rua = partes[0]
    idx_cep = next((i for i, p in enumerate(partes) if re.match(r'(?i)^cep\b', p)), None)
    if idx_cep is not None and idx_cep >= 2:
        bairro = partes[idx_cep - 1]
    elif len(partes) > 1:
        bairro = partes[1]
    else:
        bairro = ''
    return ' - '.join(p for p in [rua, bairro] if p)


app.jinja_env.globals['resumir_endereco'] = resumir_endereco_mandado

# ─────────────────────────────────────────────────────────────────────────
# Importação de PDF de Mandado (BNMP / Tribunal de Justiça)
# Lê o texto do PDF (pdfplumber, sem custo, sem serviço externo) e usa
# expressões regulares em cima do layout padrão do BNMP 3.0 -- usado por
# praticamente todos os tribunais do país para mandado de prisão/internação.
# Se o PDF for uma imagem escaneada (sem texto selecionável), a extração
# simplesmente não encontra nada e a tela avisa pra digitar manualmente.
# ─────────────────────────────────────────────────────────────────────────
MESES_PT = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9,
    'outubro': 10, 'novembro': 11, 'dezembro': 12,
}

def _extrair_texto_pdf_mandado(file_storage):
    partes = []
    with pdfplumber.open(file_storage) as pdf:
        for page in pdf.pages:
            partes.append(page.extract_text() or '')
    return '\n'.join(partes)

def _campo(padrao, texto, flags=re.IGNORECASE):
    r = re.search(padrao, texto, flags)
    return r.group(1).strip() if r else None

def _campo_util(padrao, texto, flags=re.IGNORECASE | re.MULTILINE):
    valor = _campo(padrao, texto, flags)
    if not valor or valor.strip().lower().startswith('não informad'):
        return ''
    return valor.strip()

def extrair_dados_mandado(texto):
    """Recebe o texto já extraído do PDF e devolve um dicionário com os
    campos reconhecidos. Nenhum campo é obrigatório -- o que não for
    encontrado simplesmente volta vazio, pra revisão manual na tela."""
    d = {}

    d['tipo_mandado'] = _campo(r'^\s*(MANDADO DE [A-ZÇÃÕÁÉÍÓÚÂÊÔ ]+?)\s*$', texto, re.MULTILINE) or ''
    d['numero_documento'] = _campo(r'N[°º]\s*do Documento:\s*([\d./-]+)', texto) or ''
    d['nome'] = _campo(r'Nome da Pessoa:\s*(.+?)\s+CPF:', texto) or ''
    d['cpf'] = _campo(r'CPF:\s*([\d.\-]+)', texto) or ''
    d['alcunha'] = _campo_util(r'Alcunha:\s*(.+?)\s*$', texto)
    d['natural_de'] = _campo_util(r'Natural de:\s*(.+?)\s*$', texto)
    d['data_nascimento'] = _campo(r'Data de Nascimento:\s*([\d/]+)', texto) or ''
    d['sexo'] = _campo(r'Sexo:\s*(\w+)', texto) or ''
    d['cor'] = _campo_util(r'Cor:\s*(.+?)\s*$', texto)
    d['rg'] = _campo_util(r'\bRG:\s*(.+?)\s*$', texto)

    mae = _campo(r'Filia[çc][aã]o:\s*(.+?)\(m[ãa]e\)', texto, re.IGNORECASE | re.DOTALL)
    d['genitora'] = re.sub(r'\s+', ' ', mae).strip() if mae else ''

    pai = _campo(r'\be\s+(.+?)\(pai\)', texto, re.IGNORECASE | re.DOTALL)
    d['genitor'] = re.sub(r'\s+', ' ', pai).strip() if pai else ''

    d['logradouro'] = d['bairro'] = d['numero_endereco'] = d['cep'] = ''
    d['municipio'] = d['uf'] = d['endereco_bruto'] = ''
    endereco_bruto = _campo(r'Endere[çc]os\s*\n(.+?)\s*$', texto, re.MULTILINE)
    if endereco_bruto:
        d['endereco_bruto'] = endereco_bruto
        partes_end = [p.strip() for p in endereco_bruto.split(',')]
        d['logradouro'] = partes_end[0] if len(partes_end) > 0 else ''

        # O endereço vem como:
        #   Rua X, número, [complementos opcionais - "Nºs alternativos" etc.], Bairro, CEP ..., Município - UF
        # O bairro é sempre o trecho logo antes do CEP -- e não o 2º item da
        # lista, porque às vezes há um número extra de complemento no meio
        # (o que fazia o "bairro" sair errado, com o número da casa).
        idx_cep = next(
            (i for i, p in enumerate(partes_end) if re.match(r'(?i)^cep\b', p)),
            None
        )
        if idx_cep is not None and idx_cep >= 2:
            d['bairro'] = partes_end[idx_cep - 1]
            d['numero_endereco'] = ', '.join(p for p in partes_end[1:idx_cep - 1] if p)
        else:
            # Formato inesperado (sem "CEP" separado por vírgula) -- mantém o
            # comportamento antigo como último recurso, pra não deixar vazio.
            d['bairro'] = partes_end[1] if len(partes_end) > 1 else ''
            d['numero_endereco'] = partes_end[2] if len(partes_end) > 2 else ''

        cep_m = re.search(r'CEP\s*([\d.\-]+)', endereco_bruto, re.IGNORECASE)
        d['cep'] = cep_m.group(1) if cep_m else ''
        muni_uf_m = re.search(r',\s*([A-Za-zÀ-ú\s]+?)\s*[-/]\s*([A-Z]{2})\s*[.,]?\s*$', endereco_bruto)
        d['municipio'] = muni_uf_m.group(1).strip() if muni_uf_m else ''
        d['uf'] = muni_uf_m.group(2).strip() if muni_uf_m else ''

    d['processo'] = _campo(r'N[ºo]\s*do processo:\s*([\d./-]+)', texto) or ''
    if not d['numero_documento']:
        # Nem todo mandado tem uma linha separada "Nº do Documento" -- nesse
        # caso o número que identifica o mandado é mesmo o do processo.
        d['numero_documento'] = d['processo']
    orgao = _campo(r'[ÓO]rg[ãa]o Judicial:\s*(.+?)\s*$', texto, re.MULTILINE) or ''
    d['orgao_judicial'] = orgao
    comarca_m = re.search(r'COMARCA DE ([A-ZÇÃÕÁÉÍÓÚÂÊÔ\s]+?)(?:\s*-\s*TJ|$)', orgao, re.IGNORECASE)
    d['comarca'] = comarca_m.group(1).strip().title() if comarca_m else ''

    d['especie'] = _campo(r'Esp[eé]cie d[ae] (?:Interna[çc][ãa]o|Pris[ãa]o):\s*(.+?)\s*$', texto, re.MULTILINE) or ''

    blocos = re.findall(
        r'Lei:\s*([\d.]+)\s*\n?Artigo:\s*(\d+[ºo]?)\s*\n?(?:Par[aá]grafo:\s*(\S+)|Inciso:\s*(\S+))?',
        texto
    )
    tipificacoes = []
    for lei, artigo, paragrafo, inciso in blocos:
        item = f'Lei {lei}, Art. {artigo}'
        if paragrafo:
            item += f', §{paragrafo}'
        if inciso:
            item += f', Inc. {inciso}'
        tipificacoes.append(item)
    d['tipificacao'] = '; '.join(tipificacoes)

    d['prazo_minimo'] = _campo(r'Prazo M[íi]nimo da (?:Interna[çc][ãa]o|Pris[ãa]o):\s*(.+?)\s*$', texto, re.MULTILINE) or ''
    d['validade'] = _campo(r'Validade:\s*([\d/]+)', texto) or ''

    lav = re.search(r'Lavrado por:\s*([A-Za-zÀ-ú\s]+),\s*(\d{1,2}) de (\w+) de (\d{4})', texto, re.IGNORECASE)
    if not lav:
        # Sem "Lavrado por:" -- procura o mesmo padrão "Cidade, DD de Mês de
        # AAAA" em qualquer lugar do texto (costuma aparecer sozinho, perto
        # de "Observação:", no fecho do documento).
        lav = re.search(r'\b([A-ZÀ-Ú][a-zà-ú]+),\s*(\d{1,2}) de (\w+) de (\d{4})', texto)
    d['cidade_lavratura'] = ''
    d['data_mandado'] = ''
    if lav:
        cidade, dia, mes_nome, ano = lav.groups()
        d['cidade_lavratura'] = cidade.strip()
        mes_num = MESES_PT.get(mes_nome.lower())
        if mes_num:
            d['data_mandado'] = f'{int(dia):02d}/{mes_num:02d}/{ano}'

    if not d['data_mandado']:
        # Ainda não achou -- tenta outros rótulos comuns nesse tipo de
        # documento antes de deixar em branco.
        alt = (
            _campo(r'Data de Expedi[çc][ãa]o:?\s*(\d{1,2}/\d{1,2}/\d{4})', texto)
            or _campo(r'Expedido em:?\s*(\d{1,2}/\d{1,2}/\d{4})', texto)
            or _campo(r'Data do Documento:?\s*(\d{1,2}/\d{1,2}/\d{4})', texto)
            or _campo(r'assinado (?:eletronicamente|digitalmente) pel[oa].*?em\s*(\d{1,2}/\d{1,2}/\d{4})', texto, re.IGNORECASE | re.DOTALL)
        )
        if alt:
            d['data_mandado'] = alt

    return d

class OpcaoCadastro(db.Model):
    """Itens ADICIONADOS pelo usuário nos comboboxes de facção, município e
    bairro (via botão '+'). As opções padrão (CV, PCC, FORTALEZA, a lista de
    bairros etc.) continuam fixas no código -- aqui só entram as extras,
    para não precisar duplicar nem migrar nada que já existe."""
    __tablename__ = 'opcao_cadastro'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)        # 'faccao', 'municipio' ou 'bairro'
    municipio = db.Column(db.String(100), nullable=True)   # só usado quando tipo == 'bairro'
    valor = db.Column(db.String(150), nullable=False)


class Anotacao(db.Model):
    """Anotações estruturadas (Data + Tipo + Contexto) de um alvo, criadas
    pelo botão '+' da tela de Anotações. Cada uma vira um 'balão' com
    edição/exclusão próprias, independente do resto do cadastro.

    O campo antigo Pessoa.anotacoes (texto livre) continua existindo e é
    atualizado sozinho a cada mudança aqui (ver sincronizar_anotacoes_legado),
    só para a busca reversa e a pesquisa em lote -- que já leem esse campo --
    continuarem funcionando sem precisar mexer nelas."""
    __tablename__ = 'anotacao'
    id = db.Column(db.Integer, primary_key=True)
    pessoa_id = db.Column(db.Integer, db.ForeignKey('pessoa.id'), nullable=False)
    data = db.Column(db.Date, nullable=True)
    tipo = db.Column(db.String(150), nullable=True)
    contexto = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    pessoa = db.relationship('Pessoa', backref=db.backref('anotacoes_lista', lazy=True))


def sincronizar_anotacoes_legado(pessoa):
    """Reconstrói pessoa.anotacoes (texto) a partir da lista estruturada de
    Anotacao, mais recente primeiro. Não commita sozinho -- quem chama
    decide quando salvar."""
    itens = Anotacao.query.filter_by(pessoa_id=pessoa.id).all()
    itens.sort(key=lambda a: (a.data or date.min, a.criado_em or datetime.min), reverse=True)
    linhas = []
    for a in itens:
        data_str = a.data.strftime('%d/%m/%Y') if a.data else ''
        cabecalho = ' '.join(filter(None, [f'[{data_str}]' if data_str else '', a.tipo or '']))
        linhas.append(f"{cabecalho}: {a.contexto}" if cabecalho else a.contexto)
    pessoa.anotacoes = '\n\n'.join(linhas)


def _anotacao_para_json(a):
    return {
        'id': a.id,
        'data': a.data.isoformat() if a.data else '',
        'tipo': a.tipo or '',
        'contexto': a.contexto or '',
    }


@app.route('/anotacoes/<int:pessoa_id>', methods=['GET'])
def listar_anotacoes(pessoa_id):
    if 'usuario_logado' not in session:
        return jsonify([]), 401
    try:
        itens = Anotacao.query.filter_by(pessoa_id=pessoa_id).all()
    except Exception as e:
        db.session.rollback()
        print(f"[/anotacoes/{pessoa_id}] Aviso: não consegui ler a tabela anotacao "
              f"(rode 'python criar_tabela_opcoes.py' se ainda não rodou). Erro: {e}")
        return jsonify([])
    itens.sort(key=lambda a: (a.data or date.min, a.criado_em or datetime.min), reverse=True)
    return jsonify([_anotacao_para_json(a) for a in itens])


@app.route('/anotacoes/<int:pessoa_id>', methods=['POST'])
def criar_anotacao(pessoa_id):
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401

    pessoa = Pessoa.query.get(pessoa_id)
    if not pessoa:
        return jsonify({'erro': 'Alvo não encontrado.'}), 404

    dados = request.get_json(silent=True) or {}
    contexto = (dados.get('contexto') or '').strip()
    tipo = (dados.get('tipo') or '').strip()
    data_str = (dados.get('data') or '').strip()

    if not contexto:
        return jsonify({'erro': 'Escreva o contexto da anotação.'}), 400

    data_valor = None
    if data_str:
        try:
            data_valor = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'erro': 'Data inválida.'}), 400

    try:
        nova = Anotacao(pessoa_id=pessoa.id, data=data_valor, tipo=tipo, contexto=contexto)
        db.session.add(nova)
        db.session.flush()
        sincronizar_anotacoes_legado(pessoa)
        db.session.commit()
        return jsonify(_anotacao_para_json(nova)), 201
    except Exception as e:
        db.session.rollback()
        print(f"[/anotacoes/{pessoa_id}] Erro ao adicionar anotação: {e}")
        return jsonify({
            'erro': 'Não foi possível salvar a anotação. A tabela "anotacao" '
                    'existe? Rode: python criar_tabela_opcoes.py'
        }), 500


@app.route('/anotacoes/<int:anotacao_id>', methods=['PUT'])
def editar_anotacao(anotacao_id):
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401

    anotacao = Anotacao.query.get(anotacao_id)
    if not anotacao:
        return jsonify({'erro': 'Anotação não encontrada.'}), 404

    dados = request.get_json(silent=True) or {}
    contexto = (dados.get('contexto') or '').strip()
    tipo = (dados.get('tipo') or '').strip()
    data_str = (dados.get('data') or '').strip()

    if not contexto:
        return jsonify({'erro': 'Escreva o contexto da anotação.'}), 400

    data_valor = None
    if data_str:
        try:
            data_valor = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'erro': 'Data inválida.'}), 400

    try:
        anotacao.contexto = contexto
        anotacao.tipo = tipo
        anotacao.data = data_valor
        sincronizar_anotacoes_legado(anotacao.pessoa)
        db.session.commit()
        return jsonify(_anotacao_para_json(anotacao))
    except Exception as e:
        db.session.rollback()
        print(f"[/anotacoes/{anotacao_id}] Erro ao editar anotação: {e}")
        return jsonify({'erro': 'Não foi possível salvar a edição.'}), 500


@app.route('/anotacoes/<int:anotacao_id>', methods=['DELETE'])
def excluir_anotacao(anotacao_id):
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401

    anotacao = Anotacao.query.get(anotacao_id)
    if not anotacao:
        return jsonify({'erro': 'Anotação não encontrada.'}), 404

    try:
        pessoa = anotacao.pessoa
        db.session.delete(anotacao)
        db.session.flush()
        sincronizar_anotacoes_legado(pessoa)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        print(f"[/anotacoes/{anotacao_id}] Erro ao excluir anotação: {e}")
        return jsonify({'erro': 'Não foi possível excluir.'}), 500


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        raw_password = request.form['password']
        password = hashlib.sha256(raw_password.encode()).hexdigest()

        user = Usuario.query.filter_by(username=username, password=password).first()
        if user:
            if user.ativo:
                session['usuario_logado'] = username
                session['is_admin'] = (user.tipo.lower() == 'admin')
                session['tipo'] = user.tipo.lower()  # 👈 ESSENCIAL: salva o tipo ('normal', 'moderador', 'admin')
                registrar_log('login', usuario=user)
                return redirect(url_for('menu_principal'))
            else:
                return render_template('login.html', erro='⛔ Aguarde liberação do administrador.')
        else:
            return render_template('login.html', erro='⚠️ Login inválido.')
    return render_template('login.html')

@app.route('/menu')
def menu_principal():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    tipo = session.get('tipo', 'normal')  # garante que sempre tenha um valor

    is_admin = tipo == 'admin'
    is_moderador = tipo == 'moderador'
    total = Pessoa.query.count()  # 👈 contagem de alvos

    return render_template(
        'menu.html',
        is_admin=is_admin,
        is_moderador=is_moderador,
        total=total
    )
@app.route('/mandado/extrair_pdf', methods=['POST'])
def mandado_extrair_pdf():
    if 'usuario_logado' not in session:
        return jsonify(ok=False, erro='Sessão expirada.'), 401

    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify(ok=False, erro='Nenhum arquivo enviado.'), 400
    if not arquivo.filename.lower().endswith('.pdf'):
        return jsonify(ok=False, erro='Envie um arquivo PDF.'), 400

    try:
        texto = _extrair_texto_pdf_mandado(arquivo)
    except Exception as e:
        return jsonify(ok=False, erro=f'Não consegui abrir esse PDF ({e}).'), 400

    if not texto or not texto.strip():
        return jsonify(
            ok=False,
            erro='Esse PDF parece ser uma imagem escaneada (sem texto pra copiar). '
                 'Preencha os campos manualmente.'
        ), 200

    dados = extrair_dados_mandado(texto)

    # Ajusta bairro/município pro MESMO formato usado nos <select> do
    # cadastro (limpar_texto = maiúsculo + sem acento), pra já vir
    # selecionado certo quando bater com a lista existente.
    dados['municipio_normalizado'] = limpar_texto(dados.get('municipio', ''))
    dados['bairro_normalizado'] = limpar_texto(dados.get('bairro', ''))

    return jsonify(ok=True, dados=dados)


@app.route('/mandado/encurtar_link', methods=['POST'])
def encurtar_link():
    if 'usuario_logado' not in session:
        return jsonify(ok=False, erro='Sessão expirada.'), 401

    corpo = request.get_json(silent=True) or {}
    url = (corpo.get('url') or '').strip()
    if not url:
        return jsonify(ok=False, erro='URL vazia.'), 400

    try:
        resp = requests.get('https://tinyurl.com/api-create.php', params={'url': url}, timeout=4)
        curto = resp.text.strip()
        if resp.ok and curto.startswith('http'):
            return jsonify(ok=True, url=curto)
    except Exception as e:
        print(f"[/mandado/encurtar_link] Erro ao encurtar link: {e}")

    # Se o encurtador falhar ou demorar, devolve o link original --
    # a mensagem nunca fica sem link por causa disso.
    return jsonify(ok=True, url=url)

def _normalizar_data_mandado(texto):
    """Converte a data do mandado (digitada como DD/MM/AAAA) para o formato
    ISO 'AAAA-MM-DD', que é o formato usado para exibir e filtrar em
    /mandados. Se o texto já estiver em ISO, mantém. Se não der pra
    reconhecer o formato, devolve o texto original sem quebrar o cadastro."""
    texto = (texto or '').strip()
    if not texto:
        return ''

    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', texto)
    if m:
        dia, mes, ano = m.groups()
        try:
            return datetime(int(ano), int(mes), int(dia)).strftime('%Y-%m-%d')
        except ValueError:
            return texto

    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', texto)
    if m:
        return texto

    return texto


@app.route('/mandado/importar', methods=['GET', 'POST'])
def mandado_importar():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        total = Pessoa.query.count()
        return render_template('importar_mandado.html', total=total)

    # ---- POST: salva Pessoa + Anotações + Mandado, tudo de uma vez ----
    nome = limpar_texto(request.form.get('nome', ''))
    vulgo = limpar_texto(request.form.get('vulgo', ''))
    genitora = limpar_texto(request.form.get('genitora', ''))
    faccao = limpar_texto(request.form.get('faccao', ''))
    bairro = limpar_texto(request.form.get('bairro', ''))
    municipio = limpar_texto(request.form.get('municipio', ''))
    octopus = limpar_texto(request.form.get('octopus', ''))
    octopusasint = limpar_texto(request.form.get('octopusasint', 'NAO'))
    comunidade = limpar_texto(request.form.get('comunidade', '')) or None
    anotacoes_json = request.form.get('anotacoes_json', '[]')

    if not nome:
        total = Pessoa.query.count()
        return render_template('importar_mandado.html', mensagem='⚠️ Informe o nome.', total=total)

    existente = Pessoa.query.filter_by(nome=nome).first()
    if existente:
        total = Pessoa.query.count()
        return render_template(
            'importar_mandado.html',
            mensagem='⚠️ Nome já cadastrado no SISCAD.',
            nome_existente=nome,
            total=total
        )

    usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()

    foto = request.files.get('foto')
    foto_url, foto_public_id = '', None
    if foto and foto.filename:
        foto_url, foto_public_id = upload_image_to_cloudinary(foto, nome)

    nova_pessoa = Pessoa(
        nome=nome, vulgo=vulgo, foto=foto_url, foto_public_id=foto_public_id,
        genitora=genitora, faccao=faccao, bairro=bairro, municipio=municipio,
        anotacoes='', octopus=octopus, octopusasint=octopusasint,
        comunidade=comunidade,
        usuario_id=usuario.id,
        fonetico_nome=calcular_fonetico(nome),
        fonetico_vulgo=calcular_fonetico(vulgo),
        forma_nome=calcular_forma_comparacao(nome),
        forma_vulgo=calcular_forma_comparacao(vulgo),
    )
    db.session.add(nova_pessoa)
    db.session.commit()
    registrar_log('cadastro_criado', pessoa=nova_pessoa, usuario=usuario, detalhes='Importado de PDF de mandado')

    try:
        itens = json.loads(anotacoes_json) if anotacoes_json else []
    except (ValueError, TypeError):
        itens = []
    if isinstance(itens, list) and itens:
        for item in itens:
            contexto = (item.get('contexto') or '').strip()
            if not contexto:
                continue
            tipo_item = (item.get('tipo') or '').strip()
            data_valor = None
            data_str = (item.get('data') or '').strip()
            if data_str:
                try:
                    data_valor = datetime.strptime(data_str, '%Y-%m-%d').date()
                except ValueError:
                    data_valor = None
            db.session.add(Anotacao(pessoa_id=nova_pessoa.id, data=data_valor, tipo=tipo_item, contexto=contexto))
        db.session.flush()
        sincronizar_anotacoes_legado(nova_pessoa)
        db.session.commit()

    # ---- Tabela de Mandados ----
    mandado_nome = request.form.get('mandado_nome', '').strip() or nome
    mandado_genitora = request.form.get('mandado_genitora', '').strip() or genitora
    mandado_data = _normalizar_data_mandado(request.form.get('mandado_data', ''))
    mandado_endereco = request.form.get('mandado_endereco', '').strip() or octopus
    mandado_tipificacao = request.form.get('mandado_tipificacao', '').strip()

    novo_mandado = Mandado(
        nome=mandado_nome,
        genitora=mandado_genitora,
        tipificacao=mandado_tipificacao,
        data=mandado_data,
        endereco=mandado_endereco,
        status='neutro',
    )
    db.session.add(novo_mandado)
    db.session.commit()
    registrar_log('mandado_importado', pessoa=nova_pessoa, usuario=usuario,
                  detalhes=f'Mandado nº {request.form.get("mandado_numero", "")}')

    total = Pessoa.query.count()
    return render_template('sucesso.html', mensagem="✅ Alvo cadastrado e mandado registrado com sucesso!")

@app.route('/mandados', methods=['GET'])
def mandados():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    # Busca todos os registros para exibir na tabela
    dados = Mandado.query.all()
    return render_template('mandados.html', dados=dados)




@app.route('/estatisticas')
def estatisticas():
    tipo = session.get('tipo', 'normal')  # garante que sempre tenha um valor

    if tipo not in ['admin', 'moderador']:
        return '⚠️ Acesso negado.'

    total = Pessoa.query.count()
    com_sim = Pessoa.query.filter(Pessoa.octopusasint.ilike('sim')).count()
    porcentagem = round((com_sim / total) * 100, 2) if total > 0 else 0

    return render_template(
        'estatisticas.html',
        total=total,
        com_sim=com_sim,
        porcentagem=porcentagem
    )

@app.route('/mandados/atualizar_status', methods=['POST'])
def atualizar_status():
    data = request.get_json()
    mandado_id = data.get('id')
    status = data.get('status')

    if status not in ['verde', 'vermelho', 'neutro']:
        return jsonify({'ok': False, 'erro': 'Status inválido'}), 400

    mandado = Mandado.query.get(mandado_id)
    if not mandado:
        return jsonify({'ok': False, 'erro': 'Mandado não encontrado'}), 404

    mandado.status = status
    db.session.commit()

    return jsonify({'ok': True})


@app.route('/mandados/excluir', methods=['POST'])
def excluir_mandado():
    if 'usuario_logado' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado.'}), 401

    data = request.get_json(silent=True) or {}
    mandado_id = data.get('id')

    mandado = Mandado.query.get(mandado_id)
    if not mandado:
        return jsonify({'ok': False, 'erro': 'Mandado não encontrado'}), 404

    try:
        db.session.delete(mandado)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        print(f"[/mandados/excluir] Erro ao excluir mandado: {e}")
        return jsonify({'ok': False, 'erro': 'Não foi possível excluir.'}), 500




# dashboard
@app.route("/dashboard")
def dashboard():
    # Consulta: contagem por bairro e facção
    registros = db.session.query(
        Pessoa.bairro,
        Pessoa.faccao,
        db.func.count(Pessoa.id)
    ).filter(Pessoa.bairro.isnot(None), Pessoa.faccao.isnot(None)) \
     .group_by(Pessoa.bairro, Pessoa.faccao).all()

    # Lista fixa de facções
    faccoes = ['CV', 'PCC', 'GDE', 'AQ', 'ADA', 'MASSA', 'SEM']

    # Inicializa estrutura: facção → bairro → contagem
    contagem_por_bairro = {}
    for bairro, faccao, count in registros:
        if faccao not in faccoes:
            continue
        if bairro not in contagem_por_bairro:
            contagem_por_bairro[bairro] = {f: 0 for f in faccoes}
        contagem_por_bairro[bairro][faccao] += count

    # Ordena bairros por total de cadastros (soma de todas facções)
    bairros_ordenados = sorted(
        contagem_por_bairro.keys(),
        key=lambda b: sum(contagem_por_bairro[b].values()),
        reverse=True
    )

    # Monta estrutura final: facção → lista de contagens por bairro
    faccao_por_bairro = {
        f: [contagem_por_bairro[b][f] for b in bairros_ordenados]
        for f in faccoes
    }

    dados = {
        "bairros": bairros_ordenados,
        "faccoes": faccao_por_bairro
    }

    return render_template("dashboard.html", dados=dados)

@app.route('/visualizar_todos', methods=['GET', 'POST'])
def visualizar_todos():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    filtro = request.form.get('filtro_octopusasint')

    query = Pessoa.query.with_entities(
        Pessoa.id,  # Adicionado!
        Pessoa.nome,
        Pessoa.vulgo,
        Pessoa.genitora,
        Pessoa.faccao,
        Pessoa.octopusasint
    )

    if filtro == 'SIM':
        query = query.filter(Pessoa.octopusasint.ilike('SIM'))
    elif filtro == 'NAO':
        query = query.filter(Pessoa.octopusasint.ilike('NAO'))
    elif filtro == 'None':
        query = query.filter(Pessoa.octopusasint.is_(None))

    dados = query.all()

    return render_template('visualizar_todos.html', dados=dados, filtro=filtro)

@app.route('/atualizar_octopusasint', methods=['POST'])
def atualizar_octopusasint():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id = request.form.get('id')
    novo_valor = request.form.get('novo_valor')

    pessoa = Pessoa.query.get(id)
    if pessoa:
        pessoa.octopusasint = novo_valor
        db.session.commit()
        flash('✅ Valor atualizado com sucesso!', 'sucesso')
    else:
        flash('❌ Pessoa não encontrada.', 'erro')

    return redirect(url_for('visualizar_todos'))

@app.route('/relatorio')
def relatorio():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    # Consulta: conta quantos alvos cada usuário cadastrou e ordena do maior para o menor
    relatorio = db.session.query(
        Usuario.username,
        db.func.count(Pessoa.id).label('quantidade')
    ).join(Pessoa).group_by(Usuario.username).order_by(db.func.count(Pessoa.id).desc()).all()

    return render_template('relatorio.html', relatorio=relatorio)

@app.route('/ver_cadastros/<username>')
def ver_cadastros_usuario(username):
    if not session.get('is_admin'):
        return '⚠️ Acesso negado.'

    usuario = Usuario.query.filter_by(username=username).first()
    if not usuario:
        return f'❌ Usuário "{username}" não encontrado.'

    cadastros = Pessoa.query.filter_by(usuario_id=usuario.id).all()
    return render_template('cadastros_usuario.html', cadastros=cadastros, username=username)

@app.route('/novos_cadastros', methods=['GET', 'POST'])
def novos_cadastros():
    if 'usuario_logado' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    dias = 5  # valor padrão
    if request.method == 'POST':
        try:
            dias = int(request.form.get('dias', 5))
        except ValueError:
            dias = 5

    limite_data = datetime.utcnow() - timedelta(days=dias)

    recentes = Pessoa.query.filter(Pessoa.data_criacao >= limite_data).order_by(Pessoa.data_criacao.desc()).all()
    total = len(recentes)

    return render_template('novos_cadastros.html', recentes=recentes, dias=dias, total=total)


# ✅ Rota de pesquisa por vínculo com normalização
@app.route('/pesquisa_vinculo', methods=['GET', 'POST'])
def pesquisa_vinculo():
    termos = []
    resultados = []

    if request.method == 'POST':
        termos = [normalizar(t.strip()) for t in [
            request.form.get('termo1'),
            request.form.get('termo2'),
            request.form.get('termo3')
        ] if t]

        todos = Pessoa.query.all()

        for pessoa in todos:
            campos = [
                normalizar(pessoa.nome),
                normalizar(pessoa.vulgo),
                normalizar(pessoa.genitora),
                normalizar(pessoa.anotacoes)
            ]
            texto_completo = ' '.join(campos)

            if all(termo in texto_completo for termo in termos):
                resultados.append(pessoa)

    return render_template('pesquisa_vinculo.html', resultados=resultados, termos=termos)

# ✅ Rota de pesquisa reversa
@app.route('/busca_reversa', methods=['GET', 'POST'])
def busca_reversa():
    resultados = []
    termos_frequentes = []
    sugestoes_vinculo = []

    if request.method == 'POST':
        texto_input = request.form.get('anotacao')
        if not texto_input:
            return "Anotação não informada", 400

        texto_normalizado = normalizar(texto_input)
        palavras = texto_normalizado.split()
        contagem = Counter(palavras)
        termos_frequentes = contagem.most_common(10)

        todos = Pessoa.query.all()
        anotacoes_banco = [normalizar(p.anotacoes or "") for p in todos]

        corpus = [texto_normalizado] + anotacoes_banco
        vectorizer = TfidfVectorizer(ngram_range=(1, 3)).fit_transform(corpus)
        sim_matrix = cosine_similarity(vectorizer[0:1], vectorizer[1:])
        sim_scores = sim_matrix[0]

        for i, pessoa in enumerate(todos):
            score = sim_scores[i]
            if score > 0.1:  # mais tolerante
                anotacao_destacada = destacar_termos(pessoa.anotacoes, palavras)
                resultados.append({
                    "pessoa": pessoa,
                    "score": round(score, 2),
                    "anotacao": anotacao_destacada
                })

                if pessoa.genitora and normalizar(pessoa.genitora) in texto_normalizado:
                    sugestoes_vinculo.append(f"Genitora em comum: {pessoa.genitora}")
                if pessoa.faccao and normalizar(pessoa.faccao) in texto_normalizado:
                    sugestoes_vinculo.append(f"Facção mencionada: {pessoa.faccao}")

        print("Texto recebido:", texto_input)
        print("Total de pessoas:", len(todos))
        print("Scores:", sim_scores)

    return render_template('busca_reversa.html',
                           resultados=resultados,
                           termos_frequentes=termos_frequentes,
                           sugestoes_vinculo=sugestoes_vinculo)
# ✅ Rota para dados do alvo (usada no modal)
@app.route('/comunidade/localizar', methods=['POST'])
def comunidade_localizar():
    if 'usuario_logado' not in session:
        return jsonify(ok=False, erro='Sessão expirada.'), 401
    dados_json = request.get_json(silent=True) or {}
    try:
        lat = float(request.form.get('lat') or dados_json.get('lat'))
        lon = float(request.form.get('lon') or dados_json.get('lon'))
    except (TypeError, ValueError):
        return jsonify(ok=False, erro='Coordenadas inválidas.'), 400

    comunidade = encontrar_comunidade(lat, lon)
    return jsonify(ok=True, comunidade=comunidade)

@app.route('/comunidade/lista')
def comunidade_lista():
    if 'usuario_logado' not in session:
        return jsonify([]), 401
    nomes = sorted(set(c['nome_normalizado'] for c in COMUNIDADES_AIS18))
    return jsonify([{'valor': nome, 'id': None} for nome in nomes])

@app.route('/dados_alvo/<int:id>')
def dados_alvo(id):
    pessoa = Pessoa.query.get_or_404(id)

    foto_url = pessoa.foto or ''

    # Extrair endereço da coluna octopus
    endereco = ''
    if pessoa.octopus:
        linhas = pessoa.octopus.split('\n')
        for linha in linhas:
            if 'ENDEREÇO:' in linha.upper():
                endereco = linha.split(':', 1)[-1].strip()

    return jsonify({
        "foto": foto_url,
        "nome": pessoa.nome,
        "vulgo": pessoa.vulgo,
        "genitora": pessoa.genitora,
        "faccao": pessoa.faccao,
        "bairro": pessoa.bairro or '',
        "endereco": endereco,
        "comunidade": pessoa.comunidade or '',
        "anotacoes": pessoa.anotacoes or ''
    })

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username'].strip().replace(" ", "")
        senha = request.form['password']
        confirmar = request.form['confirmar']

        if senha != confirmar:
            return render_template('cadastro.html', erro='⚠️ As senhas não coincidem.')

        password_hash = hashlib.sha256(senha.encode()).hexdigest()

        if Usuario.query.filter_by(username=username).first():
            return render_template('cadastro.html', erro='⚠️ Usuário já existe.')

        novo_usuario = Usuario(username=username, password=password_hash)
        db.session.add(novo_usuario)
        db.session.commit()

        return render_template('login.html', sucesso='✅ Cadastro realizado com sucesso! Espere a liberação do administrador.')
    
    return render_template('cadastro.html')
@app.route('/verificar_usuario')
def verificar_usuario():
    nome = request.args.get('nome', '').strip().upper().replace(" ", "")
    existe = Usuario.query.filter_by(username=nome).first()

    if request.args.get('fmt') == 'json':
        return jsonify({
            "status": "existente" if existe else "disponivel",
            "id": existe.id if existe else None
        })

    return "existente" if existe else "disponivel"

@app.route('/cadastro_alvo', methods=['GET', 'POST'])
def cadastro_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = limpar_texto(request.form['nome'])
        vulgo = limpar_texto(request.form['vulgo'])
        genitora = limpar_texto(request.form['genitora'])
        faccao = limpar_texto(request.form['faccao'])  # ✅ Novo campo
        bairro = limpar_texto(request.form['bairro'])
        municipio = limpar_texto(request.form['municipio'])
        anotacoes_json = request.form.get('anotacoes_json', '[]')
        octopus = limpar_texto(request.form['octopus'])
        octopusasint = limpar_texto(request.form['octopusasint'])  # ✅ Novo campo
        comunidade = limpar_texto(request.form.get('comunidade', '')) or None
        foto = request.files['foto']
        foto_url = ''
        foto_public_id = None

        if foto and foto.filename:
            foto_url, foto_public_id = upload_image_to_cloudinary(foto, nome)

        existente = Pessoa.query.filter_by(nome=nome).first()
        if existente:
            total = Pessoa.query.count()
            # Envia o nome já existente para o template
            return render_template(
                'cadastro_alvo.html',
                mensagem="⚠️ Nome já cadastrado.",
                nome_existente=nome,
                total=total
            )
        # ✅ Busca o usuário logado
        usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()

        nova_pessoa = Pessoa(
    nome=nome, vulgo=vulgo, foto=foto_url,
    foto_public_id=foto_public_id,
    genitora=genitora, faccao=faccao,  # ✅ Aqui
    bairro=bairro, municipio=municipio,
    anotacoes='', octopus=octopus,
    octopusasint=octopusasint,  # ✅ Aqui
    comunidade=comunidade,
    usuario_id=usuario.id, # 👈 vincula ao usuário
    fonetico_nome=calcular_fonetico(nome),
    fonetico_vulgo=calcular_fonetico(vulgo),
    forma_nome=calcular_forma_comparacao(nome),
    forma_vulgo=calcular_forma_comparacao(vulgo),
)
        db.session.add(nova_pessoa)
        db.session.commit()
        registrar_log('cadastro_criado', pessoa=nova_pessoa, usuario=usuario)

        # Anotações estruturadas (Data + Tipo + Contexto) montadas no modal
        # "+" da tela de cadastro. Só dá pra gravar depois daqui porque só
        # agora a pessoa tem id (chegam como JSON no campo oculto).
        try:
            itens = json.loads(anotacoes_json) if anotacoes_json else []
        except (ValueError, TypeError):
            itens = []
        if isinstance(itens, list) and itens:
            for item in itens:
                contexto = (item.get('contexto') or '').strip()
                if not contexto:
                    continue
                tipo_item = (item.get('tipo') or '').strip()
                data_valor = None
                data_str = (item.get('data') or '').strip()
                if data_str:
                    try:
                        data_valor = datetime.strptime(data_str, '%Y-%m-%d').date()
                    except ValueError:
                        data_valor = None
                db.session.add(Anotacao(
                    pessoa_id=nova_pessoa.id, data=data_valor,
                    tipo=tipo_item, contexto=contexto
                ))
            db.session.flush()
            sincronizar_anotacoes_legado(nova_pessoa)
            db.session.commit()

        total = Pessoa.query.count()
        return render_template('sucesso.html', mensagem="✅ Alvo cadastrado com sucesso!")
    
    total = Pessoa.query.count()
    return render_template('cadastro_alvo.html', total=total)
# pesquisar alvo
RESULTADOS_POR_PAGINA = 20

def _buscar_alvos_query(nome, vulgo, bairro, municipio, nome_parecido=False, fonetica=False, comunidade=''):
    query = Pessoa.query

    # Campo "Nome" -- busca só na coluna nome (+ variações, se marcadas).
    if nome:
        condicao_nome = Pessoa.nome.ilike(f'%{nome}%')
        if nome_parecido:
            condicao_parecido = _condicao_nome_parecido(nome, Pessoa.forma_nome)
            if condicao_parecido is not None:
                condicao_nome = condicao_nome | condicao_parecido
        if fonetica:
            condicao_fonetica = _condicao_fonetica(nome, Pessoa.fonetico_nome)
            if condicao_fonetica is not None:
                condicao_nome = condicao_nome | condicao_fonetica
        query = query.filter(condicao_nome)

    # Campo "Vulgo" -- busca só na coluna vulgo (+ variações, se marcadas).
    # Independente do campo Nome: os dois juntos filtram em AND.
    if vulgo:
        condicao_vulgo = Pessoa.vulgo.ilike(f'%{vulgo}%')
        if nome_parecido:
            condicao_parecido_v = _condicao_nome_parecido(vulgo, Pessoa.forma_vulgo)
            if condicao_parecido_v is not None:
                condicao_vulgo = condicao_vulgo | condicao_parecido_v
        if fonetica:
            condicao_fonetica_v = _condicao_fonetica(vulgo, Pessoa.fonetico_vulgo)
            if condicao_fonetica_v is not None:
                condicao_vulgo = condicao_vulgo | condicao_fonetica_v
        query = query.filter(condicao_vulgo)

    if municipio:
        query = query.filter(Pessoa.municipio.ilike(municipio))
    if bairro:
        query = query.filter(Pessoa.bairro.ilike(bairro))
    if comunidade:
        query = query.filter(Pessoa.comunidade.ilike(comunidade))
    return query.order_by(Pessoa.nome)


def _buscar_alvos_paginado(nome, vulgo, bairro, municipio, pagina, nome_parecido=False, fonetica=False, comunidade=''):
    query = _buscar_alvos_query(nome, vulgo, bairro, municipio, nome_parecido, fonetica, comunidade)
    pagina = max(1, pagina)
    paginacao = query.paginate(page=pagina, per_page=RESULTADOS_POR_PAGINA, error_out=False)
    if paginacao.pages and pagina > paginacao.pages:
        # página pedida (ex: link antigo, ou editada na URL) não existe mais -> mostra a última
        paginacao = query.paginate(page=paginacao.pages, per_page=RESULTADOS_POR_PAGINA, error_out=False)
    return paginacao.items, paginacao.pages or 1, paginacao.page


@app.route('/pesquisar_alvo', methods=['GET', 'POST'])
def pesquisar_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    termo = ''
    vulgo_busca = ''
    bairro = ''
    municipio = ''
    comunidade = ''
    resultados = []
    alvo = None
    mensagem = ''
    pagina = 1
    total_paginas = 1
    nome_parecido = False
    fonetica = False

    if request.method == 'POST':
        termo = limpar_texto(request.form.get('termo', ''))
        vulgo_busca = limpar_texto(request.form.get('vulgo_busca', ''))
        bairro = limpar_texto(request.form.get('bairro', ''))
        municipio = limpar_texto(request.form.get('municipio', ''))
        comunidade = limpar_texto(request.form.get('comunidade', ''))
        nome_parecido = request.form.get('nome_parecido') == '1'
        fonetica = request.form.get('fonetica') == '1'

        resultados, total_paginas, pagina = _buscar_alvos_paginado(termo, vulgo_busca, bairro, municipio, 1, nome_parecido, fonetica, comunidade)

        if not resultados:
            mensagem = "Não há resultados para essa busca."

    # Ao clicar num resultado ou trocar de página (GET com termo), refaz a
    # mesma busca a partir dos termos que vieram junto na URL, para a lista
    # continuar disponível ao lado do alvo selecionado (e o botão
    # "Voltar aos resultados" e a paginação funcionarem).
    elif 'termo' in request.args or 'vulgo_busca' in request.args:
        termo = limpar_texto(request.args.get('termo', ''))
        vulgo_busca = limpar_texto(request.args.get('vulgo_busca', ''))
        bairro = limpar_texto(request.args.get('bairro', ''))
        municipio = limpar_texto(request.args.get('municipio', ''))
        comunidade = limpar_texto(request.args.get('comunidade', ''))
        nome_parecido = request.args.get('nome_parecido') == '1'
        fonetica = request.args.get('fonetica') == '1'
        pagina_solicitada = request.args.get('pagina', 1, type=int) or 1
        resultados, total_paginas, pagina = _buscar_alvos_paginado(termo, vulgo_busca, bairro, municipio, pagina_solicitada, nome_parecido, fonetica, comunidade)

    if request.args.get('id'):
        alvo = Pessoa.query.filter_by(id=request.args.get('id')).first()

    fotos_antigas_count = 0
    if alvo:
        fotos_antigas_count = FotoHistorico.query.filter_by(pessoa_id=alvo.id).count()

    is_admin = session.get('is_admin', False)
    return render_template(
        'pesquisar_alvo.html',
        termo=termo,
        vulgo_busca=vulgo_busca,
        bairro=bairro,
        municipio=municipio,
        comunidade=comunidade,
        resultados=resultados,
        alvo=alvo,
        is_admin=is_admin,
        fotos_antigas_count=fotos_antigas_count,
        mensagem=mensagem,
        pagina=pagina,
        total_paginas=total_paginas,
        nome_parecido=nome_parecido,
        fonetica=fonetica,
    )


@app.route('/exportar_alvo/<int:id>')
def exportar_alvo(id):
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    alvo = Pessoa.query.get(id)
    if not alvo:
        return '❌ Alvo não encontrado.'

    html = render_template(
        'exportar_alvo.html',
        alvo=alvo,
        gerado_em=datetime.now().strftime('%d/%m/%Y %H:%M'),
    )

    # Por padrão só EXIBE a página. O download em arquivo só acontece se
    # vier ?baixar=1 (pelo botão "Baixar" dentro da própria página exportada).
    if request.args.get('baixar'):
        nome_arquivo = re.sub(r'[^A-Za-z0-9]+', '_', alvo.nome or 'alvo').strip('_').lower() or 'alvo'
        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename="alvo_{nome_arquivo}.html"'},
        )

    return html


# pesquisa em lote
@app.route('/pesquisa_lotes', methods=['GET', 'POST'])
def pesquisa_lotes():
    resultados = []

    if request.method == 'POST':
        municipio = request.form.get('municipio', '').strip()
        bairro = request.form.get('bairro', '').strip()
        faccao = request.form.get('facção', '').strip()
        crime = request.form.get('crime', '').strip()
        comunidade = request.form.get('comunidade', '').strip()

        crime_normalizado = normalizar(crime)

        query = Pessoa.query

        if municipio:
            query = query.filter(Pessoa.municipio == municipio.upper())
        if bairro:
            query = query.filter(Pessoa.bairro == bairro.upper())
        if faccao:
            query = query.filter(Pessoa.faccao == faccao.upper())
        if comunidade:
            query = query.filter(Pessoa.comunidade == comunidade.upper())

        todos = query.all()

        for pessoa in todos:
            anotacao_normalizada = normalizar(pessoa.anotacoes or "")
            if crime and crime_normalizado not in anotacao_normalizada:
                continue
            resultados.append(pessoa)

    return render_template('pesquisa_lote.html', resultados=resultados)

@app.route('/editar_alvo', methods=['POST'])
def editar_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id_alvo = request.form['id']
    alvo = Pessoa.query.get(id_alvo)
    if not alvo:
        return '❌ Alvo não encontrado.'

    # Guarda os valores antigos dos campos simples só pra saber, no
    # histórico, o que realmente mudou nessa edição (sem guardar o
    # conteúdo em si, só o nome dos campos).
    campos_monitorados = ['nome', 'vulgo', 'genitora', 'faccao', 'bairro', 'municipio', 'octopus', 'octopusasint', 'comunidade']
    valores_antigos = {campo: getattr(alvo, campo) for campo in campos_monitorados}

    # Atualiza os dados do formulário
    alvo.nome = limpar_texto(request.form['nome'])
    alvo.vulgo = limpar_texto(request.form['vulgo'])
    alvo.fonetico_nome = calcular_fonetico(alvo.nome)
    alvo.fonetico_vulgo = calcular_fonetico(alvo.vulgo)
    alvo.forma_nome = calcular_forma_comparacao(alvo.nome)
    alvo.forma_vulgo = calcular_forma_comparacao(alvo.vulgo)
    alvo.genitora = limpar_texto(request.form['genitora'])
    alvo.faccao = limpar_texto(request.form['faccao'])  # ✅ Atualização
    alvo.bairro = limpar_texto(request.form['bairro'])
    alvo.municipio = limpar_texto(request.form['municipio'])
    # Anotações não vêm mais deste formulário -- cada uma é criada/editada/
    # excluída na hora, via /anotacoes/<id>, pelo modal de "+" (isso também
    # elimina o bug antigo em que reabrir "Alterar dados" grudava a data de
    # hoje no topo do texto toda vez, mesmo sem mexer nas anotações).
    alvo.octopus = limpar_texto(request.form['octopus'])
    alvo.octopusasint = limpar_texto(request.form['octopusasint'])  # ✅ Atualização
    alvo.comunidade = limpar_texto(request.form.get('comunidade', '')) or None
    
    # Atualiza a foto se enviada -- antes de trocar, guarda a foto antiga no
    # histórico (pra não perder o público_id e poder excluí-la do Cloudinary
    # depois, em vez de deixá-la órfã e ocupando espaço lá pra sempre)
    nova_foto = request.files.get('nova_foto')
    if nova_foto and nova_foto.filename:
        if alvo.foto:
            public_id_antigo = alvo.foto_public_id or extrair_public_id_cloudinary(alvo.foto)
            if public_id_antigo:
                db.session.add(FotoHistorico(
                    pessoa_id=alvo.id,
                    url=alvo.foto,
                    public_id=public_id_antigo,
                ))
        foto_url, foto_public_id = upload_image_to_cloudinary(nova_foto, alvo.nome)
        alvo.foto = foto_url  # Atualiza direto no objeto
        alvo.foto_public_id = foto_public_id

    campos_alterados = [c for c in campos_monitorados if valores_antigos[c] != getattr(alvo, c)]
    if nova_foto and nova_foto.filename:
        campos_alterados.append('foto')

    db.session.commit()
    registrar_log(
        'cadastro_editado',
        pessoa=alvo,
        detalhes=('Campos alterados: ' + ', '.join(campos_alterados)) if campos_alterados else 'Sem alterações detectadas',
    )
    flash('✅ Alterações salvas com sucesso!', 'sucesso')
    return redirect(url_for(
        'pesquisar_alvo',
        id=id_alvo,
        termo=request.form.get('termo_busca', ''),
        bairro=request.form.get('bairro_busca', ''),
        municipio=request.form.get('municipio_busca', ''),
    ))

@app.route('/excluir_alvo', methods=['POST'])
def excluir_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id_alvo = request.form['id']
    alvo = Pessoa.query.get(id_alvo)

    if alvo:
        # Ao excluir o cadastro inteiro, aproveita e limpa também a foto
        # atual e todo o histórico dela no Cloudinary -- senão ficam órfãs
        # lá, ocupando espaço sem servir pra nada.
        public_id_atual = alvo.foto_public_id or extrair_public_id_cloudinary(alvo.foto)
        if public_id_atual:
            try:
                cloudinary.uploader.destroy(public_id_atual)
            except Exception as e:
                print(f"[excluir_alvo] Erro ao excluir foto atual do Cloudinary: {e}")

        for antiga in FotoHistorico.query.filter_by(pessoa_id=id_alvo).all():
            try:
                cloudinary.uploader.destroy(antiga.public_id)
            except Exception as e:
                print(f"[excluir_alvo] Erro ao excluir foto antiga do Cloudinary: {e}")

        FotoHistorico.query.filter_by(pessoa_id=id_alvo).delete()

    Anotacao.query.filter_by(pessoa_id=id_alvo).delete()
    Pessoa.query.filter_by(id=id_alvo).delete()
    db.session.commit()
    return redirect(url_for('pesquisar_alvo'))


@app.route('/fotos_antigas/<int:pessoa_id>')
def listar_fotos_antigas(pessoa_id):
    """Lista as fotos antigas (já substituídas) de um alvo, pro modal do
    botão '+📷' na tela de pesquisa."""
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado.'}), 401

    fotos = (FotoHistorico.query
             .filter_by(pessoa_id=pessoa_id)
             .order_by(FotoHistorico.criado_em.desc())
             .all())
    return jsonify({
        'fotos': [{'id': f.id, 'url': f.url} for f in fotos]
    })


@app.route('/fotos_antigas/<int:foto_id>/excluir', methods=['POST'])
def excluir_foto_antiga(foto_id):
    """Exclui uma foto antiga tanto do banco quanto do Cloudinary.
    Só o perfil admin pode fazer isso.

    Se por algum motivo a foto excluída for a mesma que está valendo como
    foto atual do perfil (Pessoa.foto), promove a próxima mais recente do
    histórico pra ocupar o lugar dela -- em vez de deixar o cadastro
    apontando para uma imagem que não existe mais."""
    if not session.get('is_admin'):
        return jsonify({'erro': 'Apenas administradores podem excluir fotos.'}), 403

    foto = FotoHistorico.query.get(foto_id)
    if not foto:
        return jsonify({'erro': 'Foto não encontrada.'}), 404

    try:
        cloudinary.uploader.destroy(foto.public_id)
    except Exception as e:
        print(f"[excluir_foto_antiga] Erro ao excluir do Cloudinary: {e}")
        return jsonify({'erro': 'Não foi possível excluir a foto no Cloudinary.'}), 500

    pessoa_id = foto.pessoa_id
    pessoa = Pessoa.query.get(pessoa_id)
    era_foto_atual = bool(pessoa and pessoa.foto and pessoa.foto == foto.url)

    db.session.delete(foto)
    db.session.flush()  # a foto excluída já não deve contar na busca abaixo

    nova_foto_url = None
    if era_foto_atual and pessoa:
        proxima = (FotoHistorico.query
                   .filter_by(pessoa_id=pessoa_id)
                   .order_by(FotoHistorico.criado_em.desc())
                   .first())
        if proxima:
            pessoa.foto = proxima.url
            pessoa.foto_public_id = proxima.public_id
            nova_foto_url = proxima.url
            db.session.delete(proxima)  # agora é a atual, não faz mais parte do histórico
        else:
            pessoa.foto = None
            pessoa.foto_public_id = None
            nova_foto_url = ''

    db.session.commit()

    restantes = FotoHistorico.query.filter_by(pessoa_id=pessoa_id).count()
    return jsonify({
        'ok': True,
        'restantes': restantes,
        'foto_atual_alterada': era_foto_atual,
        'nova_foto_url': nova_foto_url or '',
    })

@app.route('/gerenciar_usuarios', methods=['GET', 'POST'])
def gerenciar_usuarios():
    if not session.get('is_admin'):
        return '⚠️ Acesso negado.'

    if request.method == 'POST':
        user_id = request.form.get('id')

        if 'nova_senha' in request.form:
            nova_senha = request.form['nova_senha']
            hash = hashlib.sha256(nova_senha.encode()).hexdigest()
            Usuario.query.filter_by(id=user_id).update({'password': hash})
            db.session.commit()

        elif 'excluir_id' in request.form:
            excluir_id = request.form['excluir_id']
            Usuario.query.filter_by(id=excluir_id).delete()
            db.session.commit()

        elif 'novo_tipo' in request.form:
            novo_tipo = request.form['novo_tipo']
            if novo_tipo in ['admin', 'normal', 'moderador']:
                Usuario.query.filter_by(id=user_id).update({'tipo': novo_tipo})
                db.session.commit()

        elif 'ver_historico_id' in request.form:
            # Só a SAMARA pode conceder/revogar acesso ao histórico de
            # atividades para outros admins — mesmo sendo admin, ninguém
            # mais mexe nisso.
            if session.get('usuario_logado', '').strip().upper() == 'SAMARA':
                alvo_id = request.form['ver_historico_id']
                valor = request.form.get('ver_historico_valor') == '1'
                Usuario.query.filter_by(id=alvo_id).update({'pode_ver_historico': valor})
                db.session.commit()

    usuarios = Usuario.query.all()
    pendentes = Usuario.query.filter_by(ativo=False).all()
    eh_samara = session.get('usuario_logado', '').strip().upper() == 'SAMARA'
    return render_template('gerenciar_usuarios.html', usuarios=usuarios, pendentes=pendentes, eh_samara=eh_samara)

@app.route('/historico')
def historico():
    if not pode_ver_historico():
        return '⚠️ Acesso negado.'

    pagina = request.args.get('pagina', 1, type=int)
    paginacao = AtividadeLog.query.order_by(AtividadeLog.criado_em.desc()) \
        .paginate(page=max(1, pagina), per_page=50, error_out=False)
    return render_template('historico.html', paginacao=paginacao)

@app.route('/autorizar/<int:id>')
def autorizar(id):
    if not session.get('is_admin'):
        return '⚠️ Acesso negado.'
    Usuario.query.filter_by(id=id).update({'ativo': True})
    db.session.commit()
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/api/minha_conta')
def api_minha_conta():
    if 'usuario_logado' not in session:
        return jsonify(ok=False, erro='Sessão expirada.'), 401
    usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()
    if not usuario:
        return jsonify(ok=False, erro='Usuário não encontrado.'), 404
    return jsonify(ok=True, username=usuario.username, email=usuario.email or '')

@app.route('/conta/atualizar', methods=['POST'])
def conta_atualizar():
    if 'usuario_logado' not in session:
        return jsonify(ok=False, erro='Sessão expirada. Faça login novamente.'), 401

    usuario = Usuario.query.filter_by(username=session['usuario_logado']).first()
    if not usuario:
        return jsonify(ok=False, erro='Usuário não encontrado.'), 404

    senha_atual = request.form.get('senha_atual', '')
    if not senha_atual or hashlib.sha256(senha_atual.encode()).hexdigest() != usuario.password:
        return jsonify(ok=False, erro='Senha atual incorreta.'), 400

    novo_email = request.form.get('novo_email', '').strip()
    nova_senha = request.form.get('nova_senha', '')
    confirmar_senha = request.form.get('confirmar_senha', '')

    mudou_algo = False

    if novo_email:
        usuario.email = novo_email
        mudou_algo = True

    if nova_senha or confirmar_senha:
        if nova_senha != confirmar_senha:
            return jsonify(ok=False, erro='As senhas novas não coincidem.'), 400
        if len(nova_senha) < 6:
            return jsonify(ok=False, erro='A nova senha deve ter pelo menos 6 caracteres.'), 400
        usuario.password = hashlib.sha256(nova_senha.encode()).hexdigest()
        mudou_algo = True

    if not mudou_algo:
        return jsonify(ok=False, erro='Nada para atualizar.'), 400

    db.session.commit()
    return jsonify(ok=True, email=usuario.email or '')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/verificar_nome')
def verificar_nome():
    nome = limpar_texto(request.args.get('nome', ''))
    existe = Pessoa.query.filter_by(nome=nome).first()

    # Resposta JSON opcional, preservando o comportamento antigo
    if request.args.get('fmt') == 'json':
        return jsonify({
            "status": "existente" if existe else "disponivel",
            "id": existe.id if existe else None
        })

    return "existente" if existe else "disponivel"

def mostrar_ip_local():
    try:
        hostname = socket.gethostname()
        ip_local = socket.gethostbyname(hostname)
        print(f"\n🌐 Site disponível em: http://{ip_local}:5000 (rede local)\n")
    except Exception as e:
        print("⚠️ IP local não detectado:", e)

if __name__ == '__main__':
    print(f"\n🔗 Banco conectado: {app.config['SQLALCHEMY_DATABASE_URI']}\n")
    mostrar_ip_local()
    app.run(debug=True, host='0.0.0.0', port=5000)