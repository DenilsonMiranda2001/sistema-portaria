BEGIN;

-- Existing rows were protected by NOT VALID checks first. Once production has
-- run safely with those checks in place, validate historical data so the
-- constraints protect both old and new package records.
ALTER TABLE encomendas VALIDATE CONSTRAINT ck_encomendas_status_known;
ALTER TABLE encomendas VALIDATE CONSTRAINT ck_encomendas_retirada_evidence;

COMMIT;
