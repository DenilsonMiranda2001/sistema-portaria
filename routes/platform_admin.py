from functools import wraps
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
import re
from werkzeug.security import generate_password_hash
from database.connection import conectar, liberar

platform_admin_bp = Blueprint("platform_admin", __name__, url_prefix="/plataforma")

def platform_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user or user.get("nivel") != "platform_admin":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped

@platform_admin_bp.get("/condominios")
@platform_admin_required
def condominios():
    conn=conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id,nome,slug,ativo,criado_em FROM condominios ORDER BY nome")
            dados=cur.fetchall()
        return render_template("platform_condominios.html", condominios=dados)
    finally:
        liberar(conn)

@platform_admin_bp.post("/condominios")
@platform_admin_required
def criar_condominio():
    nome=request.form.get("nome","").strip()
    slug=request.form.get("slug","").strip().lower()
    if not nome or not slug:
        flash("Informe nome e código do condomínio.","erro")
        return redirect(url_for("platform_admin.condominios"))
    if len(slug) > 80 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        flash("O código deve usar apenas letras minúsculas, números e hífens.", "erro")
        return redirect(url_for("platform_admin.condominios"))
    conn=conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO condominios(nome,slug,ativo) VALUES(%s,%s,TRUE) RETURNING id",(nome,slug))
            cur.fetchone()
        conn.commit()
        flash("Condomínio criado com sucesso.","sucesso")
    except Exception:
        conn.rollback()
        flash("Não foi possível criar o condomínio. Verifique se o código já existe.","erro")
    finally:
        liberar(conn)
    return redirect(url_for("platform_admin.condominios"))

@platform_admin_bp.post("/condominios/<int:condominio_id>/usuarios")
@platform_admin_required
def criar_usuario_condominio(condominio_id):
    nome=request.form.get("nome","").strip()
    usuario=request.form.get("usuario","").strip()
    senha=request.form.get("senha","")
    nivel=request.form.get("nivel","funcionario").strip().lower()
    if nivel not in ("admin","funcionario"):
        nivel="funcionario"
    if not nome or not usuario or len(usuario) > 100 or len(senha)<12:
        flash("Preencha os dados do usuário; a senha deve ter pelo menos 12 caracteres.","erro")
        return redirect(url_for("platform_admin.condominios"))
    conn=conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM condominios WHERE id=%s AND ativo=TRUE",(condominio_id,))
            if not cur.fetchone():
                flash("Condomínio não encontrado ou inativo.","erro")
                return redirect(url_for("platform_admin.condominios"))
            cur.execute("SELECT 1 FROM platform_admins WHERE usuario=%s", (usuario,))
            if cur.fetchone():
                flash("Este login é reservado pela plataforma.", "erro")
                return redirect(url_for("platform_admin.condominios"))
            cur.execute("SELECT 1 FROM usuarios WHERE usuario=%s", (usuario,))
            if cur.fetchone():
                flash("Este login já está em uso.", "erro")
                return redirect(url_for("platform_admin.condominios"))
            cur.execute("""INSERT INTO usuarios(condominio_id,nome,usuario,senha,nivel,ativo)
                           VALUES(%s,%s,%s,%s,%s,TRUE)""",
                        (condominio_id,nome.upper(),usuario,generate_password_hash(senha),nivel))
        conn.commit()
        flash("Usuário do condomínio criado com sucesso.","sucesso")
    except Exception:
        conn.rollback()
        flash("Não foi possível criar o usuário.","erro")
    finally:
        liberar(conn)
    return redirect(url_for("platform_admin.condominios"))
