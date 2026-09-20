from functools import wraps
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
import re
from werkzeug.security import generate_password_hash
from database.platform import (
    listar_condominios_com_metricas, buscar_condominio_detalhe,
    atualizar_condominio, definir_status_condominio, definir_status_usuario_tenant,
    criar_condominio_com_usuario, criar_usuario_tenant,
)
from utils.audit import registrar_auditoria

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
    dados, resumo = listar_condominios_com_metricas()
    return render_template("platform_condominios.html", condominios=dados, resumo=resumo)

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
    try:
        condominio_id, _ = criar_condominio_com_usuario(nome, slug)
        registrar_auditoria("plataforma.condominio_criado", actor_tipo="platform_admin", actor_id=session["usuario_id"], entidade="condominio", entidade_id=condominio_id, detalhes={"slug": slug})
        flash("Condomínio criado com sucesso.","sucesso")
    except Exception:
        flash("Não foi possível criar o condomínio. Verifique se o código já existe.","erro")
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
    try:
        novo_usuario_id = criar_usuario_tenant(condominio_id, nome, usuario, generate_password_hash(senha), nivel)
        registrar_auditoria("plataforma.usuario_tenant_criado", actor_tipo="platform_admin", actor_id=session["usuario_id"], condominio_id=condominio_id, entidade="usuario", entidade_id=novo_usuario_id, detalhes={"nivel": nivel})
        flash("Usuário do condomínio criado com sucesso.","sucesso")
    except ValueError as exc:
        flash(str(exc),"erro")
    except Exception:
        flash("Não foi possível criar o usuário. Verifique se o login já está em uso.","erro")
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
                           VALUES(%s,%s,%s,%s,%s,TRUE) RETURNING id""",
                        (condominio_id,nome.upper(),usuario,generate_password_hash(senha),nivel))
            novo_usuario = cur.fetchone()
        conn.commit()
        registrar_auditoria("plataforma.usuario_tenant_criado", actor_tipo="platform_admin", actor_id=session["usuario_id"], condominio_id=condominio_id, entidade="usuario", entidade_id=novo_usuario["id"], detalhes={"nivel": nivel})
        flash("Usuário do condomínio criado com sucesso.","sucesso")
    except Exception:
        conn.rollback()
        flash("Não foi possível criar o usuário.","erro")
    finally:
        liberar(conn)
    return redirect(url_for("platform_admin.condominios"))


@platform_admin_bp.get("/condominios/<int:condominio_id>")
@platform_admin_required
def detalhe_condominio(condominio_id):
    condominio, usuarios = buscar_condominio_detalhe(condominio_id)
    if not condominio:
        flash("Condomínio não encontrado.", "erro")
        return redirect(url_for("platform_admin.condominios"))
    return render_template("platform_condominio_detalhe.html", condominio=condominio, usuarios=usuarios)


@platform_admin_bp.post("/condominios/<int:condominio_id>/editar")
@platform_admin_required
def editar_condominio(condominio_id):
    nome=request.form.get("nome","").strip()
    slug=request.form.get("slug","").strip().lower()
    if not nome or len(nome)>160 or len(slug)>80 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",slug):
        flash("Dados do condomínio inválidos.","erro")
        return redirect(url_for("platform_admin.detalhe_condominio",condominio_id=condominio_id))
    try:
        if not atualizar_condominio(condominio_id,nome,slug):
            flash("Condomínio não encontrado.","erro")
        else:
            registrar_auditoria("plataforma.condominio_atualizado",actor_tipo="platform_admin",actor_id=session["usuario_id"],entidade="condominio",entidade_id=condominio_id,detalhes={"slug":slug})
            flash("Condomínio atualizado.","sucesso")
    except Exception:
        flash("Não foi possível atualizar o condomínio. Verifique o código informado.","erro")
    return redirect(url_for("platform_admin.detalhe_condominio",condominio_id=condominio_id))


@platform_admin_bp.post("/condominios/<int:condominio_id>/status")
@platform_admin_required
def status_condominio(condominio_id):
    ativo=request.form.get("ativo")=="1"
    try:
        if definir_status_condominio(condominio_id,ativo):
            registrar_auditoria("plataforma.condominio_status",actor_tipo="platform_admin",actor_id=session["usuario_id"],entidade="condominio",entidade_id=condominio_id,detalhes={"ativo":ativo})
            flash("Status do condomínio atualizado.","sucesso")
    except ValueError as exc:
        flash(str(exc),"erro")
    return redirect(url_for("platform_admin.detalhe_condominio",condominio_id=condominio_id))


@platform_admin_bp.post("/condominios/<int:condominio_id>/usuarios/<int:usuario_id>/status")
@platform_admin_required
def status_usuario_condominio(condominio_id,usuario_id):
    ativo=request.form.get("ativo")=="1"
    try:
        if definir_status_usuario_tenant(condominio_id,usuario_id,ativo):
            registrar_auditoria("plataforma.usuario_tenant_status",actor_tipo="platform_admin",actor_id=session["usuario_id"],condominio_id=condominio_id,entidade="usuario",entidade_id=usuario_id,detalhes={"ativo":ativo})
            flash("Status do usuário atualizado.","sucesso")
    except ValueError as exc:
        flash(str(exc),"erro")
    return redirect(url_for("platform_admin.detalhe_condominio",condominio_id=condominio_id))
