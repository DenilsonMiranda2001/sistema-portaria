import re

def formatar_endereco_condominio(valor):
    if not valor:
        return ""

    valor = str(valor).strip().upper()

    # Mantém apenas números para testar padrão 070220
    numeros = re.sub(r"\D", "", valor)

    if len(numeros) == 6:
        quadra = numeros[0:2]
        conjunto = numeros[2:4]
        casa = numeros[4:6]
        return f"QUADRA {quadra}, CONJUNTO {conjunto}, CASA {casa}"

    return valor