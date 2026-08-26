import os
import uuid
import base64
from datetime import datetime

def salvar_foto_webcam(base64_data, pasta_destino):
    if not base64_data:
        return None

    if "," not in base64_data:
        return None

    cabecalho, dados_imagem = base64_data.split(",", 1)

    extensao = ".jpg"
    if "image/png" in cabecalho:
        extensao = ".png"
    elif "image/webp" in cabecalho:
        extensao = ".webp"

    nome_arquivo = f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{extensao}"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)

    with open(caminho_arquivo, "wb") as f:
        f.write(base64.b64decode(dados_imagem))

    return nome_arquivo