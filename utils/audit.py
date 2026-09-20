import hashlib
import json
import os
from flask import request
from database.connection import conectar, liberar


def _ip_hash():
    ip = (request.remote_addr or "").strip()
    salt = os.getenv("AUDIT_IP_SALT", "")
    return hashlib.sha256((salt + ip).encode("utf-8")).hexdigest() if ip else None


def registrar_auditoria(acao, usuario_id=None, condominio_id=None, entidade=None, entidade_id=None, detalhes=None):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs
                    (condominio_id, usuario_id, acao, entidade, entidade_id, detalhes, ip_hash)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
            """, (
                condominio_id, usuario_id, acao, entidade,
                str(entidade_id) if entidade_id is not None else None,
                json.dumps(detalhes or {}, ensure_ascii=False),
                _ip_hash(),
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
