import re


def limpar_cpf(cpf: str) -> str:
    return "".join(filter(str.isdigit, cpf or ""))


def validar_cpf(cpf: str) -> bool:
    cpf = limpar_cpf(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


def validar_placa(placa: str) -> bool:
    placa = (placa or "").strip().upper().replace("-", "")
    return bool(
        re.match(r"^[A-Z]{3}\d{4}$", placa) or      # padrão antigo
        re.match(r"^[A-Z]{3}\d[A-Z]\d{2}$", placa)  # Mercosul
    )


def sanitizar_texto(valor: str, maiusculo: bool = True) -> str:
    valor = (valor or "").strip()
    return valor.upper() if maiusculo else valor


EXTENSOES_FOTO_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}
MIME_FOTO_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
