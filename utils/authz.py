from functools import wraps
from flask import abort, g, redirect, session, url_for
from database.models import buscar_usuario_por_id


def load_identity():
    if session.get("is_platform_admin"):
        g.current_user = {"id": session.get("usuario_id"), "nome": session.get("usuario_nome"), "nivel": "platform_admin", "ativo": True}
        g.tenant_id = None
        return
    user_id = session.get("usuario_id")
    if not user_id:
        g.current_user = None
        g.tenant_id = None
        return
    user = buscar_usuario_por_id(user_id)
    if not user or not user.get("ativo") or not user.get("condominio_ativo"):
        session.clear()
        g.current_user = None
        g.tenant_id = None
        return
    g.current_user = user
    g.tenant_id = user.get("condominio_id")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "current_user", None):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    allowed = set(roles)
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return redirect(url_for("auth.login"))
            if user.get("nivel") not in allowed:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
