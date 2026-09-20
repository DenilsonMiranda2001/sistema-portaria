BEGIN;

-- Tenant-aware composite identities let foreign keys enforce that related rows
-- belong to the same condominium, not merely that each id exists somewhere.
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_id_tenant ON usuarios(id, condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_unidades_id_tenant ON unidades(id, condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_moradores_id_tenant ON moradores(id, condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_visitantes_id_tenant ON visitantes(id, condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lotes_id_tenant ON lotes_encomendas(id, condominio_id);

ALTER TABLE moradores
    DROP CONSTRAINT IF EXISTS fk_moradores_unidade_tenant,
    ADD CONSTRAINT fk_moradores_unidade_tenant
      FOREIGN KEY (unidade_id, condominio_id)
      REFERENCES unidades(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE visitas
    DROP CONSTRAINT IF EXISTS fk_visitas_visitante_tenant,
    ADD CONSTRAINT fk_visitas_visitante_tenant
      FOREIGN KEY (visitante_id, condominio_id)
      REFERENCES visitantes(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_visitas_unidade_tenant,
    ADD CONSTRAINT fk_visitas_unidade_tenant
      FOREIGN KEY (unidade_id, condominio_id)
      REFERENCES unidades(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_visitas_morador_tenant,
    ADD CONSTRAINT fk_visitas_morador_tenant
      FOREIGN KEY (morador_id, condominio_id)
      REFERENCES moradores(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_visitas_usuario_entrada_tenant,
    ADD CONSTRAINT fk_visitas_usuario_entrada_tenant
      FOREIGN KEY (usuario_entrada_id, condominio_id)
      REFERENCES usuarios(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_visitas_usuario_saida_tenant,
    ADD CONSTRAINT fk_visitas_usuario_saida_tenant
      FOREIGN KEY (usuario_saida_id, condominio_id)
      REFERENCES usuarios(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE lotes_encomendas
    DROP CONSTRAINT IF EXISTS fk_lotes_usuario_tenant,
    ADD CONSTRAINT fk_lotes_usuario_tenant
      FOREIGN KEY (usuario_criacao_id, condominio_id)
      REFERENCES usuarios(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE encomendas
    DROP CONSTRAINT IF EXISTS fk_encomendas_lote_tenant,
    ADD CONSTRAINT fk_encomendas_lote_tenant
      FOREIGN KEY (lote_id, condominio_id)
      REFERENCES lotes_encomendas(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_encomendas_morador_tenant,
    ADD CONSTRAINT fk_encomendas_morador_tenant
      FOREIGN KEY (morador_id, condominio_id)
      REFERENCES moradores(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_encomendas_unidade_tenant,
    ADD CONSTRAINT fk_encomendas_unidade_tenant
      FOREIGN KEY (unidade_id, condominio_id)
      REFERENCES unidades(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE,
    DROP CONSTRAINT IF EXISTS fk_encomendas_usuario_tenant,
    ADD CONSTRAINT fk_encomendas_usuario_tenant
      FOREIGN KEY (usuario_criacao_id, condominio_id)
      REFERENCES usuarios(id, condominio_id)
      DEFERRABLE INITIALLY IMMEDIATE;

COMMIT;
