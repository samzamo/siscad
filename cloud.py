import os
import cloudinary
import cloudinary.uploader

# ✅ Configuração do Cloudinary
cloudinary.config(
    cloud_name='dygav0zig',
    api_key='893737834757873',
    api_secret='SZgEhRl51osJgbThv-SUN5ErK1M'
)

# 📂 Pasta onde estão as imagens
IMAGEM_DIR = os.path.join(os.path.dirname(__file__), 'static', 'IMAGEM')

# 🖼️ Lista para armazenar os <img> tags
img_tags = []

# 🚀 Percorre os arquivos da pasta
for filename in os.listdir(IMAGEM_DIR):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        caminho_completo = os.path.join(IMAGEM_DIR, filename)
        public_id = os.path.splitext(filename)[0].strip()  # remove espaços extras

        print(f'📤 Upload de: "{filename}" como public_id: "{public_id}"')

        # ☁️ Upload para Cloudinary
        resultado = cloudinary.uploader.upload(
            caminho_completo,
            folder='meu_site',
            public_id=public_id,
            overwrite=True
        )

        # 🔗 Gera a tag HTML
        url = resultado['secure_url']
        tag = f'<img src="{url}" alt="{filename}">'
        img_tags.append(tag)

# ✅ Exibe os <img> tags gerados
print('\n✅ Tags HTML geradas:')
for tag in img_tags:
    print(tag)
