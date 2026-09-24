import uuid
import re
from datetime import time
from psycopg2 import errors
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from database.connection import conectar, liberar
from database.models import listar_moradores
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
        repo = HardwareRepository(conn)
        devices = repo.list_device_operational_status(g.tenant_id)
        zones = [z for z in repo.list_access_zones(g.tenant_id) if z["ativo"]]
        alerts = [d for d in devices if d["operational_status"] != "online"]
        return render_template("hardware/dispositivos.html", devices=devices, zones=zones, alerts=alerts)
    finally:
        liberar(conn)


@hardware_admin_bp.get("/credenciais")
@roles_required("admin_condominio")
def credenciais():
    conn = conectar()
    try:
        credentials = HardwareRepository(conn).list_credentials(g.tenant_id)
        residents = listar_moradores(apenas_ativos=True)
        return render_template("hardware/credenciais.html", credentials=credentials, residents=residents)
    finally:
        liberar(conn)


@hardware_admin_bp.post("/credenciais/morador")
@roles_required("admin_condominio")
def criar_credencial_morador():
    raw_identifier = request.form.get("identificador", "").strip()
    resident_id = request.form.get("morador_id", "").strip()
    credential_type = request.form.get("tipo", "rfid").strip().lower()
    if credential_type not in {"rfid", "uhf"} or not raw_identifier or len(raw_identifier) > 256 or not resident_id.isdigit():
        flash("Dados da credencial inválidos.", "erro")
        return redirect(url_for("hardware_admin.credenciais"))
    conn = conectar()
    try:
        repo = HardwareRepository(conn)
        credential_id = str(uuid.uuid4())
        created = repo.create_resident_credential(
            credential_id=credential_id, tenant_id=g.tenant_id, credential_type=credential_type,
            raw_identifier=raw_identifier, resident_id=int(resident_id)
        )
        if not created:
            conn.rollback()
            flash("Morador ativo não encontrado neste condomínio.", "erro")
            return redirect(url_for("hardware_admin.credenciais"))
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_credential_created", g.current_user["id"], g.tenant_id,
                                       "hardware_credential", credential_id,
                                       {"tipo": credential_type, "morador_id": int(resident_id)},
                                       actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
        flash("Credencial cadastrada.", "sucesso")
    except errors.UniqueViolation:
        conn.rollback()
        flash("Esta credencial já está cadastrada neste condomínio.", "erro")
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    return redirect(url_for("hardware_admin.credenciais"))


@hardware_admin_bp.post("/credenciais/<uuid:credential_id>/desativar")
@roles_required("admin_condominio")
def desativar_credencial(credential_id):
    conn = conectar()
    try:
        changed = HardwareRepository(conn).deactivate_credential(g.tenant_id, str(credential_id))
        if changed:
            with conn.cursor() as cur:
                registrar_auditoria_cursor(cur, "hardware_credential_deactivated", g.current_user["id"], g.tenant_id,
                                           "hardware_credential", credential_id, {},
                                           actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Credencial desativada." if changed else "Credencial não encontrada ou já inativa.",
          "sucesso" if changed else "aviso")
    return redirect(url_for("hardware_admin.credenciais"))


@hardware_admin_bp.get("/incidentes")
@roles_required("admin_condominio")
def incidentes():
    conn = conectar()
    try:
        return render_template("hardware/incidentes.html",
                               incidents=HardwareRepository(conn).list_incidents(g.tenant_id))
    finally:
        liberar(conn)


@hardware_admin_bp.get("/zonas")
@roles_required("admin_condominio")
def zonas():
    conn = conectar()
    try:
        zones = HardwareRepository(conn).list_access_zone_operational_status(g.tenant_id)
        alerts = [z for z in zones if z["ativo"] and z["operational_status"] != "operational"]
        return render_template("hardware/zonas.html", zones=zones, alerts=alerts)
    finally:
        liberar(conn)


@hardware_admin_bp.post("/zonas")
@roles_required("admin_condominio")
def criar_zona():
    name = request.form.get("nome", "").strip()
    code = request.form.get("codigo", "").strip().lower().replace(" ", "-")
    description = request.form.get("descricao", "").strip() or None
    if (not name or len(name) > 120 or not code or len(code) > 80
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", code)
            or (description is not None and len(description) > 500)):
        flash("Informe nome e código válidos para o ponto de acesso.", "erro")
        return redirect(url_for("hardware_admin.zonas"))
    conn = conectar()
    zone_id = str(uuid.uuid4())
    try:
        HardwareRepository(conn).create_access_zone(zone_id=zone_id, tenant_id=g.tenant_id, name=name, code=code, description=description)
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_access_zone_created", g.current_user["id"], g.tenant_id,
                                       "hardware_access_zone", zone_id, {"nome": name, "codigo": code},
                                       actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except errors.UniqueViolation:
        conn.rollback()
        flash("Já existe um ponto de acesso com esse código neste condomínio.", "erro")
        return redirect(url_for("hardware_admin.zonas"))
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Ponto de acesso criado.", "sucesso")
    return redirect(url_for("hardware_admin.zonas"))


@hardware_admin_bp.post("/zonas/<uuid:zone_id>/desativar")
@roles_required("admin_condominio")
def desativar_zona(zone_id):
    conn = conectar()
    try:
        changed = HardwareRepository(conn).deactivate_access_zone(g.tenant_id, str(zone_id))
        if changed:
            with conn.cursor() as cur:
                registrar_auditoria_cursor(cur, "hardware_access_zone_deactivated", g.current_user["id"], g.tenant_id,
                                           "hardware_access_zone", zone_id, {},
                                           actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Ponto de acesso desativado." if changed else "Ponto de acesso não encontrado ou já inativo.",
          "sucesso" if changed else "aviso")
    return redirect(url_for("hardware_admin.zonas"))


@hardware_admin_bp.get("/permissoes")
@roles_required("admin_condominio")
def permissoes():
    conn = conectar()
    try:
        repo = HardwareRepository(conn)
        return render_template("hardware/permissoes.html",
                               policies=repo.list_admin_access_policies(g.tenant_id),
                               credentials=[x for x in repo.list_credentials(g.tenant_id) if x["ativo"]],
                               zones=[x for x in repo.list_access_zones(g.tenant_id) if x["ativo"]])
    finally:
        liberar(conn)


@hardware_admin_bp.post("/permissoes")
@roles_required("admin_condominio")
def criar_permissao():
    credential_id = request.form.get("credential_id", "").strip()
    access_zone_id = request.form.get("access_zone_id", "").strip()
    weekdays_raw = request.form.getlist("dias_semana")
    start_time = request.form.get("hora_inicio", "").strip() or None
    end_time = request.form.get("hora_fim", "").strip() or None
    try:
        weekdays = sorted({int(day) for day in weekdays_raw})
    except ValueError:
        weekdays = []
    try:
        uuid.UUID(credential_id)
        uuid.UUID(access_zone_id)
    except (ValueError, AttributeError):
        flash("Selecione credencial e ponto de acesso válidos.", "erro")
        return redirect(url_for("hardware_admin.permissoes"))
    if not weekdays or any(day < 0 or day > 6 for day in weekdays):
        flash("Selecione ao menos um dia válido.", "erro")
        return redirect(url_for("hardware_admin.permissoes"))
    if bool(start_time) != bool(end_time):
        flash("Informe horário inicial e final juntos.", "erro")
        return redirect(url_for("hardware_admin.permissoes"))
    if start_time:
        try:
            time.fromisoformat(start_time)
            time.fromisoformat(end_time)
        except ValueError:
            flash("Informe horários válidos.", "erro")
            return redirect(url_for("hardware_admin.permissoes"))
    conn = conectar()
    policy_id = str(uuid.uuid4())
    try:
        created = HardwareRepository(conn).create_access_policy(
            policy_id=policy_id, tenant_id=g.tenant_id, credential_id=credential_id,
            access_zone_id=access_zone_id, weekdays=weekdays, start_time=start_time, end_time=end_time
        )
        if not created:
            conn.rollback()
            flash("Credencial ou ponto de acesso não pertence a este condomínio ou está inativo.", "erro")
            return redirect(url_for("hardware_admin.permissoes"))
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_access_policy_created", g.current_user["id"], g.tenant_id,
                                       "hardware_access_policy", policy_id,
                                       {"access_zone_id": access_zone_id, "credential_id": credential_id, "dias_semana": weekdays},
                                       actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Permissão de acesso criada.", "sucesso")
    return redirect(url_for("hardware_admin.permissoes"))


@hardware_admin_bp.post("/permissoes/<uuid:policy_id>/desativar")
@roles_required("admin_condominio")
def desativar_permissao(policy_id):
    conn = conectar()
    try:
        changed = HardwareRepository(conn).deactivate_access_policy(g.tenant_id, str(policy_id))
        if changed:
            with conn.cursor() as cur:
                registrar_auditoria_cursor(cur, "hardware_access_policy_deactivated", g.current_user["id"], g.tenant_id,
                                           "hardware_access_policy", policy_id, {},
                                           actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Permissão desativada." if changed else "Permissão não encontrada ou já inativa.",
          "sucesso" if changed else "aviso")
    return redirect(url_for("hardware_admin.permissoes"))


@hardware_admin_bp.post("/<uuid:device_id>/zona")
@roles_required("admin_condominio")
def vincular_zona_dispositivo(device_id):
    zone_id = request.form.get("zone_id", "").strip()
    if not zone_id:
        flash("Selecione um ponto de acesso.", "erro")
        return redirect(url_for("hardware_admin.dispositivos"))
    try:
        uuid.UUID(zone_id)
    except (ValueError, AttributeError):
        flash("Ponto de acesso inválido.", "erro")
        return redirect(url_for("hardware_admin.dispositivos"))
    conn = conectar()
    try:
        assigned = HardwareRepository(conn).assign_device_zone(g.tenant_id, str(device_id), zone_id)
        if not assigned:
            conn.rollback()
            flash("Dispositivo ou ponto de acesso não pertence a este condomínio ou está inativo.", "erro")
            return redirect(url_for("hardware_admin.dispositivos"))
        with conn.cursor() as cur:
            registrar_auditoria_cursor(cur, "hardware_device_zone_assigned", g.current_user["id"], g.tenant_id,
                                       "hardware_device", device_id, {"access_zone_id": zone_id},
                                       actor_tipo="usuario", actor_id=g.current_user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
    flash("Ponto de acesso vinculado ao dispositivo.", "sucesso")
    return redirect(url_for("hardware_admin.dispositivos"))


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
    response = make_response(render_template("hardware/segredo_dispositivo.html", provisioned=provisioned))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


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
    response = make_response(render_template(
        "hardware/segredo_dispositivo.html",
        provisioned={"device_id": str(device_id), "secret": secret, "key_id": None},
    ))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


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
