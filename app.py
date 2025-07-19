import unicodedata
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import os
import pandas as pd
from werkzeug.utils import secure_filename
import socket

def limpar_texto(texto):
    texto = texto.upper()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura_123'
app.config['UPLOAD_FOLDER'] = 'static/IMAGEM'

def criar_tabelas():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            ativo INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            vulgo TEXT,
            foto TEXT,
            genitora TEXT,
            bairro TEXT,
            anotacoes TEXT,
            octopus TEXT,
            municipio TEXT
        )
    ''')
    conn.commit()
    conn.close()

def importar_planilha():
    caminho = 'pessoas.xlsx'
    if not os.path.exists(caminho): return
    df = pd.read_excel(caminho)
    df.columns = df.columns.str.strip().str.lower()
    obrigatorias = ['id', 'nome', 'vulgo', 'foto', 'genitora', 'bairro', 'anotacoes', 'octopus', 'municipio']
    if not all(c in df.columns for c in obrigatorias): return
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    for _, row in df.iterrows():
        try:
            id_valor = int(row['id'])
            nome = str(row['nome']).strip()
            vulgo = str(row['vulgo']).strip()
            foto = str(row['foto']).strip()
            genitora = str(row['genitora']).strip()
            bairro = str(row['bairro']).strip()
            anotacoes = str(row['anotacoes']).strip()
            octopus = str(row['octopus']).strip()
            municipio = str(row['municipio']).strip()
            cursor.execute('SELECT * FROM pessoas WHERE id = ?', (id_valor,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO pessoas (
                        id, nome, vulgo, foto, genitora, bairro, anotacoes, octopus, municipio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (id_valor, nome, vulgo, foto, genitora, bairro, anotacoes, octopus, municipio))
        except:
            pass
    conn.commit()
    conn.close()

criar_tabelas()
importar_planilha()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        raw_password = request.form['password']
        password = hashlib.sha256(raw_password.encode()).hexdigest()

        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password, ativo, tipo FROM usuarios WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            if user[3] == 1:  # Verifica se está ativo
                session['usuario_logado'] = username
                session['is_admin'] = (user[4] == 'adm')  # Agora usando o campo tipo
                return redirect(url_for('menu_principal'))
            else:
                return '⛔ Aguarde liberação do administrador.'
        else:
            return '⚠️ Login inválido.'

    return render_template('login.html')

@app.route('/menu')
def menu_principal():
    is_admin = session.get('is_admin', False)
    return render_template('menu.html', is_admin=is_admin)

@app.route('/gerenciar_usuarios', methods=['GET', 'POST'])
def gerenciar_usuarios():
    if not session.get('is_admin'):
        return '⚠️ Acesso negado. Esta página é restrita a administradores.'

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    # 🔒 Atualizar senha
    if request.method == 'POST' and 'nova_senha' in request.form:
        user_id = request.form['id']
        nova_senha = request.form['nova_senha']
        hash = hashlib.sha256(nova_senha.encode()).hexdigest()
        cursor.execute('UPDATE usuarios SET password = ? WHERE id = ?', (hash, user_id))
        conn.commit()

    # 🗑️ Excluir usuário
    if request.method == 'POST' and 'excluir_id' in request.form:
        excluir_id = request.form['excluir_id']
        cursor.execute('DELETE FROM usuarios WHERE id = ?', (excluir_id,))
        conn.commit()

    # 🔁 Alterar tipo (perfil)
    if request.method == 'POST' and 'novo_tipo' in request.form:
        user_id = request.form['id']
        novo_tipo = request.form['novo_tipo']
        if novo_tipo in ['adm', 'normal']:
            cursor.execute('UPDATE usuarios SET tipo = ? WHERE id = ?', (novo_tipo, user_id))
            conn.commit()

    # 🔄 Listagem de usuários
    cursor.execute('SELECT id, username, ativo, password, tipo FROM usuarios')
    usuarios = cursor.fetchall()

    # ⏳ Usuários pendentes
    cursor.execute('SELECT id, username FROM usuarios WHERE ativo = 0')
    pendentes = cursor.fetchall()

    conn.close()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios, pendentes=pendentes)

@app.route('/autorizar/<int:id>')
def autorizar(id):
    if not session.get('is_admin'):
        return '⚠️ Acesso negado. Esta página é restrita a administradores.'

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET ativo = 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('gerenciar_usuarios'))

# Parte 2 continua já já! 😄 Segura que vou trazer o resto completinho pra você.
@app.route('/pesquisar_alvo', methods=['GET', 'POST'])
def pesquisar_alvo():
    termo = ''
    bairro = ''
    resultados = []
    alvo = None

    if request.method == 'POST':
        termo = limpar_texto(request.form['termo'])
        bairro = limpar_texto(request.form['bairro'])
        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        if bairro:
            cursor.execute('''
                SELECT * FROM pessoas
                WHERE (nome LIKE ? OR vulgo LIKE ?) AND bairro LIKE ?
            ''', (f'%{termo}%', f'%{termo}%', f'%{bairro}%'))
        else:
            cursor.execute('''
                SELECT * FROM pessoas
                WHERE nome LIKE ? OR vulgo LIKE ?
            ''', (f'%{termo}%', f'%{termo}%'))
        resultados = cursor.fetchall()
        conn.close()

    if request.args.get('id'):
        id_alvo = request.args.get('id')
        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pessoas WHERE id = ?', (id_alvo,))
        alvo = cursor.fetchone()
        conn.close()

    is_admin = session.get('is_admin', False)
    return render_template('pesquisar_alvo.html', termo=termo, bairro=bairro, resultados=resultados, alvo=alvo, is_admin=is_admin)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['password']
        confirmar = request.form['confirmar']

        if senha != confirmar:
            return '⚠️ As senhas não coincidem.'

        password_hash = hashlib.sha256(senha.encode()).hexdigest()
        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO usuarios (username, password, ativo)
                VALUES (?, ?, 0)
            ''', (username, password_hash))
            conn.commit()
            return '✅ Cadastro enviado! Aguarde aprovação.'
        except sqlite3.IntegrityError:
            return '⚠️ Usuário já existe.'
        finally:
            conn.close()

    return render_template('cadastro.html')


from flask import request, render_template
from werkzeug.utils import secure_filename
import sqlite3
import os

@app.route('/cadastro_alvo', methods=['GET', 'POST'])
def cadastro_alvo():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM pessoas')
    total_cadastros = cursor.fetchone()[0]

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

        # 🔍 Verifica se já existe nome OU vulgo cadastrado
        cursor.execute('SELECT id FROM pessoas WHERE nome = ? OR vulgo = ?', (nome, vulgo))
        existente = cursor.fetchone()
        if existente:
            conn.close()
            return render_template(
                'cadastro_alvo.html',
                mensagem="⚠️ Este nome ou vulgo já está cadastrado.",
                total=total_cadastros
            )

        # 🚀 Insere novo registro
        cursor.execute('''
            INSERT INTO pessoas (
                id, nome, vulgo, foto, genitora, bairro, anotacoes, octopus, municipio
            ) VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM pessoas), ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, vulgo, foto_nome, genitora, bairro, anotacoes, octopus, municipio))

        conn.commit()
        cursor.execute('SELECT COUNT(*) FROM pessoas')
        total_cadastros = cursor.fetchone()[0]
        conn.close()

        return render_template('sucesso.html', mensagem='✅ Alvo cadastrado com sucesso!')

    conn.close()
    return render_template('cadastro_alvo.html', total=total_cadastros)

@app.route('/verificar_nome')
def verificar_nome():
    nome = request.args.get('nome', '').strip()
    if not nome:
        return 'vazio'

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM pessoas WHERE LOWER(nome) = LOWER(?)', (nome,))
    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        return 'existente'
    else:
        return 'novo'

@app.route('/atualizar_foto', methods=['POST'])
def atualizar_foto():
    id_alvo = request.form['id']
    nova_foto = request.files['nova_foto']
    if nova_foto and nova_foto.filename:
        foto_nome = secure_filename(nova_foto.filename)
        nova_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_nome))
        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE pessoas SET foto = ? WHERE id = ?', (foto_nome, id_alvo))
        conn.commit()
        conn.close()
    return redirect(url_for('pesquisar_alvo', id=id_alvo))


@app.route('/editar_alvo', methods=['POST'])
def editar_alvo():
    id_alvo = request.form['id']
    nome = limpar_texto(request.form['nome'])
    vulgo = limpar_texto(request.form['vulgo'])
    genitora = limpar_texto(request.form['genitora'])
    bairro = limpar_texto(request.form['bairro'])
    municipio = limpar_texto(request.form['municipio'])
    anotacoes = request.form['anotacoes']
    octopus = limpar_texto(request.form['octopus'])

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pessoas
        SET nome = ?, vulgo = ?, genitora = ?, bairro = ?, municipio = ?, anotacoes = ?, octopus = ?
        WHERE id = ?
    ''', (nome, vulgo, genitora, bairro, municipio, anotacoes, octopus, id_alvo))
    conn.commit()
    conn.close()
    return redirect(url_for('pesquisar_alvo', id=id_alvo))


@app.route('/excluir_alvo', methods=['POST'])
def excluir_alvo():
    id_alvo = request.form['id']
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pessoas WHERE id = ?', (id_alvo,))
    conn.commit()
    conn.close()
    return redirect(url_for('pesquisar_alvo'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def mostrar_ip_local():
    try:
        hostname = socket.gethostname()
        ip_local = socket.gethostbyname(hostname)
        print(f"\n🌐 Site disponível em: http://{ip_local}:5000 (rede local)\n")
    except Exception as e:
        print("⚠️ Não foi possível detectar o IP local:", e)

if __name__ == '__main__':
    print("🚀 Iniciando o sistema...")
    mostrar_ip_local()
    app.run(debug=True, host='0.0.0.0', port=5000)
