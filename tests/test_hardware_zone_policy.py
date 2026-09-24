from datetime import datetime, timezone
from pathlib import Path
from hardware.policy import evaluate_access_policies

def test_policy_can_authorize_logical_zone_independent_of_device():
    policy={"id":"p","ativo":True,"device_id":None,"access_zone_id":"garage","zona":None,
            "valido_de":None,"valido_ate":None,"dias_semana":[0,1,2,3,4,5,6],
            "hora_inicio":None,"hora_fim":None,"timezone":"UTC"}
    assert evaluate_access_policies([policy],device_id="replacement-device",zone="garage",
                                    at=datetime.now(timezone.utc)).allowed
    assert not evaluate_access_policies([policy],device_id="replacement-device",zone="lobby",
                                        at=datetime.now(timezone.utc)).allowed

def test_policy_schema_requires_device_or_logical_zone():
    source=Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "CHECK (device_id IS NOT NULL OR access_zone_id IS NOT NULL)" in source
    assert "FOREIGN KEY (access_zone_id, condominio_id)" in source
