from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import hashlib, os, unicodedata, socket

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura_123'

# ✅ Conexão com banco PostgreSQL no Neon (corrigida e otimizada)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_fCVgz9kF0RBD@ep-polished-cherry-af5c7u6k-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require&connect_timeout=10'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/IMAGEM'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
db = SQLAlchemy(app)

def limpar_texto(texto):
    texto = texto.upper()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=False)
    tipo = db.Column(db.String(10), default='normal')

class Pessoa(db.Model):
    __tablename__ = 'pessoa'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String, nullable=False)
    vulgo = db.Column(db.String)
    genitora = db.Column(db.String)
    bairro = db.Column(db.String)
    municipio = db.Column(db.String)
    anotacoes = db.Column(db.Text)
    foto = db.Column(db.String)
    octopus = db.Column(db.String)

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
    return render_template('menu.html', is_admin=is_admin)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username']
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

        # ✅ Redireciona para login com mensagem de sucesso
        return render_template('login.html', sucesso='✅ Cadastro realizado com sucesso! Espere a liberação do administrador.')
    
    return render_template('cadastro.html')


@app.route('/cadastro_alvo', methods=['GET', 'POST'])
def cadastro_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = limpar_texto(request.form['nome'])
        vulgo = limpar_texto(request.form['vulgo'])
        genitora = limpar_texto(request.form['genitora'])
        bairro = limpar_texto(request.form['bairro'])
        municipio = limpar_texto(request.form['municipio'])
        anotacoes = request.form['anotacoes']
        octopus = limpar_texto(request.form['octopus'])
        foto = request.files['foto']
        foto_nome = ''
        if foto and foto.filename:
            foto_nome = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_nome))

        existente = Pessoa.query.filter_by(nome=nome).first()
        if existente:
            total = Pessoa.query.count()
            return render_template('cadastro_alvo.html', mensagem="⚠️ Nome já cadastrado.", total=total)

        nova_pessoa = Pessoa(
            nome=nome, vulgo=vulgo, foto=foto_nome,
            genitora=genitora, bairro=bairro,
            anotacoes=anotacoes, octopus=octopus,
            municipio=municipio
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

    if request.method == 'POST':
        termo = limpar_texto(request.form['termo'])
        bairro = limpar_texto(request.form['bairro'])
        query = Pessoa.query.filter(
            (Pessoa.nome.ilike(f'%{termo}%')) | (Pessoa.vulgo.ilike(f'%{termo}%'))
        )
        if bairro:
            query = query.filter(Pessoa.bairro.ilike(f'%{bairro}%'))
        resultados = query.all()

    if request.args.get('id'):
        alvo = Pessoa.query.filter_by(id=request.args.get('id')).first()

    is_admin = session.get('is_admin', False)
    return render_template('pesquisar_alvo.html', termo=termo, bairro=bairro, resultados=resultados, alvo=alvo, is_admin=is_admin)

@app.route('/editar_alvo', methods=['POST'])
def editar_alvo():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id_alvo = request.form['id']
    alvo = Pessoa.query.get(id_alvo)
    if not alvo:
        return '❌ Alvo não encontrado.'

    alvo.nome = limpar_texto(request.form['nome'])
    alvo.vulgo = limpar_texto(request.form['vulgo'])
    alvo.genitora = limpar_texto(request.form['genitora'])
    alvo.bairro = limpar_texto(request.form['bairro'])
    alvo.municipio = limpar_texto(request.form['municipio'])
    alvo.anotacoes = request.form['anotacoes']
    alvo.octopus = limpar_texto(request.form['octopus'])

    db.session.commit()
    return redirect(url_for('pesquisar_alvo', id=id_alvo))

@app.route('/atualizar_foto', methods=['POST'])
def atualizar_foto():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    id_alvo = request.form['id']
    nova_foto = request.files['nova_foto']
    if nova_foto and nova_foto.filename:
        foto_nome = secure_filename(nova_foto.filename)
        nova_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_nome))
        Pessoa.query.filter_by(id=id_alvo).update({'foto': foto_nome})
        db.session.commit()
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
    return "existente" if existe else "disponivel"

def mostrar_ip_local():
    try:
        hostname = socket.gethostname()
        ip_local = socket.gethostbyname(hostname)
        print(f"\n🌐 Site disponível em: http://{ip_local}:5000 (rede local)\n")
    except Exception as e:
        print("⚠️ IP local não detectado:", e)

if __name__ == '__main__':
    print("🚀 Iniciando o sistema...")
    mostrar_ip_local()
    app.run(debug=True, host='0.0.0.0', port=5000)
