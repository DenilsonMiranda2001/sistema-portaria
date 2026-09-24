from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from database.connection import conectar, liberar
from hardware.provisioning import provision_simulator_device, revoke_device_auth, rotate_simulator_secret
from hardware.repository import HardwareRepository
from utils.authz import roles_required
from utils.audit import registrar_auditoria_cursor


hardware_admin_bp = Blueprint("hardware_admin", __name__, url_prefix="/admin/dispositivos")


@hardware_admin_bp.get("/")
@roles_required("admin_condominio")
def dispositivos():
    conn = conectar()
    try:
        devices = HardwareRepository(conn).list_devices(g.tenant_id)
        return render_template("hardware/dispositivos.html", devices=devices)
    finally:
        liberar(conn)


@hardware_admin_bp.post("/simulador")
@roles_required("admin_condominio")
def criar_simulador():
    nome = request.form.get("nome", "").strip()
    if not nome or len(nome) > 150:
        flash("Informe um nome válido para o dispositivo.", "erro")
        return redirect(url_for("hardware_admin.dispositivos"))
    conn = conectar()
    try:
        provisioned = provision_simulator_device(HardwareRepository(conn), tenant_id=g.tenant_id, name=nome)
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_device_provisioned", g.current_user["id"], g.tenant_id,
                                       "hardware_device", provisioned.device_id,
                                       {"vendor": "simulator", "nome": nome}, actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    return render_template("hardware/segredo_dispositivo.html", provisioned=provisioned)


@hardware_admin_bp.post("/<uuid:device_id>/rotacionar")
@roles_required("admin_condominio")
def rotacionar(device_id):
    conn = conectar()
    try:
        secret = rotate_simulator_secret(HardwareRepository(conn), tenant_id=g.tenant_id, device_id=str(device_id))
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_device_secret_rotated", g.current_user["id"], g.tenant_id,
                                       "hardware_device", device_id, {"vendor": "simulator"},
                                       actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except LookupError:
        conn.rollback()
        flash("Dispositivo não encontrado ou não elegível para rotação.", "erro")
        return redirect(url_for("hardware_admin.dispositivos"))
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    return render_template("hardware/segredo_dispositivo.html", provisioned={"device_id": str(device_id), "secret": secret, "key_id": None})


@hardware_admin_bp.post("/<uuid:device_id>/revogar")
@roles_required("admin_condominio")
def revogar(device_id):
    conn = conectar()
    try:
        changed = revoke_device_auth(HardwareRepository(conn), tenant_id=g.tenant_id, device_id=str(device_id))
        if changed:
            with conn.cursor() as cur:
                registrar_auditoria_cursor(cur, "hardware_device_auth_revoked", g.current_user["id"], g.tenant_id,
                                           "hardware_device", device_id, {},
                                           actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Autenticação do dispositivo revogada." if changed else "Dispositivo não encontrado ou já revogado.", "sucesso" if changed else "aviso")
    return redirect(url_for("hardware_admin.dispositivos"))
