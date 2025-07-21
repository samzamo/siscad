from app import app, db, Usuario  # certifique-se que 'app' está sendo importado
import hashlib

# Gera o hash da senha
senha_hash = hashlib.sha256('LATINA'.encode()).hexdigest()

# Ativa o contexto da aplicação
with app.app_context():
    novo_usuario = Usuario(
        username='SAMARA',
        password=senha_hash,
        ativo=True,
        tipo='admin'
    )

    db.session.add(novo_usuario)
    db.session.commit()

    print("Usuário SAMARA criado com sucesso!")