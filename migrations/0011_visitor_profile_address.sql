-- Visitor profile address is master data, not a visit destination.
ALTER TABLE visitantes ADD COLUMN IF NOT EXISTS endereco TEXT;

-- Backfill only when a historical visit has an address and the profile has none.
-- Existing data may represent a destination, so this intentionally does not copy it.
COMMENT ON COLUMN visitantes.endereco IS 'Endereco cadastral do visitante; nao representa destino da visita.';
