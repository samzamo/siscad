from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import hashlib, os, unicodedata, socket
import cloudinary
import cloudinary.uploader
import cloudinary.api

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

def limpar_texto(texto):
    texto = texto.upper()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

def upload_image_to_cloudinary(file_storage):
    result = cloudinary.uploader.upload(file_storage)
    return result['secure_url']

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
    is_admin = session.get('is_admin', False)
    total = Pessoa.query.count()  # 👈 Adiciona a contagem de alvos
    return render_template('menu.html', is_admin=is_admin, total=total)

@app.route('/estatisticas')
def estatisticas():
    if not session.get('is_admin'):
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
            foto_url = upload_image_to_cloudinary(foto)

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
        foto_url = upload_image_to_cloudinary(nova_foto)
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
            if novo_tipo in ['admin', 'normal']:
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

