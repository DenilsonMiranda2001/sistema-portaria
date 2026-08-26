import sqlite3
import os
import sys
import re


def caminho_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def caminho_banco():
    return os.path.join(caminho_base(), "visitantes.db")


def conectar():
    conn = sqlite3.connect(caminho_banco())
    conn.row_factory = sqlite3.Row
    return conn


def limpar_cpf(cpf):
    return re.sub(r"\D", "", (cpf or "").strip())


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visitantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        cpf TEXT,
        endereco TEXT,
        tipo TEXT,
        placa TEXT,
        modelo TEXT,
        marca TEXT,
        foto TEXT,
        observacao TEXT,
        data_entrada TEXT,
        data_saida TEXT
    )
    """)

    conn.commit()
    conn.close()


def atualizar_tabela_visitantes():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(visitantes)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "endereco" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN endereco TEXT")

    if "tipo" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN tipo TEXT")

    if "placa" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN placa TEXT")

    if "modelo" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN modelo TEXT")

    if "marca" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN marca TEXT")

    if "foto" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN foto TEXT")

    if "observacao" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN observacao TEXT")

    if "data_entrada" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN data_entrada TEXT")

    if "data_saida" not in colunas:
        cursor.execute("ALTER TABLE visitantes ADD COLUMN data_saida TEXT")

    conn.commit()
    conn.close()


def criar_tabela_visitas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visitas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visitante_id INTEGER,
        endereco TEXT,
        data_entrada TEXT,
        data_saida TEXT,
        usuario_entrada_id INTEGER,
        usuario_saida_id INTEGER,
        placa TEXT,
        marca TEXT,
        modelo TEXT,
        FOREIGN KEY (visitante_id) REFERENCES visitantes(id),
        FOREIGN KEY (usuario_entrada_id) REFERENCES usuarios(id),
        FOREIGN KEY (usuario_saida_id) REFERENCES usuarios(id)
    )
    """)

    conn.commit()
    conn.close()


def atualizar_tabela_visitas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(visitas)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "endereco" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN endereco TEXT")

    if "usuario_entrada_id" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN usuario_entrada_id INTEGER")

    if "usuario_saida_id" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN usuario_saida_id INTEGER")

    if "placa" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN placa TEXT")

    if "marca" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN marca TEXT")

    if "modelo" not in colunas:
        cursor.execute("ALTER TABLE visitas ADD COLUMN modelo TEXT")

    conn.commit()
    conn.close()


def criar_tabela_usuarios():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT NOT NULL UNIQUE,
        senha TEXT NOT NULL,
        tipo TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def normalizar_cpfs_existentes():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, cpf FROM visitantes")
    visitantes = cursor.fetchall()

    for visitante in visitantes:
        cpf_limpo = limpar_cpf(visitante["cpf"])
        cursor.execute(
            "UPDATE visitantes SET cpf = ? WHERE id = ?",
            (cpf_limpo, visitante["id"])
        )

    conn.commit()
    conn.close()


def remover_cpfs_duplicados():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cpf
        FROM visitantes
        WHERE cpf IS NOT NULL AND TRIM(cpf) <> ''
        GROUP BY cpf
        HAVING COUNT(*) > 1
    """)
    cpfs_duplicados = cursor.fetchall()

    for item in cpfs_duplicados:
        cpf = item["cpf"]

        cursor.execute("""
            SELECT id
            FROM visitantes
            WHERE cpf = ?
            ORDER BY id ASC
        """, (cpf,))
        registros = cursor.fetchall()

        # mantém o primeiro e apaga os demais
        ids_para_apagar = [r["id"] for r in registros[1:]]

        for visitante_id in ids_para_apagar:
            # apaga visitas vinculadas ao cadastro duplicado
            cursor.execute("DELETE FROM visitas WHERE visitante_id = ?", (visitante_id,))
            # apaga o visitante duplicado
            cursor.execute("DELETE FROM visitantes WHERE id = ?", (visitante_id,))

    conn.commit()
    conn.close()


def criar_indice_unico_cpf():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_visitantes_cpf
        ON visitantes(cpf)
    """)

    conn.commit()
    conn.close()


def cpf_ja_cadastrado(cpf):
    conn = conectar()
    cursor = conn.cursor()

    cpf = limpar_cpf(cpf)

    cursor.execute("""
        SELECT id, nome, cpf
        FROM visitantes
        WHERE cpf = ?
        LIMIT 1
    """, (cpf,))

    visitante = cursor.fetchone()
    conn.close()
    return visitante

def limpar_cpf(cpf):
    return re.sub(r"\D", "", (cpf or "").strip())

def criar_tabela_usuarios():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'funcionario',
            ativo INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

def preparar_banco():
    criar_tabela()
    atualizar_tabela_visitantes()
    criar_tabela_visitas()
    atualizar_tabela_visitas()
    criar_tabela_usuarios()
    normalizar_cpfs_existentes()
    remover_cpfs_duplicados()
    criar_indice_unico_cpf()

def atualizar_tabela_usuarios():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "ativo" not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN ativo INTEGER DEFAULT 1")

    if "tipo" not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'funcionario'")

    conn.commit()
    conn.close()