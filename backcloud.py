import cloudinary
import cloudinary.api
import requests
import os

# 🔐 Configuração da conta
cloudinary.config(
    cloud_name='dygav0zig',
    api_key='356954525268762',
    api_secret='9KXP41yJPdXDj78aK_S6CKl_9-I'
)

# 📁 Pasta de destino
backup_folder = "backup_cloudinary"
os.makedirs(backup_folder, exist_ok=True)

# 🔄 Buscar imagens
print("🔍 Buscando imagens no Cloudinary...")
resources = cloudinary.api.resources(type="upload", resource_type="image", max_results=100)

# 💾 Baixar cada imagem
for item in resources["resources"]:
    url = item["secure_url"]
    ext = item["format"]
    filename = f"{item['public_id']}.{ext}"
    path = os.path.join(backup_folder, filename)

    print(f"⬇️ Baixando: {filename}")
    response = requests.get(url)
    with open(path, "wb") as f:
        f.write(response.content)

print("✅ Backup de imagens completo!")
