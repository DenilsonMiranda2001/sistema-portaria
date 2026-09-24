from database.connection import conectar, liberar
from .repository import HardwareRepository


INCIDENT_TYPE = "access_zone_unavailable"


def reconcile_hardware_incidents(tenant_id: int, stale_seconds: int = 90):
    """Open/update one incident per unavailable zone and resolve it after recovery."""
    conn = conectar()
    try:
        repo = HardwareRepository(conn)
        zones = repo.list_access_zone_operational_status(tenant_id, stale_seconds=stale_seconds)
        changed = []
        for zone in zones:
            if not zone["ativo"]:
                continue
            status = zone["operational_status"]
            # A configured zone with no assigned device is an onboarding/configuration state,
            # not an operational outage. Incident monitoring starts once hardware is assigned.
            if status == "no_device":
                repo.reconcile_zone_incident(
                    tenant_id=tenant_id,
                    zone_id=zone["id"],
                    incident_type=INCIDENT_TYPE,
                    unavailable=False,
                )
                continue
            unavailable = status == "unavailable"
            result = repo.reconcile_zone_incident(
                tenant_id=tenant_id,
                zone_id=zone["id"],
                incident_type=INCIDENT_TYPE,
                unavailable=unavailable,
                details={
                    "operational_status": zone["operational_status"],
                    "active_devices": zone["active_devices"],
                    "online_devices": zone["online_devices"],
                },
            )
            if result:
                changed.append(result)
        conn.commit()
        return changed
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
