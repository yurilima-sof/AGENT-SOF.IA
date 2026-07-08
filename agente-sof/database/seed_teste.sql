-- =============================================================================
-- database/seed_teste.sql - Seed MÍNIMO para Testes (Grupo Thiago)
-- =============================================================================
-- Este script popula apenas o grupo de teste para validar o fluxo completo
-- antes de expandir para os demais clientes.
--
-- COMO RODAR:
--   docker exec -i agente_sof_db psql -U agente_user -d agente_sof_db < database/seed_teste.sql
-- =============================================================================

-- Garante que o registro não vai duplicar se rodar o script mais de uma vez.
INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, estado, credenciais_tuya, ativo)
VALUES (
  '120363422455765261-group',
  'Grupo Thiago (Teste)',
  'PE',
  '{
    "tipo": "ifttt",
    "observacao": "Grupo exclusivo de testes - Jaylson SOF",
    "freezer": "https://maker.ifttt.com/trigger/T-LOW-TESTE/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/Teste_ligar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "medio": "https://maker.ifttt.com/trigger/TESTE/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/T-OFF-TEST/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "ligar": "https://maker.ifttt.com/trigger/Teste_ligar/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
)
ON CONFLICT (id_grupo_wpp)
DO UPDATE SET
  nome_revenda    = EXCLUDED.nome_revenda,
  credenciais_tuya = EXCLUDED.credenciais_tuya,
  ativo           = EXCLUDED.ativo,
  atualizado_em   = NOW();

-- Confirma o que foi inserido
SELECT
  id_grupo_wpp,
  nome_revenda,
  estado,
  ativo,
  credenciais_tuya->>'freezer'   AS ifttt_freezer,
  credenciais_tuya->>'esquentar' AS ifttt_esquentar,
  credenciais_tuya->>'off'       AS ifttt_off,
  criado_em
FROM mapa_revendas
WHERE id_grupo_wpp = '120363422455765261-group';
