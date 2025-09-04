from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from markupsafe import Markup
import time
import numpy as np
import cv2
import hashlib, os, unicodedata, socket
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import re


app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura_123'

# 🔗 Conexão com banco PostgreSQL no Neon
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql://neondb_owner:npg_fCVgz9kF0RBD@ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech/neondb'
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

def upload_image_to_cloudinary(file_storage, nome_alvo):
    result = cloudinary.uploader.upload(
        file_storage,
        public_id=f"{nome_alvo}_{int(time.time())}",
        overwrite=False
    )
    return result['secure_url']

# ✅ detectar rosto
def detectar_rosto(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    if len(faces) == 0:
        return None

    x, y, w, h = faces[0]
    rosto = img[y:y+h, x:x+w]
    return rosto

def comparar_histogramas(img1, img2):
    hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8], [0, 256]*3)
    hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8], [0, 256]*3)
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return score
# ✅ ler imagem
def ler_imagem(file_storage):
    file_bytes = np.frombuffer(file_storage.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return img

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
    cadastros = db.relationship('Pessoa', backref='usuario', lazy=True)

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
    octopus = db.Column(db.String)
    faccao = db.Column(db.String(100), nullable=True)
    octopusasint = db.Column(db.String(3))  # ✅ Novo campo: "Sim" ou "Não"
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))  # 👈 novo campo
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow) # data da criação

class Cadastro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(255))  # ou qualquer outro campo
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

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
@app.route('/dados_alvo/<int:id>')
def dados_alvo(id):
    pessoa = Pessoa.query.get_or_404(id)

    # Se a foto estiver salva localmente
    if pessoa.foto and not pessoa.foto.startswith('http'):
        
        url_for('static', filename='IMAGEM/' + pessoa.foto)
    else:
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
        anotacoes = request.form['anotacoes']
        octopus = limpar_texto(request.form['octopus'])
        octopusasint = limpar_texto(request.form['octopusasint'])  # ✅ Novo campo
        foto = request.files['foto']
        foto_url = ''

        if foto and foto.filename:
            foto_url = upload_image_to_cloudinary(foto, nome)

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
    genitora=genitora, faccao=faccao,  # ✅ Aqui
    bairro=bairro, municipio=municipio,
    anotacoes=anotacoes, octopus=octopus,
    octopusasint=octopusasint,  # ✅ Aqui
    usuario_id=usuario.id # 👈 vincula ao usuário
)
        db.session.add(nova_pessoa)
        db.session.commit()
        total = Pessoa.query.count()
        return render_template('sucesso.html', mensagem="✅ Alvo cadastrado com sucesso!")
    
    total = Pessoa.query.count()
    return render_template('cadastro_alvo.html', total=total)
# pesquisar alvo
@app.route('/pesquisar_alvo', methods=['GET', 'POST'])
def pesquisar_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    termo = ''
    bairro = ''
    resultados = []
    alvo = None
    mensagem = ''
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    if request.method == 'POST':
        termo = limpar_texto(request.form['termo'])
        bairro = limpar_texto(request.form['bairro'])

        query = Pessoa.query.filter(
            (Pessoa.nome.ilike(f'%{termo}%')) | (Pessoa.vulgo.ilike(f'%{termo}%'))
        )
        if bairro:
            query = query.filter(Pessoa.bairro.ilike(f'%{bairro}%'))

        resultados = query.all()

        if not resultados:
            mensagem = "Não há resultados para este nome."

    if request.args.get('id'):
        alvo = Pessoa.query.filter_by(id=request.args.get('id')).first()

    is_admin = session.get('is_admin', False)
    return render_template(
         'pesquisar_alvo.html',
    termo=termo,
    bairro=bairro,
    resultados=resultados,
    alvo=alvo,
    is_admin=is_admin,
    mensagem=mensagem,
    now=now  # 👈 envia a data atual para o template
)

# pesquisa em lote
@app.route('/pesquisa_lotes', methods=['GET', 'POST'])
def pesquisa_lotes():
    resultados = []

    if request.method == 'POST':
        municipio = request.form.get('municipio', '').strip()
        bairro = request.form.get('bairro', '').strip()
        faccao = request.form.get('facção', '').strip()
        crime = request.form.get('crime', '').strip()

        crime_normalizado = normalizar(crime)

        query = Pessoa.query

        if municipio:
            query = query.filter(Pessoa.municipio == municipio.upper())
        if bairro:
            query = query.filter(Pessoa.bairro == bairro.upper())
        if faccao:
            query = query.filter(Pessoa.faccao == faccao.upper())

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

    # Atualiza os dados do formulário
    alvo.nome = limpar_texto(request.form['nome'])
    alvo.vulgo = limpar_texto(request.form['vulgo'])
    alvo.genitora = limpar_texto(request.form['genitora'])
    alvo.faccao = limpar_texto(request.form['faccao'])  # ✅ Atualização
    alvo.bairro = limpar_texto(request.form['bairro'])
    alvo.municipio = limpar_texto(request.form['municipio'])
    alvo.anotacoes = request.form['anotacoes']
    alvo.octopus = limpar_texto(request.form['octopus'])
    alvo.octopusasint = limpar_texto(request.form['octopusasint'])  # ✅ Atualização
    
    # Atualiza a foto se enviada
    nova_foto = request.files.get('nova_foto')
    if nova_foto and nova_foto.filename:
        foto_url = upload_image_to_cloudinary(nova_foto, alvo.nome)
        alvo.foto = foto_url  # Atualiza direto no objeto

    db.session.commit()
    flash('✅ Alterações salvas com sucesso!', 'sucesso')
    return redirect(url_for('pesquisar_alvo', id=id_alvo))

@app.route('/excluir_alvo', methods=['POST'])
def excluir_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id_alvo = request.form['id']
    Pessoa.query.filter_by(id=id_alvo).delete()
    db.session.commit()
    return redirect(url_for('pesquisar_alvo'))

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

    usuarios = Usuario.query.all()
    pendentes = Usuario.query.filter_by(ativo=False).all()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios, pendentes=pendentes)

@app.route('/autorizar/<int:id>')
def autorizar(id):
    if not session.get('is_admin'):
        return '⚠️ Acesso negado.'
    Usuario.query.filter_by(id=id).update({'ativo': True})
    db.session.commit()
    return redirect(url_for('gerenciar_usuarios'))

# comparar fotos
@app.route("/comparador")
def comparador():
    return render_template("comparador.html")

@app.route("/comparar", methods=["POST"])
def comparar():
    try:
        foto1 = request.files.get("foto1")
        foto2 = request.files.get("foto2")

        if not foto1 or not foto2:
            return jsonify({"erro": "Envie duas fotos"}), 400

        img1 = ler_imagem(foto1)
        img2 = ler_imagem(foto2)

        if img1 is None or img2 is None:
            return jsonify({"erro": "Erro ao ler as imagens"}), 400

        rosto1 = detectar_rosto(img1)
        rosto2 = detectar_rosto(img2)

        if rosto1 is None or rosto2 is None:
            return jsonify({"erro": "Rosto não detectado em uma das imagens"}), 400

        score = comparar_histogramas(rosto1, rosto2)
        porcentagem = round(score * 100, 2)

        return jsonify({
            "porcentagem": porcentagem,
            "match": porcentagem > 70  # ajuste o limiar como quiser
        })

    except Exception as e:
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

  
      
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

