-- =============================================================================
-- database/seed_grupos.sql - Dados Iniciais de Grupos/Revendas para Testes
-- =============================================================================
-- COMO USAR:
--   Execute este script DEPOIS que o banco já estiver rodando:
--   docker exec -i agente_sof_db psql -U agente_user -d agente_sof_db < database/seed_grupos.sql
--
-- IMPORTANTE:
--   Os links IFTTT abaixo foram extraídos do fluxo n8n atual.
--   Grupos com links comentados (pendentes) são inseridos mas sem URLs ativas.
--   O campo `ativo` = false bloqueia grupos sem configuração IFTTT.
-- =============================================================================

-- Limpa registros anteriores de seed (idempotente: pode rodar várias vezes).
-- Em produção, USE APENAS INSERT ... ON CONFLICT para não perder dados reais!
DELETE FROM mapa_revendas WHERE id_grupo_wpp LIKE '%-group';


-- =============================================================================
-- GRUPOS COM IFTTT CONFIGURADO E ATIVO ✅
-- =============================================================================

INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, estado, credenciais_tuya, ativo) VALUES
(
  '120363298041373758-group',
  'Revenda 0019',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0019_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0019_esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0019_off/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363401204481216-group',
  'Revenda 0047',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0047_Esfriar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0047_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0047_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363298127856818-group',
  'Revenda 0016',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0016_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0016_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0016_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363279998161437-group',
  'Revenda 0020',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0020_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0020_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0020_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363199036541250-group',
  'Revenda 0002',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0002_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0002_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0002_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363282476786392-group',
  'Revenda 0021',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0021_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0021_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0021_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363279978711780-group',
  'Revenda 0009',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0009_Freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0009_esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0009_off/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363281098848004-group',
  'Revenda 0018',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0018_freezer/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": "https://maker.ifttt.com/trigger/0018_Esquentar/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "off": "https://maker.ifttt.com/trigger/0018_OFF/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
),
(
  '120363422455765261-group',
  'Grupo Thiago (Teste)',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/thiago_on/with/key/boVO_NH7Ia-1fj95TkxKZf",
    "esquentar": null,
    "off": "https://maker.ifttt.com/trigger/thiago_off/with/key/boVO_NH7Ia-1fj95TkxKZf"
  }',
  true
);


-- =============================================================================
-- GRUPOS PENDENTES DE CONFIGURAÇÃO IFTTT ⚠️ (ativo = false)
-- =============================================================================
-- Estão no mapa mas não serão acionados até configurar os links IFTTT.

INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, estado, credenciais_tuya, ativo) VALUES
('120363324972918585-group', 'Revenda 0015 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363399960956454-group', 'Revenda 0076 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363421263750896-group', 'Revenda 0063 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363418714887384-group', 'Revenda 0037 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363401359633431-group', 'Revenda 0040 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363419939662342-group', 'Revenda 0052 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363418878294124-group', 'Revenda 0045 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363419677042527-group', 'Revenda 0042 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363400265141468-group', 'Revenda 0048 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363404164054502-group', 'Revenda 0039 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363283372696640-group', 'Revenda 0033 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363418500883724-group', 'Revenda 0051 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363418248455431-group', 'Revenda 0049 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363416691329634-group', 'Revenda 0044 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363420148871001-group', 'Revenda 0041 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363299730692570-group', 'Revenda 0032 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363402155032954-group', 'Revenda 0064 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363299584288213-group', 'Revenda 0034 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false),
('120363416873746928-group', 'Revenda 0065 (Pendente)', 'XX', '{"tipo": "ifttt", "status": "pendente_configuracao"}', false);


-- =============================================================================
-- VERIFICAÇÃO FINAL
-- =============================================================================
SELECT
  id_grupo_wpp,
  nome_revenda,
  ativo,
  credenciais_tuya->>'tipo' AS tipo_integracao,
  CASE
    WHEN credenciais_tuya->>'status' = 'pendente_configuracao' THEN '⚠️  PENDENTE'
    WHEN ativo = true THEN '✅ ATIVO'
    ELSE '❌ INATIVO'
  END AS situacao
FROM mapa_revendas
ORDER BY ativo DESC, nome_revenda;
