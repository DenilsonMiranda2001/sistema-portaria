from database.models import criar_usuario

try:
    criar_usuario("Administrador", "admin", "123456", "admin")
    print("Usuário admin criado com sucesso.")
except Exception as e:
    print("Erro ao criar usuário:", e)