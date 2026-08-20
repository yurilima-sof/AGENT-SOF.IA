-- =============================================================================
-- database/seed_completo.sql - Povoamento Completo do Banco (Revendas + Tuya)
-- =============================================================================
-- Executar no container Docker PostgreSQL:
-- docker exec -i agente_sof_db psql -U agente_user -d agente_sof_db < database/seed_completo.sql
-- =============================================================================

BEGIN;

-- 1. Garante colunas e restrições necessárias
ALTER TABLE mapa_revendas ADD COLUMN IF NOT EXISTS tuya_home_id VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_mapa_revendas_home_id ON mapa_revendas(tuya_home_id);

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_tuya_homes_sigla_home') THEN
        ALTER TABLE tuya_clientes_homes ADD CONSTRAINT uq_tuya_homes_sigla_home UNIQUE (sigla_cliente, home_id);
    END IF;
END $$;


-- 2. DADOS DE GRUPOS WHATSAPP (mapa_revendas)
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
    "freezer": "https://maker.ifttt.com/trigger/0019_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0019_esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0019_off/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363401204481216-group',
  'Revenda 0047',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0047_Esfriar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0047_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0047_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363298127856818-group',
  'Revenda 0016',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0016_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0016_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0016_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363279998161437-group',
  'Revenda 0020',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0020_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0020_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0020_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363199036541250-group',
  'Revenda 0002',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0002_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0002_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0002_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363282476786392-group',
  'Revenda 0021',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0021_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0021_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0021_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363279978711780-group',
  'Revenda 0009',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0009_Freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0009_esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0009_off/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363281098848004-group',
  'Revenda 0018',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/0018_freezer/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": "https://maker.ifttt.com/trigger/0018_Esquentar/with/key/SUA_CHAVE_IFTTT_AQUI",
    "off": "https://maker.ifttt.com/trigger/0018_OFF/with/key/SUA_CHAVE_IFTTT_AQUI"
  }',
  true
),
(
  '120363422455765261-group',
  'Grupo Thiago (Teste)',
  'XX',
  '{
    "tipo": "ifttt",
    "freezer": "https://maker.ifttt.com/trigger/thiago_on/with/key/SUA_CHAVE_IFTTT_AQUI",
    "esquentar": null,
    "off": "https://maker.ifttt.com/trigger/thiago_off/with/key/SUA_CHAVE_IFTTT_AQUI"
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

-- 3. HOMES E CENAS TUYA (tuya_clientes_homes / tuya_clientes_cenas)
-- Script Gerado Automaticamente para inserir Homes e Cenas da Tuya

INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('18fb4147-a71c-4f2d-9dbe-a081b000b2f3', 'pe', 'az1758205559313AAFQn', '265054363', '[SOF] Testes') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d77106b8-a9ee-44fb-9d48-646b615bfec8', 'pe', '265054363', 'T-HIGH', 'mY1294TSxGYNVxIV', 'T-HIGH', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ee51fe3a-f145-4e99-8b48-53924cef3f20', 'pe', '265054363', 'T-MEDIUM', 'sshzr0QvAbeQ735O', 'T-MEDIUM ', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1caa7d70-112d-453d-8cae-0d5b46a7b300', 'pe', '265054363', 'T-OFF', 'DMGOA4ACoaJTWUKf', 'T-OFF', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('70fd791c-2e37-4288-8e85-dd9c73b3ed3b', 'pe', '265054363', 'T-LOW', 'oA32iJuJZIegKuZo', 'T-LOW', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('0da9f3cd-0ac3-4e03-992f-6701e933fe00', 'pe', 'az1758205559313AAFQn', '204511269', '[Recife/PE]Escola Conecta') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3fa094e5-3b04-4eba-91c8-52643320a725', 'pe', '204511269', 'Desligar tudo', 'uybvmw05sX8O1obS', 'Desligar tudo ', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('fa06c8ef-5918-47ae-b167-04515f25e8bc', 'pe', '204511269', '0001 SL 08', 'ECe8CXzRkhk2U4cJ', '0001 | SL 08 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f47ba99f-1098-4c17-8351-5e6a830ad199', 'pe', '204511269', '0001 SL 08', 'SLwguCywEUIuzRnS', '0001 | SL 08 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('440f7721-0e23-4324-b8c7-047c23dd5eee', 'pe', '204511269', '0001 SL 09', 'nxmyHyKRtSPlvrmc', '0001 | SL 09 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9b0c011a-53fa-4256-8dc0-4f5f3c64d4b4', 'pe', '204511269', '0001 SL 09', 'ssJ0rHZrOyeKieD5', '0001 | SL 09 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9e5808c6-269a-48f5-b647-386cf2144fd5', 'pe', '204511269', '0001 SL 11', 'zqPevNxdUAu9Aaq8', '0001 | SL 11 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('839d32e1-bfb9-4bf5-b036-e4c7e83136a6', 'pe', '204511269', '0001 Sl 11', 'kQCE9jDn2nDtz7LC', '0001 | Sl 11 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('750b0ec4-cb2c-4df9-885b-a8e68c4d0797', 'pe', '204511269', '0001 SL 12', 'sGvk1wAglZ6w1dl8', '0001 | SL 12 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('353f6270-3333-4615-a8a9-2597cb38b5c6', 'pe', '204511269', '0001 SL 12', 'dyeja6ziU9VKA9Qf', '0001 | SL 12 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7bbeccec-ed98-4f6a-af53-2e124cbc3fef', 'pe', '204511269', '0001 SL 13', 'yr3xXt6SxU9dgRxB', '0001 | SL 13 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('45fa89ba-b4db-497f-b54a-ddc2221626e4', 'pe', '204511269', '0001 SL 13', 'XPheGVcKnMzSL1wA', '0001 | SL 13 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f5a416c6-4244-4c50-baad-6f32e6602d84', 'pe', '204511269', '0001 SL 13', '6U0GkBfxAb5u2l9J', '0001 | SL 13 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('97633857-c933-448f-a36b-1c8f0d4d78bf', 'pe', '204511269', '0001 SL 13', 'L7CprzCAgjYlAL9b', '0001 | SL 13 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6ff7a9dd-f10e-4e92-8de8-62a8a01d2508', 'pe', '204511269', '0001 SL 14', 'NoG6Md0sBd9pLaxJ', '0001 | SL 14 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4368b182-1543-4d95-994f-e16e2c54b1c2', 'pe', '204511269', '0001 SL 14', 'rEcjiGHrUuxFkE8v', '0001 | SL 14 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('beae24dd-c7e4-46ae-93d3-51d02ef655f6', 'pe', '204511269', '0001 SL 14', 'xSOxRje1ibu29gDW', '0001 | SL 14 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('acfa0790-b45b-4fbf-8a75-95928b4c76ea', 'pe', '204511269', '0001 SL Professor', 'cNBJNlOmNPYPV5Gj', '0001 | SL Professor | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3e1cf072-116e-41a6-a503-3aecdec2ae8f', 'pe', '204511269', '0001 SL Professor', 'mkNTF7sdBLmmCyLg', '0001 | SL Professor | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bef1ccc4-36f2-4767-83ca-988bb250b7f2', 'pe', '204511269', '0001 SL 18', 'IsWmeCIjj4Sfpdvv', '0001 | SL 18 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d4149820-e0e9-4edf-a137-51b40a746ddc', 'pe', '204511269', '0001 SL 18', '11455r2dgVCYchd9', '0001 | SL 18 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('645b9ce9-d0db-4d5a-b0a4-f482c3940f02', 'pe', '204511269', '0001 SL 17', 'usTqWajEkYqTVF0u', '0001 | SL 17 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d3aebf07-780d-41c0-a3ed-fc6ab02119cf', 'pe', '204511269', '0001 SL 17', '2ao49kG9BSeRgrdf', '0001 | SL 17 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3a63b64e-5f54-4a6e-9abc-b9cd03cd11f6', 'pe', '204511269', '0001 Sl Professor', 'BGpBkzY78S8S37MQ', '0001 | Sl Professor | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bbe7e10c-95fc-4835-b8d4-6132a7fdc9b9', 'pe', '204511269', '0001 Sl Professor', 'rKBMwHTFClOju2Z6', '0001 | Sl Professor | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('19b374e7-872a-487a-b19c-26bf3d0511f9', 'pe', '204511269', '0001 SL 14', 'leYoNuOyrZLxK9Ct', '0001 | SL 14 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('76193280-3b27-469c-90c7-d978a446a7ba', 'pe', '204511269', '0001 SL 14', 'lCVhWwBp5VR0o5FN', '0001 | SL 14 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('17aee5d8-af67-4233-bf9d-27ac537ef900', 'pe', '204511269', '0001 SL 08', 'HLvGmTDxzgwP3WRC', '0001 | SL 08 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d7e5b28a-aeda-43bf-87e5-e2070d5d9dde', 'pe', '204511269', '0001 SL 08', 'd9vsDKrQUGglqAWE', '0001 | SL 08 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('15e39ed0-e5bf-4860-a20a-4b06c8b95e99', 'pe', '204511269', '0001 SL 09', 'KqreoIhvqwMnGMah', '0001 | SL 09 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e03948dc-0d0f-4fae-a9f2-6a3a883d38b6', 'pe', '204511269', '0001 SL 09', 'DIldav7bEAh1spIR', '0001 | SL 09 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a9f37503-f957-404b-9cfc-6a4d7a3ae0ee', 'pe', '204511269', '0001 SL 11', 'p1SocvNzBpQwPkBl', '0001 | SL 11 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6be6d48e-d054-4124-bf49-40c015a70d25', 'pe', '204511269', '0001 SL 11', '9FDZDdvBAfaF29hg', '0001 | SL 11 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6170595e-2568-45a2-9005-d0a437e2438a', 'pe', '204511269', '0001 Sl 12', 'cvmmINL528Z1UQGQ', '0001 | Sl 12 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e0abb6e9-be53-4325-924b-14e0f1f88193', 'pe', '204511269', '0001 SL 12', 'fBaS3zBzgBDuWdF9', '0001 | SL 12 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1c1e4258-58b0-414a-b008-4587a581ee2d', 'pe', '204511269', '0001 SL 18', '0qLcu9APK5eAHtc3', '0001 | SL 18 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a031fe23-be32-4ab2-b2c1-0b4baa0e6ea6', 'pe', '204511269', '0001 SL 18', '4icw62n9k3FV6YkV', '0001 | SL 18 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c33e975b-0102-4e7a-90c1-85912c3c84cf', 'pe', '204511269', '0001 SL 17', 'AdhHKY0jjx4tTvPX', '0001 | SL 17 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a2ff06a9-4035-4496-b0bb-463323545d59', 'pe', '204511269', '0001 SL 17', 'k4tGh1IvQyOj9BeM', '0001 | SL 17 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e5de042e-3c8c-4421-92b7-419d7b795df6', 'pe', '204511269', '0001 SL 03', 'vbyJblXBU4oqMEK0', '0001 | SL 03 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('386b3900-a644-4234-acb7-1725c6dbd605', 'pe', '204511269', '0001 SL 03', 'm4PPVliEekRaAVsy', '0001 | SL 03 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b866c779-afd1-4ab1-8696-4a5f61ba60ec', 'pe', '204511269', '0001 SL 04', 'vTMmf0vfEsTIFIIH', '0001 | SL 04 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9414832a-c9bd-4b30-8d54-23605cf53a7d', 'pe', '204511269', '0001 SL 04', 'T7V4JeAk34anTV04', '0001 | SL 04 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('76bc887d-63fc-404e-9a21-145a07ef21a0', 'pe', '204511269', '0001 SL 04', 'Ube8O2MGhAEgB9sn', '0001 | SL 04 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e02137ee-f953-46f3-8939-de927c096948', 'pe', '204511269', '0001 SL 04', 'obkGe9JvCYdttGMF', '0001 | SL 04 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('42ed394b-831d-4816-882b-37394a84f432', 'pe', '204511269', '0001 SL 03', 'aHbR7AK80JKKZPqb', '0001 | SL 03 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('45946432-cada-4d20-8380-70141bc701a8', 'pe', '204511269', '0001 SL 03', 'dbmsoD5UASwJBEc2', '0001 | SL 03 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d91f9d93-b6bc-44eb-91de-bfb9c0c7567b', 'pe', '204511269', '0001 SL 16', 'xzJKXwAEqPwB4Rj8', '0001 | SL 16 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a82b9ebc-0838-46ed-9ec4-95c096693de5', 'pe', '204511269', '0001 SL 16', '9WkbrLpvfq9zLy1G', '0001 | SL 16 | 22°C', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1106833f-bbb9-46d6-a8f8-75c842e26781', 'pe', '204511269', '0001 SL 16', 'pAv0WjZU3tArReKT', '0001 | SL 16 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('fdc9a061-7b17-464c-b11e-8faeded33332', 'pe', '204511269', '0001 SL 02', 'iVXfup8fH0Bn4pCV', '0001 | SL 02 | 25°C', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5e0abdfb-e63e-476b-adfb-2d10214825b7', 'pe', '204511269', '0001', 'LvpHoo5qAxmlF55K', '0001 | Desligamento Total', 'desligamento total') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('94fd0c66-b954-494d-9c9c-2cd2fcf3f617', 'pe', '204511269', '0001 SL 16', 'GERKdmcCPkV0KLFa', '0001 | SL 16 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('642dc40f-70c1-4af9-ae4b-19bfb7441bcf', 'pe', '204511269', '0001 SL 01', 'rfwA9dwXhlHdHDNl', '0001 | SL 01 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('86bcef30-99ef-4e13-b808-b6e12e60b2e3', 'pe', '204511269', '0001 SL 01', 'UwoWDj1JUdXPpA9U', '0001 | SL 01 | 25c', '25c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4ab8756f-5f22-4860-a9f1-414ffb157d0e', 'pe', '204511269', '0001 SL 01', '07VGFaAHdSvwmguS', '0001 | SL 01 | 22c', '22c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7214b54a-11e7-42fe-8e8e-62077ab56b0c', 'pe', '204511269', '0001 SL 01', '2kGZ8BXkhObVySrn', '0001 | SL 01 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('00c0486b-8fd9-4c88-bb91-96156dacd55b', 'pe', '204511269', '0001 SL 02', 'Ae8pvhy4gHQfmjGs', '0001 | SL 02 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c6a13148-d0b9-44b9-8392-69e3dd8f8a04', 'pe', '204511269', '0001 SL 19', 'nJoUjUCKt9nDTYuV', '0001 | SL 19 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2e216b75-2c74-4e53-956a-7dbf6bddd4af', 'pe', '204511269', '0001 SL 19', 'W8fdSKlZd6z5jlLF', '0001 | SL 19 | 25c', '25c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('85776b6c-beb8-4ded-baff-3f38d5e8203a', 'pe', '204511269', '0001 SL 19', 'GyEAb6Txa5PbTnRB', '0001 | SL 19 | 22c', '22c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7a70c43b-c300-46b2-89ea-4fcc7720ba10', 'pe', '204511269', '0001 SL 19', 'v9eIFvHeI9g61Dsd', '0001 | SL 19 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('18fff39f-a1fa-4e27-a6c7-668cde91b513', 'pe', '204511269', '0001 SL 02', 'auWX1HjAnjghc9NI', '0001 | SL 02 | 22C', '22c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ad8e64c9-f9c9-4ac7-a7c7-c3f5fed0927d', 'pe', '204511269', '0001 SL 02', 'bdqzmJ9u47QInjxs', '0001 | SL 02 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('742ce820-ae44-4fa2-9683-7694084ecb4d', 'pe', 'az1758205559313AAFQn', '225599627', '[Recife/PE] BYD BV') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('827b2533-9345-4dc0-9237-f0f950220887', 'pe', '225599627', '0020 SHNV', 'qPMAtb4A1Izp0o7G', '0020.T-HIGH.SHNV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('283ca16c-c51c-47cd-8a62-3a98de464615', 'pe', '225599627', '0020 SHNV', '2xBAz80peYxjebBD', '0020.T-MEDIUM.SHNV', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4400e8a1-c445-4994-bacd-806e708ac7ae', 'pe', '225599627', '0020 SHNV', 'DPXMD63insLmFfZF', '0020.T-LOW.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('426ee9f3-a534-4d39-bdc1-4dd761b3d3f4', 'pe', '225599627', '0020 Freezer', 'Xr7wEjcAlqpIb9kT', '0020.Freezer', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('42371328-8920-4e80-8cff-90f3a38803bb', 'pe', '225599627', '0020', 'c0zcJNjuHXXAPBmd', '0020.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('eb46bfcc-283c-45de-bf43-42d15edde457', 'pe', 'az1758205559313AAFQn', '225764371', '[Recife/PE] Toyolex RB') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d0c12cbb-14a5-4580-bdbc-b0dcc257a743', 'pe', '225764371', '009 Freezer [ALL]', 'At3G3CgNryqauaUH', '009.Freezer [ALL]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6d8d0914-8bc3-4ad9-b592-d92628f9c7a1', 'pe', '225764371', '0009 E C', 'dxBpIhJqpaNzyCEk', '0009.T-HIGH.E.C', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8c117dbd-1b88-43db-95a2-321f2a9bf7f2', 'pe', '225764371', '0009 E C', '3k2AldwEFuQQCm9Y', '0009.T-LOW.E.C', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('55e99a1c-2272-4441-b0d6-f728af145ce0', 'pe', '225764371', '0009 RS', 'sgrzxqwt51ZpdGNE', '0009.T-MEDIUM.RS', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c7cd9203-891d-4ffd-9922-b451d5683afc', 'pe', '225764371', '0009 RS', 'sJmPZGUvXduMaEXB', '0009.T-LOW.RS', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('63ec41e9-f110-4383-a2a1-ac25bf3a6405', 'pe', '225764371', '0009 SHNV', 'UnXwFxKNxy9Cb6BJ', '0009.T-HIGH.SHNV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('16f7a1a9-7d1c-4b25-bd26-6eca3467e925', 'pe', '225764371', '0009 T-MEDIUM [ALL]', '6Tc2INE3EAVEez9s', '0009.T-MEDIUM [ALL]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a44a478c-0046-4543-88ec-b98166cbdb70', 'pe', '225764371', '0009 SHNV', 'AOZQ8WWReI6PjYGx', '0009.T-LOW.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('167c4468-e4ba-4273-a73e-206d887a8f94', 'pe', '225764371', '0009 Freezer SHNV', '3wIUpSzkfhFhS7bd', '0009.Freezer.SHNV', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a960ec05-ca07-4bca-9263-3fa9cabfef8f', 'pe', '225764371', '0009 Tudo', 'BkAtVH6aSpUJJ8se', '0009.OFF.Tudo', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8d60f70e-cfd6-48fb-b3f4-1cd7ce239bf7', 'pe', '225764371', '0009 RS', 'Dv4jHLUTXCP1tRmH', '0009.OFF.RS', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('dbfbe851-5a05-4700-96b4-60291a9600ca', 'pe', '225764371', '0009 SE', '9QwN7DZxLSodA06W', '0009.OFF.SE', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('98ca11c5-43a2-4cd1-b1d9-9267f7e4079b', 'pe', '225764371', '0009 Freezer SE', 'stNwI7RLJ1Xu9TXy', '0009.Freezer.SE', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('d533bd07-ff44-4efc-91de-84a20a70a21c', 'pe', 'az1758205559313AAFQn', '230905042', '[Recife/PE]Toyolex Afog.') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('45f6a92e-666c-4c1d-90ed-63fb5bade3a5', 'pe', '230905042', '0018', 'kBiKvWpbztTWJAu7', '0018.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('76a9ef7b-9dc9-467e-80df-09033a59513a', 'pe', '230905042', '0018', 'LGDA1sMhzyLdI1P1', '0018.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('665658e9-836c-46e3-b018-2a6e23e699cc', 'pe', '230905042', '0018', 'tOjYnzeiMNfKzbZ6', '0018.T-MEDIUM ', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6c5bc6e6-7e41-4f66-b86a-b437ff619fb5', 'pe', '230905042', '0018', 'qMGbnIYddX48QaLC', '0018.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('934a1358-f560-44e5-8085-9ca0131da2f9', 'pe', '230905042', '0018 TUDO', 'ckmP4iATNakP0bjL', '0018.OFF.TUDO', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('5226a984-acea-4249-99ea-b38d0814402b', 'pe', 'az1758205559313AAFQn', '231567691', '[Recife/PE] Jeep RB') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7b20519a-d6e2-4405-a237-024897e9c135', 'pe', '231567691', '0019 Freezer[1]', '8UtUfFTDxPxg65II', '0019.Freezer[1]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b37913bb-15f7-42aa-ad39-be605674f4dc', 'pe', '231567691', '0019 SHNV', '2AYaG8urf7iCgxAQ', '0019.Freeze.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a3093af6-597d-4ef3-9f37-b2cb81e1fd16', 'pe', '231567691', '0019 [1]', 'nQi65nFl1wO5ANS9', '0019.T-HIGH.[1]', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2b592abf-7f80-48d9-98c0-61d17494f2ce', 'pe', '231567691', '0019 SHNV', 'sqW9zVSMjQygi644', '0019.T-HIGH.SHNV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d70147b0-fcda-4ed7-a574-ab3e4ee3af5f', 'pe', '231567691', '0019 T-MEDIUM[1]', 'Yr4ei1OiXsUc33gi', '0019.T-MEDIUM[1]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f519e464-b3a1-491e-b6d3-eb59eb18a9cd', 'pe', '231567691', '0019 SHNV', 'DRkeC1pXFGclPMPA', '0019.T-MEDIUM.SHNV', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0b7b57fc-e8fb-40cb-a287-05dddd696cb2', 'pe', '231567691', '0019 [1]', 'ChofZ0oI83QEajoz', '0019.T-LOW.[1]', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ecc954ca-02bd-4364-8d32-00bb67ee72a1', 'pe', '231567691', '0019 SHNV', 'U7a0MgB6HqSItfdu', '0019.T-LOW.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e9865a75-fa70-4192-be02-3a54db97dbc5', 'pe', '231567691', '0019 SHNV', 'AvyGjDli8eITPklt', '0019.OFF.SHNV', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('09889d29-5511-4338-a2f1-e96ec43b7137', 'pe', '231567691', '0019 OFF [1]', 'Aw4yIKqWrTA2RTkV', '0019.OFF [1]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('98d9a83c-2456-4b15-87a4-67702f952509', 'pe', '231567691', '0019 SHNV', 'SzUimVdPLxzeMtlE', '0019.OFF.SHNV', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('5a6161a3-211e-43c1-add1-ce0e0751fccc', 'pe', 'az1758205559313AAFQn', '235796633', '[Recife/PE] Bremen BV') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b141f56f-3c62-4ca4-8dfd-b5e3fae499b8', 'pe', '235796633', '0021 FREEZER', 'TJ1cm57bDxureZbG', '0021.FREEZER', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5c9f48b0-ae69-4322-b65b-faaf0c6811fa', 'pe', '235796633', '0021 SHNV', 'tbpejAAJfZ5Peqk4', '0021.T-HIGH.SHNV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d159c990-6b57-43ce-a16f-eab96ecd17d4', 'pe', '235796633', '0021 SHNV', 'XfEu0Shbsh8A5SVD', '0021.T-MEDIUM.SHNV', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7d1be2fc-da89-4e5b-b894-97fc17d08d15', 'pe', '235796633', '0021 SHNV', 'x9bQGfaXnisABW0D', '0021.T-LOW.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c78b82dd-2340-467e-b204-5da122b5c631', 'pe', '235796633', '0021', 'eStVYARjuo52wo7s', '0021.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('55bd7768-14b0-416a-9554-5b39913e59e6', 'pe', 'az1758205559313AAFQn', '235802587', '[Recife/PE] Toyolex Imb') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('255fa4aa-9e87-400b-b253-173e94e58290', 'pe', '235802587', '0016', 'UoX1KmMY4io5mqfK', '0016.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('206b7ae2-8369-4aa0-856c-2d7f13b56bf6', 'pe', '235802587', '0016 OFF [16:00]', 'a4UC6RoMLT0zI5hT', '0016.OFF [16:00]', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4813cf64-6b4b-4b30-b6e8-c9ed4048d491', 'pe', '235802587', '0016', 'XSUAIADTindb7F0D', '0016.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d196efd5-72c8-4c22-b6c4-6c1b1071cced', 'pe', '235802587', '0016', 'f2blqlwSdIunxO6x', '0016.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7a7f931f-8104-462b-b27b-77ce3335a0bb', 'pe', '235802587', '0016 Frezzer', 'HsRJSXd9fZsRpp21', '0016.Frezzer', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('029673db-733a-4c0c-85db-651dc43aff87', 'pe', '235802587', '0016 TUDO', '6ExTgr8ufXrfMWDH', '0016.OFF.TUDO', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('c55cf936-7688-4fef-95c0-2a333e9f7de5', 'pe', 'az1758205559313AAFQn', '235806128', '[Recife/PE] Lexus Imb') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ca2cf0c8-70a4-4671-8573-a6960e31a55d', 'pe', '235806128', '0017 SHNV', 'bgEAfIDhncESFaUm', '0017.OFF.SHNV', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b4a0450f-5743-4d29-9876-3268cc347195', 'pe', '235806128', '0017 SHNV', 'nX7yIZCzaByt1A3Q', '0017.T-HIGH.SHNV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a0e81d4b-b22e-43df-85cb-cad03dc0f7c1', 'pe', '235806128', '0017 SHNV', 'd41KHVzitmmKQcgG', '0017.T-LOW.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c5ee575c-3a59-4b46-9ae3-79899d4fcfac', 'pe', '235806128', '0017 SHNV', '2oHi3C6RpLXzZmcM', '0017.T-MEDIUM.SHNV', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f079e7f4-9ed6-49cc-9c97-548315464203', 'pe', '235806128', '0017 Freezer SHNV', 'hne4X9ogqrOWLBgE', '0017.Freezer.SHNV', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('20d37a8a-0933-4ddc-860f-1d97d93dcd68', 'pe', 'az1758205559313AAFQn', '258999508', '[Recife/PE] Auto Oriente') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('70b38019-847b-4155-8a72-818373e8b4cd', 'pe', '258999508', '0002', 'Z15fLHi0wGTxUrKU', '0002.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2622672e-34fc-4be0-a795-7ae46d062096', 'pe', '258999508', '0002', 'yqK4WyC6NFVZK799', '0002.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('dafd4f3f-f2a6-4ba9-8fa5-63e940ce7c49', 'pe', '258999508', '0002', '7Vz9qGk68yOsblKR', '0002.HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5df5b505-9ac6-4f8b-9f0d-5a04e3507b8e', 'pe', '258999508', '0002', 'cwY1zLn5qXdSwTAZ', '0002.LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('00265869-3840-4d41-ac4f-89a199fe16cc', 'pe', '258999508', '0002', 'tniDurUp9Ukb2jiv', '0002.MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('8db3654c-c6a5-457f-8b74-05b920884e90', 'pe', 'az1758205559313AAFQn', '213540661', '[Recife/PE]Escola Motivo1') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d96fd9ef-c58a-40f5-bf81-818d30bd8b49', 'pe', '213540661', 'P Med Sala 23 - Esquentar', 'MEFCYMuyf7K5jo5c', 'P.Med Sala 23 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('366b7ca4-e076-4697-b9ae-25b92be62a8e', 'pe', '213540661', 'P Med Sala 23 - Esfriar', 'zvRmdPmppiGhFeaA', 'P.Med Sala 23 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a5195f59-26ea-47b4-abbe-d32394a0f730', 'pe', '213540661', 'P Med Sala 22 - Esquentar', 'OGnmD1M3lsGu1fpy', 'P.Med Sala 22 - Esquentar ', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c32db51d-bc75-402f-a9b0-8500363445f8', 'pe', '213540661', 'P Med Sala 22 - Esfriar', 'STsI8GG6iaU36P3U', 'P.Med Sala 22 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c6107df1-3c96-477a-a4a0-ff15161f14a1', 'pe', '213540661', 'P Med Sala 20 - Esquentar', 'W48PQaYYQibWrmQv', 'P.Med Sala 20 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('562aecb0-28ee-4773-bde9-8489a415522e', 'pe', '213540661', 'P Med Sala 20 - Esfriar', 'AWqY8r22sBTw5pwH', 'P.Med Sala 20 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7d75e6d6-3643-4f8a-876c-f4fdaf240620', 'pe', '213540661', 'P Med Sala 20 - Desligar', 'Pwh6SgsKWo5gTCAY', 'P.Med Sala 20 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7802bbb7-650b-4067-a611-873586327503', 'pe', '213540661', 'P Med Sala 21 - Esquentar', 'cKkeGhUEqoBNAPCT', 'P.Med Sala 21 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('352e3039-f2b7-4472-9442-14088fedba6f', 'pe', '213540661', 'P Med Sala 21 - Esfriar', 'Zs0dj987faVcsYYH', 'P.Med Sala 21 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('59aac446-59f2-4554-b699-a14a8e540918', 'pe', '213540661', 'P inf SL26 Esquentar', 'ArF6KbsgaTjYnIKf', 'P.inf SL26 Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('996ff012-73ef-49de-9341-520725295bed', 'pe', '213540661', 'P inf SL26 Esfriar', 'MQAd8H1tANBqrS47', 'P.inf SL26 Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('42ae9566-14d2-47be-a648-354866d7ef76', 'pe', '213540661', 'P inf SL26 Desligar', 'LR2QNbqlMdn7xjwz', 'P.inf SL26 Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3b0978f4-4fc2-44e5-9d53-cf785d74b1d2', 'pe', '213540661', 'P inf SL26 Ligar', '88I5IKdjvuSA1wWx', 'P.inf SL26 Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0e52a65e-8a92-4589-a42a-77d6c8c71b75', 'pe', '213540661', 'P Med Sala 18 - Esquentar', 'eGStgt1EGkWwKMaw', 'P.Med Sala 18 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d55f5ce6-0614-4138-8894-43cf1e05d70f', 'pe', '213540661', 'P Med Sala 18 - Esfriar', '6TWAmBPQCUvPlvaI', 'P.Med Sala 18 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('42bfe8af-7d30-4af0-8ce1-2b7749eeec18', 'pe', '213540661', 'P Med Sala 17 - Esquentar', 'bSYKn7ziPG0mzpWo', 'P.Med Sala 17 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a9720ae4-c3ad-4854-b1d7-b6109e9f8f55', 'pe', '213540661', 'P Med Sala 17 - Esfriar', 'BUFWOfcPGQF8mZ7Y', 'P.Med Sala 17 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0715e38d-bf7b-43a3-8503-2c743cf1b260', 'pe', '213540661', 'P Inf Sala 12 - Esquentar', 'cbaAl3sTLFS0ANNq', 'P.Inf Sala 12 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b5a58f7c-4c22-4d72-bd18-8a63936bbeff', 'pe', '213540661', 'P Inf Sala 12 - Esfriar', 'pjnWdq24oD3wO9jj', 'P.Inf Sala 12 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3225b978-10c3-446d-b504-55e58972f8b0', 'pe', '213540661', 'P Inf Sala 08 - Esquentar', 'wb6UpXrKJjHLIFnA', 'P.Inf Sala 08 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c92f10a7-daf1-4296-9ef7-5c77b10efda0', 'pe', '213540661', 'P Inf Sala 08 - Esfriar', 'aNl0soy7PwQOczAm', 'P.Inf Sala 08 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2a22afab-d914-4c66-8ba1-64593b3184cb', 'pe', '213540661', 'P Inf Sala 05 - Esquentar', 'cmc24nfqvDbwxBoA', 'P.Inf Sala 05 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('cab96bcd-2c1b-4a88-a1fc-f58fd704c21c', 'pe', '213540661', 'P Inf Sala 05 - Esfriar', 'P95CPR05UcilAb3b', 'P.Inf Sala 05 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c5c3b77f-209a-4b46-89ba-4fff251f8bae', 'pe', '213540661', 'P Inf Sala 03 - Esquentar', 'PYQZSL0bAkPkxz8m', 'P.Inf Sala 03 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c6ac6a3e-5603-497c-a9ec-3769f3475cd5', 'pe', '213540661', 'P Inf Sala 03 - Esfriar', '8AjgAxaEyi8jUofj', 'P.Inf Sala 03 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('93a9a70c-f43a-411d-9ac7-6815b6f410ae', 'pe', '213540661', 'P Inf Sala 02 - Esquentar', 'N0EV8KaTNHWNodSn', 'P.Inf Sala 02 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('cc844155-e136-48c6-a064-00d595e4adc1', 'pe', '213540661', 'P Inf Sala 02 - Esfriar', 'UlYDlJWvzDBALOly', 'P.Inf Sala 02 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('03a2074b-0ba0-4f3e-9cf6-f1376aaf50c1', 'pe', '213540661', 'P Inf Sala 01 - Esquentar', 'lJcKa9jCULcRzkI7', 'P.Inf Sala 01 - Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d6846cad-b836-4ab2-b2c6-0a8dbfdbe92d', 'pe', '213540661', 'P Inf Sala 01 - Esfriar', '4KWAa3lsdrZXE5RB', 'P.Inf Sala 01 - Esfriar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f4ae6bae-bb4b-4652-8209-b80f95508d78', 'pe', '213540661', 'PINF SL15 Esquentar', 'gvx7lbQOHAoz2mYG', 'PINF SL15 Esquentar', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7869b362-ca1e-4af0-8d9c-d5bab197da5a', 'pe', '213540661', 'PINF Sl15 Esfriar', 'D7xXsrdwjnarveek', 'PINF Sl15 Esfriar', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('82ac77a9-fa07-4458-b76c-b6f247f6728a', 'pe', '213540661', 'PInf SL15 Desligar', 'UW45yPNlMtwNCmHO', 'PInf SL15 Desligar', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a017af3b-d242-4c59-ab2a-9394ef1e102d', 'pe', '213540661', 'P Inf SL15 Ligar', 'sAdmySaAxiytiJIp', 'P.Inf SL15 Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('990b22db-0473-439f-80dc-1b0b2b6669ab', 'pe', '213540661', 'P.inf SL07', 'I4bRR23Jcrp1Keq8', 'P.inf SL07 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ee98c28a-888b-407f-a7ad-b22a662d8718', 'pe', '213540661', 'P.inf SL07', 'afaWdJvypXvh1znX', 'P.inf SL07 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4788ed1e-27ea-4621-97f3-809998c962a9', 'pe', '213540661', 'P.inf SL07', 'cmocUKTLB5hAAlKU', 'P.inf SL07 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5b328c42-9697-439c-8e7c-8c7b7977b235', 'pe', '213540661', 'P.Inf SL07', 'WV7EAg2jVDdQ8qyb', 'P.Inf SL07 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e582b722-14ad-4272-942b-f4a1d2eb0407', 'pe', '213540661', 'P.med SL26', 'ZYIuM4KX0i76OJuS', 'P.med SL26 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f077762a-5212-4b97-92b3-f80a830ba946', 'pe', '213540661', 'P.Med SL26', 'UJJKQEKsn8YfIpAU', 'P.Med SL26 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f051c1f0-9b24-43b6-b3eb-7997f2d73653', 'pe', '213540661', 'P.med SL26', '6kpH5US089iwcxeQ', 'P.med SL26 | OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0a6063cc-d447-4151-953b-ca543b42a293', 'pe', '213540661', 'P.Med SL26', '2VT6LozaHmOwto81', 'P.Med SL26 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b4d46c13-385f-4209-b7de-5246c944dc1a', 'pe', '213540661', 'P.med SL34', 'zDUbdr0mYLfQkQXv', 'P.med SL34 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('84cb901a-165c-4f96-9e74-9458520fb51a', 'pe', '213540661', 'Pmed SL34', 'JvpLALBqYAGPzjlF', 'Pmed SL34 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('fbe9dafa-12c8-4bc2-9e1b-fb1444337a1f', 'pe', '213540661', 'P.med SL34', 'mFKJp6EQEYD1ei17', 'P.med SL34 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c4a71718-6cc6-4b73-b0c4-f61790c8aee1', 'pe', '213540661', 'P.med SL34', 'RPGcmzwaI4P7iZyF', 'P.med SL34 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5849b9a4-8e47-417f-b3d2-a4c67b9cbb10', 'pe', '213540661', 'P.med SL35', 'MReGf31JZ83LC9Qx', 'P.med SL35 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('98461f69-de33-4140-86b3-fc19b0c74065', 'pe', '213540661', 'Pmed SL35', 'Ngptew9rwEV7Dvhv', 'Pmed SL35 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bb00e344-fdda-4240-9000-4a4a0724bb5a', 'pe', '213540661', 'P.med SL35', 'YOfE2ERcwcMQI39Y', 'P.med SL35 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('994261a2-b47c-4bc4-aa30-2c46a079ec1f', 'pe', '213540661', 'P.med SL35', 'UktHHWwqhCjKqBwx', 'P.med | SL35 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('13c59a73-403b-4f7d-90b4-86d8c19e79a3', 'pe', '213540661', 'P.Inf SL 22', 'HVhBXUcsKS4uxrXz', 'P.Inf SL 22 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8c5a690d-8ad9-4e72-bae0-7e18f92285ec', 'pe', '213540661', 'P.inf SL 28', 'nSQFtjS60scM1AFT', 'P.inf SL 28 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9c2dc685-a726-4285-8b30-c1f3ea6f0f23', 'pe', '213540661', 'P.Inf SL 22', '4J6CnUPHdae8YdrI', 'P.Inf SL 22 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ad4e1b6e-eaf8-4ff3-bea5-e2ca198e6685', 'pe', '213540661', 'P.inf SL 28', 'APGRN7iGequmILlA', 'P.inf SL 28 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('56775a85-c48e-445f-b59b-833e9d464ef2', 'pe', '213540661', 'P.Inf SL 22', 'eaZAWpzrho8Utwlw', 'P.Inf SL 22 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('56dc72ce-4c5c-46da-9a33-cc278b63fe80', 'pe', '213540661', 'P.inf SL 28', 'ysf1fJAIJ3H5Js06', 'P.inf SL 28 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9d06744b-1357-4cce-8e7e-a80ddb6e2c79', 'pe', '213540661', 'P.Inf SL 22', 'XtgK51zA0ZsIsObZ', 'P.Inf SL 22 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3053628c-8c18-45be-a05f-38e29882a42f', 'pe', '213540661', 'P.Inf SL 21', 'rPDyNpCJubSm7OTs', 'P.Inf SL 21 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('fdbd2065-a4fa-47d2-8465-c31be67c73da', 'pe', '213540661', 'P.inf SL 28', 'uCFlAPR8amz6FxvJ', 'P.inf SL 28 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5595e775-95db-463b-8900-399424e45c62', 'pe', '213540661', 'P.Inf SL 21', 'V8GUnRD1ir6nWXwd', 'P.Inf SL 21 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1a38c01b-2df4-4188-b875-d3d09843ae73', 'pe', '213540661', 'P.Inf SL 21', 'NogU1aume66gXOfY', 'P.Inf SL 21 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1e320faa-6361-4c0d-9971-53b0db60d37f', 'pe', '213540661', 'P.Inf SL 21', 'JzdNzmJxGAujdRVI', 'P.Inf SL 21 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a40f8f6f-dcd9-4bb3-82af-bdb2c34935b7', 'pe', '213540661', 'P.inf SL 29', 'B7nNtsvrgACazFhP', 'P.inf SL 29 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('32afbe49-1f90-422b-87a8-6e5fc7888bbf', 'pe', '213540661', 'P.Inf SL 20', 'dAH8lwUdQ92yoALg', 'P.Inf SL 20 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('98dc712d-c0a6-420a-b68a-ba849143b29e', 'pe', '213540661', 'P.inf SL 29', 'Ncqfe2GJEObhxobv', 'P.inf SL 29 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('23c8c9da-e4ad-4f0b-9cde-a80cccb6dc41', 'pe', '213540661', 'P.Inf SL 20', 'MIG2nfkJzg3ELwtF', 'P.Inf SL 20 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('884f2cf8-b595-4bc3-964d-6e644a560b68', 'pe', '213540661', 'P.Inf SL 29', 'LwBlsWol1ergS73H', 'P.Inf SL 29 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d40de4b8-2dee-4506-8484-c3b2838a81dc', 'pe', '213540661', 'P.Inf SL 20', 'iXgFTW1KF1TALrJR', 'P.Inf SL 20 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a28a6aed-2f9a-4167-a932-5ebe39cf9005', 'pe', '213540661', 'P.Inf SL 20', 'WnfP1ehdn4c6elC6', 'P.Inf SL 20 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bde42372-74f7-4cf6-99a6-6f840dd923d7', 'pe', '213540661', 'P.Inf SL 29', 'A7elUAWQZP9dNrLb', 'P.Inf SL 29 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('00d4d155-0cb5-4d18-b7b0-7cae2b9a383e', 'pe', '213540661', 'P.Inf SL 19', 'wAtFDLCUDKYcqfCL', 'P.Inf SL 19 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('52d62118-77a9-47f6-a50a-c5e9d177bf36', 'pe', '213540661', 'P.Inf SL 19', '4KfyCZZgM3GHwjRg', 'P.Inf SL 19 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('360ea040-78ee-474f-95e6-81fbe93a5967', 'pe', '213540661', 'P.Inf SL 19', '4T0uhkrEl4RjHfBH', 'P.Inf SL 19 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('580c8e87-de4d-445f-bacf-4dbb0a16a770', 'pe', '213540661', 'P.inf SL 32', 'Tgr7jRWpckQIqUF8', 'P.inf SL 32 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('76dee60f-b699-452a-a394-3737007c7fdc', 'pe', '213540661', 'P.Inf SL 19', 'qnd4xHP4Pzv2Avc3', 'P.Inf SL 19 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c033b351-a359-4498-9fd0-211b39763691', 'pe', '213540661', 'P.inf SL 32', '3AB0UpjSEYviQ045', 'P.inf SL 32 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1aecd286-dfbb-4cd2-b206-c2f5ab6c4a5b', 'pe', '213540661', 'P.Inf SL 18', 's894mXBoU8IE9Scb', 'P.Inf SL 18 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8f44a226-695f-4db4-9503-de17018439c9', 'pe', '213540661', 'P.Inf SL 18', 'f2VgzoRsatAzgulV', 'P.Inf SL 18 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9aa99aa9-77a2-4e12-ae06-da95d73c5ad6', 'pe', '213540661', 'P.inf SL 32', 'MBq3e6zRhzAWQYuQ', 'P.inf SL 32 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5c2e7bb1-d2b1-4c90-b1a5-0907e1b877be', 'pe', '213540661', 'P.Inf SL 18', 'gVgplRXmlXbcEgoD', 'P.Inf SL 18 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8df67742-b02b-44c5-bb38-faaf8d2a8921', 'pe', '213540661', 'P.Inf SL 32', 'bqO9Q5FTGgPQT0wQ', 'P.Inf SL 32 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3b682675-477d-4b4c-896b-339110b9032b', 'pe', '213540661', 'P.Inf SL 18', 'qcSIkZyMDkLA0ny3', 'P.Inf SL 18 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0afbda76-a10e-43f7-bf48-bd771cee3c41', 'pe', '213540661', 'P.Inf SL 31', 'joGCg4klkKPgrF0R', 'P.Inf SL 31| 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9c38d6e8-cf01-440c-828e-b5b2a18e01ea', 'pe', '213540661', 'P.Inf SL 17', 'kqTKQOCX5KDUkw7T', 'P.Inf SL 17 | 25°c', '25°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7875bec4-fb08-435c-8126-0d12c24dc0a9', 'pe', '213540661', 'P.Inf SL 31', 'ACgYv1cAyqny0xPX', 'P.Inf SL 31 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('604931bd-13db-47db-8fe0-4c38c90baf92', 'pe', '213540661', 'P.inf SL 31', 'L4FqLGOrmm9sXPWA', 'P.inf SL 31 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c4cce419-f288-439e-812c-3d7f93ebff5a', 'pe', '213540661', 'P.Inf SL 17', 'mbbz0Nmre1rHIt6W', 'P.Inf SL 17 | 22°c', '22°c') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7d90b424-7c6d-4a05-a8cb-05bdb06b2861', 'pe', '213540661', 'P.Inf SL 31', 'iINcTAoWJTzUCAlS', 'P.Inf SL 31 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8699c808-4085-4b77-b314-5e6e6b63b86f', 'pe', '213540661', 'P.Inf SL 17', '1B9y5G8feTkiqCEX', 'P.Inf SL 17 | Off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0f99550e-14fa-4b13-aef3-cb1a938880e5', 'pe', '213540661', 'P.Inf SL 17', 'YjswEHoiD0cf9kT8', 'P.Inf SL 17 | On', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8a11183b-fd40-4b93-9d78-6e51495c72bc', 'pe', '213540661', 'P med Sala 20 - Ligar', 'VQWzsqBfa6SJHEdz', 'P.med Sala 20 - Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4f250d90-dd41-4e0f-b5f1-80df10d29547', 'pe', '213540661', 'P Med Sala 22 - Desligar', '4swej20FXi8sUAX0', 'P.Med Sala 22 - Desligar ', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4f20bec0-7741-415d-803c-ccc4342d7257', 'pe', '213540661', 'P Med Sala 22 - ligar', 'UYWQaA58NtYeJ9WI', 'P.Med Sala 22 - ligar ', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5dffe4ba-44ab-48fd-acc9-1c83f3c8f11e', 'pe', '213540661', 'P med Sala 21 - Desligar', '3u4Om7ZNGkuXT0s2', 'P.med Sala 21 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('37c22869-1ba3-417a-8121-048e3ea23213', 'pe', '213540661', 'P med Sala 21 - Ligar', 'VP1NQpyEopbIYxUJ', 'P.med Sala 21 - Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2d039fc7-f138-4215-a8ca-fa069cd2c847', 'pe', '213540661', 'P med Sala 18 - Desligar', 'FAa9PWlwA5xS789L', 'P.med Sala 18 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7515c212-8add-40df-98d9-ea5fa7400a70', 'pe', '213540661', 'P Med Sala 18 - Ligar', '62C9A4WamGRwG3BB', 'P.Med Sala 18 - Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8ce83753-cc46-42df-94d8-12fc4987b0f9', 'pe', '213540661', 'P Med Sala 17 - Desligar', 'y97s0ZsZKrFmCGoA', 'P.Med Sala 17 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ef85dacd-9cca-41c1-9784-c161d395d47b', 'pe', '213540661', 'P Med Sala 17 - Ligar', 'Ym6A2ZKwDSYnj1hF', 'P.Med Sala 17 - Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('27ef42af-7114-4566-a0e2-ee31e248f3e7', 'pe', '213540661', 'P Med Sala 23 - Desligar', '3ti3wzR8NcpsjqYG', 'P.Med Sala 23 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('46eb34ec-dbdb-48fc-a48e-9cadd8414796', 'pe', '213540661', 'P Med Sala 23 - Ligar', 'NUNa0gfthRowEqAl', 'P.Med Sala 23 - Ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ff68a0bc-441d-4b09-a4bf-f9216a579f21', 'pe', '213540661', 'P inf sala 12 - Desligar', '2dyQeMB56BBhqwAV', 'P. inf sala 12 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('623800fc-2b80-4568-a83b-cadc7e8c0dda', 'pe', '213540661', 'P Inf sala 12 - ligar', 'OySASUSr4TdkLQzM', 'P. Inf sala 12 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0ec49b1c-9f26-492e-8526-891e358a584f', 'pe', '213540661', 'P Inf sala 08 - Desligar', 'UDEDKV9lRk3duP9y', 'P. Inf sala 08 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d68df9b1-abbf-4f87-bdff-97bb6dd18680', 'pe', '213540661', 'P Inf sala 08 - ligar', 'bB38NdhbxxOh8rCA', 'P. Inf sala 08 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2eaf4d77-5971-4517-a052-0baa06749a21', 'pe', '213540661', 'P Inf sala 05 - Desligar', 'AraRLKCq98xO1Cbw', 'P. Inf sala 05 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e96df04a-83ea-4de2-b04d-eddc4e35415c', 'pe', '213540661', 'P Inf sala 05 - ligar', 'gZ9oADTKzbBw2yVk', 'P. Inf sala 05 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7e926315-0edc-479e-8a75-de0f55199396', 'pe', '213540661', 'P Inf sala 03 - Desligar', 'WXjnCyilnBHA5qqD', 'P. Inf sala 03 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2a1227df-4c4f-4528-b1d1-fa6613bf6426', 'pe', '213540661', 'P Inf sala 03 - ligar', 'zsmomhfYSCkiBg9q', 'P. Inf sala 03 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1e2e5b66-d272-4550-821f-5d144b1a5b26', 'pe', '213540661', 'P Inf sala 02 - Desligar', 'sBHfp5XIbXVVMuo8', 'P. Inf sala 02 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8f0bb3b4-a0f5-4b36-b83a-a6d0056f239a', 'pe', '213540661', 'P Inf sala 02 - ligar', 'Mkc3Gu8EcYkfkL8J', 'P. Inf sala 02 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1b5f496b-4aa1-4002-b23b-9d950ec415df', 'pe', '213540661', 'P Inf sala 01 - Desligar', '755BexagngjtRexc', 'P. Inf sala 01 - Desligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('621515a3-4bbf-45d2-abd5-694184f4fb6a', 'pe', '213540661', 'P Inf sala 01 - ligar', 'V2uxMR6R8lwLjdQL', 'P.Inf sala 01 - ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('4ae1696b-167b-4849-a01c-497bcb75aee0', 'pe', 'az1758205559313AAFQn', '252896901', '[Recife/PE]Escola Motivo2') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3a411ecc-f10d-451d-b148-408b9086a01d', 'pe', '252896901', 'P.med SL12', 'csCCPWL9X9McxAgV', 'P.med SL12 |Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4a498cdc-700e-431d-8b1c-c6dc2e2841d2', 'pe', '252896901', 'P.med SL12', 'oJTw9TMZCfdk5Dqh', 'P.med SL12 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5e0d3a56-2106-45da-abc1-285a39c18a99', 'pe', '252896901', 'P.med SL12', 'KrZUaRiSYuotXvTG', 'P.med SL12 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3d32d349-672a-4ecd-a354-5da9142f8e40', 'pe', '252896901', 'P.med SL12', 'AFkOwRd1rYrJ019n', 'P.med SL12 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('eae3b6d9-5956-4068-8ef4-5fc04ccfd09d', 'pe', '252896901', 'P.Inf SL27', 'eR3q7N15HICyCtAd', 'P.Inf SL27 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('09a5cba6-076f-41ca-8454-1174838821dc', 'pe', '252896901', 'P.inf SL27', 'KtNFAS01cUg3Ytin', 'P.inf SL27 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('be9d9978-3a15-4246-8e7b-231c7ab8a52f', 'pe', '252896901', 'P.inf SL27', 'Hy2YKufbEyG3pHbL', 'P.inf SL27 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5e0514ca-8e32-4ef6-9438-2175ce5b6c73', 'pe', '252896901', 'PINF Sl 27', 'eZPkvoGrpKKbWrMu', 'PINF Sl 27 | Ligar', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('11d9d02e-da39-48fe-b195-07e9b492d291', 'pe', '252896901', 'P inf SL10 ligar', 'eOzVQDPPrxIHAWYA', 'P.inf SL10 ligar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e7f3956e-284a-4d46-b917-c80fdbce8c74', 'pe', '252896901', 'P inf SL10 Esquentar', 'diQmiSpwKwKkH4FS', 'P.inf SL10 Esquentar', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('42183e41-db42-48de-8629-e7a27ad88ee8', 'pe', '252896901', 'P.inf SL10', 'cvysDTXJVt4qAvih', 'P.inf SL10 | off', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d0a426da-8098-4fd9-8939-9338cdd6a41b', 'pe', '252896901', 'P.inf SL10', 'rX2FQ99Mo6bAgcbj', 'P.inf SL10 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b9e8fab0-364f-4d12-91d6-8403833cfe81', 'pe', '252896901', 'P.MED SL02', '2ATdrX1ZBEIigAli', 'P.MED | SL02 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('99e033b3-d641-4ffb-8951-e87d3369f776', 'pe', '252896901', 'P.MED SL02', 'ptKKyDbzzcL5d885', 'P.MED | SL02 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3ff71c53-1a6c-4f9b-8094-82149adedd57', 'pe', '252896901', 'P.MED SL02', '2gilNUaAPCWaLKId', 'P.MED | SL02 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f39d9884-0eb2-428a-98ae-d2b3d5fb0da4', 'pe', '252896901', 'P.MED SL02', 'pMYHUINfzpVu2tRy', 'P.MED | SL02 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('0302114d-086f-49bc-9c3d-cf8e5e9f1e33', 'pe', '252896901', 'P.Inf SL23', 'LnyFcBB4Hy2CVe4T', 'P.Inf | SL23 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('66703a3c-d879-4130-92bb-029bed600f29', 'pe', '252896901', 'P.Inf SL23', 'rxFIDiktikp64tu1', 'P.Inf | SL23 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('663e4cff-baa7-474c-acf6-6e64616ca5a2', 'pe', '252896901', 'P.Inf SL23', '0U8mxGM97z7PoZXB', 'P.Inf | SL23 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('161de3e3-9949-4923-93c4-5debbc333f1a', 'pe', '252896901', 'P.Inf SL23', 'qg22fyzC39yDVeII', 'P.Inf | SL23 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2074072e-3813-4cf8-bc93-5c16aeb74bc5', 'pe', '252896901', 'P.Inf SL06', 'BzY0WYhCqkRCZZLq', 'P.Inf | SL06 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5bdff985-15d3-4192-ab06-4df1ef2bae5e', 'pe', '252896901', 'P.Inf SL06', 'dvwkc1SdA0C6lhuU', 'P.Inf | SL06 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4b783dc0-9bd1-43ed-9443-10ad4bee3e12', 'pe', '252896901', 'P.Inf SL06', 'E4rP5Rjfb9sTUkXT', 'P.Inf | SL06 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8801f738-a93d-478d-970e-819d4dd8ef8b', 'pe', '252896901', 'P.Inf SL06', 'kzR2X7p2PqWy3Iwp', 'P.Inf | SL06 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('417e0c5d-5660-4b7e-b973-c363ffa8213f', 'pe', '252896901', 'P.Inf SL09', '1uAgqgRzJXKlhACW', 'P.Inf | SL09 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('14bbd538-e45c-443e-a362-8f77536bff42', 'pe', '252896901', 'P.Inf SL09', 'wLBkO9tClufdV5Fy', 'P.Inf | SL09 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e3b0c1ea-65be-4aa2-a638-ab4bfdacbd29', 'pe', '252896901', 'P.Inf SL09', 'ULxlAZLkPnblcV9A', 'P.Inf | SL09 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('123810fd-b836-4d6a-8ffe-af70eddd3edf', 'pe', '252896901', 'P.Inf SL09', 'pqZEcJ87dvMP948t', 'P.Inf | SL09 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a7deb151-319c-4153-8255-165f661e660e', 'pe', '252896901', 'P.Inf SL11', 'TTnuiTNmofHDyYxy', 'P.Inf | SL11 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('305d6425-ee0b-4e5f-b538-241220706e42', 'pe', '252896901', 'P.Inf SL11', 'ALI8nxpXR7SpIiLe', 'P.Inf | SL11 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d101a7a6-eafd-4fed-81bf-1de4ca06a71b', 'pe', '252896901', 'P.Inf SL11', '2i9lEuDh7Jd7s2a1', 'P.Inf | SL11 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ca42c350-93f2-416f-b038-85fc159c3398', 'pe', '252896901', 'P.Inf SL11', 'KlfBayhNrLa9uvEu', 'P.Inf | SL11 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9fbb9e4b-3b2b-4682-89b0-6ce02671baf3', 'pe', '252896901', 'P.Inf SL14', 'AFgfH4IlhPADMXag', 'P.Inf | SL14 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9d434f2f-dfb8-4880-8c90-eef83121b1ef', 'pe', '252896901', 'P.Inf SL14', 'TkvRMSu9iZVLR92l', 'P.Inf | SL14 | Esquentar', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('62cb5fba-bd79-49fe-91b6-4cc69ab425f8', 'pe', '252896901', 'P.Inf SL14', 'Aip79g5fqT3dgjgc', 'P.Inf | SL14 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('25befb53-1d44-4e31-b80e-d8f251a20191', 'pe', '252896901', 'P.Inf SL14', 'oIRTv2vA1vn4QZ0D', 'P.Inf | SL14 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a93f3e6d-3504-4457-b42f-6eba9b78d6f7', 'pe', '252896901', 'P.Inf SL13', 'Ju2I6ymeDVGyxAqQ', 'P.Inf | SL13 | Esfriar', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f5afd55f-da1e-4e29-8ea4-9bd64ca544e5', 'pe', '252896901', 'P.Inf SL13', 'dOdSdn0ciGprnthY', 'P.Inf | SL13 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a8df967d-8b8d-4674-876b-e58245091f7d', 'pe', '252896901', 'P.Inf SL13', '2jKge4eU7UCmGliA', 'P.Inf | SL13 | Desligar', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3fad2b4d-67cd-40e6-96a2-c39613f1d062', 'pe', '252896901', 'P.Inf SL13', 'SZtNEAvlKN9S3Q6b', 'P.Inf | SL13 | LIGAR', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('33e432e6-3d8c-45f6-80af-22c385810a2a', 'pe', 'az1758205559313AAFQn', '265553041', '[Caruaru/PE] Auto Oriente') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6a308641-027b-4ec1-a742-8c91819efbdd', 'pe', '265553041', '0013', 'QojbpvJKb495pida', '0013.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('241e4c4c-f3a2-4c43-9c31-b0c88a23d371', 'pe', '265553041', '0013', 'nydu7oqcP3utxv5V', '0013.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('216dcdb2-2593-493c-8e74-5225dfe20d59', 'pe', '265553041', '0013', 'lZvAZhwVggilckcl', '0013.LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d8a73b3d-725f-4b1b-a495-73330ba7e30a', 'pe', '265553041', '0013', 'rgI3NQgwZasTr4hM', '0013.MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f23ac3c3-0b5c-443f-808c-37a5e80ff0d9', 'pe', '265553041', '0013', '5HBMWo4UEAkCjU9v', '0013.HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('b6baabf3-0acd-44f2-9fa9-795ebddf7e35', 'pe', 'az1758205559313AAFQn', '265553090', '[Caruaru/PE] AutoNunes') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('24345f75-9209-4977-a6e7-de06dc5fd567', 'pe', '265553090', '0014', 'o9EFCjxrMYaJzMGe', '0014.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6c51ef7f-dce5-469c-b9b7-a82e7c6a16e6', 'pe', '265553090', '0014', '8AebXqvPR9KXhVqX', '0014.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('930789ce-9111-4551-85a1-b37df800d87e', 'pe', '265553090', '0014', 'P5726QSd72AvRUMe', '0014.LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('da2c62fd-c8c1-4f1d-83a2-34bc2128d957', 'pe', '265553090', '0014', 'cLAu560ePhamel6o', '0014.MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b839f467-67df-41a5-8524-ecc21916b510', 'pe', '265553090', '0014', 'm2g8GFbZ9ZO9PMMG', '0014.HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('ee6a71b9-7641-4eff-bb36-b86481b501c6', 'pe', 'az1758205559313AAFQn', '278558187', '[Jaboatão/PE] GAC') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6f97071f-261a-402c-af8c-48e686dbdeab', 'pe', '278558187', '0080', 'G1lbXSQLQB2QkTdy', '0080.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('4fb4cafe-7b5d-4c64-92a4-eeab1b3869f1', 'pe', '278558187', '0080', 'cZnTwNZ8XNTSLCUH', '0080.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2a826f1e-519e-4573-b0c4-431a864b1798', 'pe', '278558187', '0080', 'epAPpcrWtVAcpW50', '0080.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('78d61fa5-ee40-48fa-99a5-f789271416f4', 'pe', '278558187', '0080', '4bByWJCAhkfCYhG7', '0080.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('8345d658-0eb1-4499-8f7c-2ad802e5bc12', 'pe', '278558187', '0080', 'DKdyLzshwsUcGA2Q', '0080.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('079004db-77ff-4586-9b25-df516a5e3b26', 'pe', 'az1758205559313AAFQn', '279332225', '[Recife/PE] Audi BV') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a593c8fe-6a52-4cba-8fc2-90c12c2fca70', 'pe', '279332225', '0022', 'sKaWgSPPfgEl4jAc', '0022.FREEZE ', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c7a579a8-d062-4fc1-98dd-2ab54054e0c9', 'pe', '279332225', '0022', 'mbQQefS5wQ1cbhZN', '0022.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ef994b93-44a9-4820-b0f0-8e53f1e4b535', 'pe', '279332225', '0022', '70QeFJmZnmxl3SWz', '0022.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7a64c80d-22b5-4aff-aa55-2516d535fc1d', 'pe', '279332225', '0022', 'BR4As5hsFn8p9eBy', '0022.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('769276bb-a588-4fcb-9f2f-bc0497bb9244', 'pe', '279332225', '0022', 's2oyYmGZZOSWZmvP', '0022.T-MEDIUM ', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('2f0de15e-63d1-49a3-85e4-32b4bbcb6f05', 'pe', 'az1758205559313AAFQn', '285173135', '[Recife/PE] Pateo Afog.') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('df400ad1-788f-4034-8b2c-ce91b8932391', 'pe', '285173135', '0012', 'YDmwbAiEtfjLkBaJ', '0012.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('d1da44fc-227d-45f8-a3b2-27961434245a', 'pe', '285173135', '0012', 'lBhqxCFRql7ZU8IU', '0012.ON', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('6752823f-5ef8-4619-bc90-b3c60e370bfa', 'pb', 'az1758202599342piVU9', '265049439', '[João P./PB] Auto Oriente') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7b2c8b3f-ecfd-4ea4-a64c-ebf6da48254a', 'pb', '265049439', '0081 NP', '1ZoodqztQylhGKv8', '0081.NP', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ee3eca87-ea20-4a9c-94d8-01919a1f4a7a', 'pb', '265049439', '0081 Freezer', 'ezN7qUtBYplyUbjd', '0081.Freezer', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b7f18f13-d725-496f-88f2-248bd073ddf7', 'pb', '265049439', '0081', 'dpn0xGGtxk9hWB00', '0081.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ab04290d-d187-4c16-a29b-b8ab2aca64c0', 'pb', '265049439', '0081', 'TVA3POx2JVGZ8gcm', '0081.T-Medium', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b3add39f-c755-4cd0-ac53-120ea52107d5', 'pb', '265049439', '0081', 'THaKNQPjHTWu3luT', '0081.High', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('b7476fc7-9567-430a-80d8-5f4b5ae1cb8d', 'pb', 'az1758202599342piVU9', '263338987', '[Natal/RN] Toyolex') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7699c4fd-9c64-4f75-90bb-81f94794bf88', 'pb', '263338987', '0015 REC SERV', 'Vc1ovqxCtVmJsRIO', '0015.OFF.REC.SERV', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bbc923b5-0e77-4991-8f40-967123ee8abd', 'pb', '263338987', '0015 REC SERV', 'CWcuXc0UwYI4cJSr', '0015.T-LOW.REC.SERV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b459cff6-c919-4976-a120-c94c8f816061', 'pb', '263338987', '0015 T-MÉDIUM REC SERV', 'ahLiRGFuCvYyoSgl', '0015.T-MÉDIUM.REC.SERV', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3bc08932-02cc-4465-82dc-5adc18a22066', 'pb', '263338987', '0015 REC SERV', 'oGU5YVXoDJ7MxsA9', '0015.T-HIGH.REC.SERV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5867bb6a-3db1-44f9-8a35-e835484dfcd5', 'pb', '263338987', '0015 SN', 'YiMSTL3tAfYnAH3F', '0015.OFF.SN', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('63bbdc4a-f990-4cd1-9564-8239d803e494', 'pb', '263338987', '0015 SN', 'aKROw4LVtoV3vW12', '0015.T-LOW.SN', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1f1515b6-a849-4dcf-a44d-fe1177375fbe', 'pb', '263338987', '0015 SN', 'BjUeMVWp1Zx137ER', '0015.T-MEDIUM.SN', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('cfbfac93-0ec5-4e6f-a209-ee81be47a3c1', 'pb', '263338987', '0015 SN', 'Ruoe77BgcBAk5ElW', '0015.T-HIGH.SN', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c85478aa-aff8-42c6-a096-2c86ac456a69', 'pb', '263338987', '0015 OOF NV', 'T7hZaAQpzntEscfT', '0015.OOF.NV', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('a8da8888-328e-42c5-bd84-eef22ab6ecb5', 'pb', '263338987', '0015 NV', 'caiTwoZVY0V9tLQA', '0015.T-LOW.NV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('fee7e585-01f4-42ac-b7b1-623a028593f7', 'pb', '263338987', '0015 NV', 'cqfS8v8feXV2X6NF', '0015.T-MEDIUM.NV', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('af9e8882-2afa-4512-bdff-6354e6741ccf', 'pb', '263338987', '0015 NV', '8tHM8oewBdbNZjYu', '0015.T-HIGH.NV', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f4255721-da35-499e-93fd-d8aea8b0a113', 'pb', '263338987', '0015', 'qZo83e1jpOQbFchp', '0015.LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('c105e1de-f2ae-4859-bc48-b507fe91bd78', 'pb', '263338987', '0015', 'iYSc8YeFYSo8voxj', '0015.HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('1dc22f7e-83ad-4391-a9b4-58abae7b4122', 'pb', '263338987', '0015', 'Z4wACc5SSsxATTPk', '0015.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('7ce2d593-6e1f-4e07-b6b6-2510d3a37802', 'pb', '263338987', '0015', 'YBvenxKHrscrBeZ8', '0015.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('671fe8b3-f2f4-4bd0-a1bc-fd1b185914be', 'pb', '263338987', '0015', 'TlHim8WeZHoktzGb', '0015.MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('3740773b-a2ea-4514-9830-15794ae3608a', 'pb', 'az1758202599342piVU9', '263456572', '[João P./PB] Auto Parvi') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('39cc02c0-a682-4cb9-b0c7-a1fbb84886dd', 'pb', 'az1758202599342piVU9', '263457722', '[João P./PB] BYD') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3a78cfef-00d6-4e39-97fc-7804a0b1de25', 'pb', '263457722', '0031', '5QwZF27luSLPtGDg', '0031.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('81528fb1-fe40-43a0-a629-a238f49af12e', 'pb', '263457722', '0031', 'U2ES3jBl5FG7eYWb', '0031.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('40d6e38a-8af0-49a0-9d6b-14252e3e7efa', 'pb', '263457722', '0031', 'i4YSR2tLYCDkP0cy', '0031.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9af67fa0-7f59-45f8-8bea-f83bbfde7b55', 'pb', '263457722', '0031', '3oFvRwCm9yGwAU9s', '0031.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5443bb02-a39c-4548-9d86-099a4cba7c81', 'pb', '263457722', '0031', 'yfrM5l0cbr0sR0lQ', '0031.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('8337713b-88e6-4d77-9166-acd803470a41', 'pb', 'az1758202599342piVU9', '263460377', '[João P./PB] Fiori') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('b940fa6a-80ea-4054-8731-1bdaa4df4413', 'pb', '263460377', '0032', 'EW3xgFzLjkYx1TLl', '0032.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e5a4096b-ff4a-4baa-86bc-b17a4ac279ed', 'pb', '263460377', '0032', 'mw4K95q9KY1gOMeo', '0032.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('14ac5fa7-d20d-4b58-a1ca-778b8b367a5e', 'pb', '263460377', '0032', 'MYS9g8WSPizzWrLw', '0032.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ba5436a4-78df-44cf-a060-59e912c1f0e0', 'pb', '263460377', '0032 T-MÉDIUM', 'bEjZQMjEVTwfpG8v', '0032.T-MÉDIUM', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('df4c2220-ec22-43fc-8cb1-223316b0830b', 'pb', '263460377', '0032', 'Ys352fPjy8Xvwq1x', '0032.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('2c036be0-9bc3-4ba6-8c30-5ad3326e29b1', 'pb', 'az1758202599342piVU9', '263461975', '[João P./PB] Pateo') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f6839a0e-5321-4483-9e5f-19f256638c7e', 'pb', '263461975', '0033', 'NU3ql2fwb1VIgifm', '0033.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('143bfb44-a3cd-44c1-8363-5a9160b69f95', 'pb', '263461975', '0033', 'EPdx3QtpdAlhyxiJ', '0033.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9f312018-1f3f-4f69-8f49-1f491fe17569', 'pb', '263461975', '0033', 'OzKjop4pqnvLgSNZ', '0033.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('2c982bc4-8071-4afd-a313-5e28defb5c3b', 'pb', '263461975', '0033', 'mbXJ7wM5iMxfu7Xp', '0033.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('14338627-1cd0-485c-9f9e-004db20a75e4', 'pb', '263461975', '0033', '10GD4JCCbYviU7ci', '0033.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('10a905e3-7ea5-4bb4-9dbe-773c30c622c1', 'pb', 'az1758202599342piVU9', '263465680', '[João P./PB] Land Rover') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('aad2d6af-e4bf-45d5-acfa-08cce1454ce9', 'pb', '263465680', '0034', 'AD6dZAJY5LlHP4wz', '0034.FREEZE', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('3c73305c-e743-429b-8051-78530871146d', 'pb', '263465680', '0034', 'GwpruvtCprLTdgC8', '0034.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('9b1252ca-5e8a-46b6-baac-acf9bfd98b69', 'pb', '263465680', '0034', 'huaSnQQA8IZWPKZ5', '0034.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('5b050e16-71cc-4078-8583-6b726391b27f', 'pb', '263465680', '0034', 'WLGYvbm4RxfBh3iX', '0034.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('865a49ff-a7eb-48df-86d6-5c72029fb01a', 'pb', '263465680', '0034', 'ajk1rMbXyZDJW507', '0034.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('7d90dc67-71b3-494c-9a77-2639966e3a0a', 'pb', 'az1758202599342piVU9', '237914424', '[Camp. Grande/PB] Fiori') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('61959850-ebdc-4f60-afe4-876ae3cd88e9', 'pb', '237914424', 'Fechamento do mês', 'yFD6MAPNdZExoH9s', 'Fechamento do mês', 'desconhecido') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('74d69e18-c9bd-4d50-bb93-7433c1a15f34', 'pb', '237914424', '0063', 'TaQFuMGeUsdYtKTW', '0063.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e4292c0b-5646-4d03-83f1-f35cd135c6ac', 'pb', '237914424', '0063', 'Trbbhi0loF1vnyI7', '0063.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('650c2cd9-a6b9-466b-83de-70c8619c6eff', 'pb', '237914424', '0063', '4rk4WDRj6v7Gky7J', '0063.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e00e4ab2-8b52-4d25-981f-13b3063d8fc7', 'pb', '237914424', '0063 Tudo', 'fLxUz9vJyom6j3cr', '0063.OFF.Tudo', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('725a6593-2198-4321-ad0d-0ed12d8cb1b2', 'pb', '237914424', '0063 Freezer', 'DZZUvBlqiijb4gPz', '0063.Freezer', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('3cefd1ab-efa3-4358-838e-dae31948ef2b', 'pb', 'az1758202599342piVU9', '237911804', '[Camp. Grande/PB] BYD') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('f62ecd94-b24d-4ebc-946b-fcf458cd8ce8', 'pb', '237911804', '0065', 'i8AxXXz0QxppOD0r', '0065.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('bd22cdc9-0b0c-4e3a-9be9-1b8b462597fd', 'pb', '237911804', '0065', 's3rfvSjYE3x50Hcb', '0065.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e5a09e4c-6777-40dc-b95c-057a1e6577d0', 'pb', '237911804', '0065', 'jIfYCNc9lGYaNqti', '0065.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ec61916d-12dc-412b-a40d-0dc4458d3404', 'pb', '237911804', '0065 SHNV', 'tAjp1Gfy9PSsXyh5', '0065.OFF.SHNV', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6927916e-c3ed-41a6-b830-4908b61155da', 'pb', '237911804', '0065 SHNV', '06TleizScrP5pM19', '0065.Freeze.SHNV', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('c2127148-07d2-4925-96fd-50805a5cf616', 'pb', 'az1758202599342piVU9', '237911851', '[Camp Grande/PB] JEEP RAM') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('47539cb4-11cb-442b-9f16-f4b0e94a1f5d', 'pb', '237911851', '0064', 'w4ReYIqIgAJsDvxs', '0064.Freeze', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('baf30578-8180-41b7-b6a2-c517a0d03252', 'pb', '237911851', '0064', 'LEkfsUlkhA05SmYp', '0064.OFF', 'desligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('50c3675e-7b4d-4136-994f-6e94774931ae', 'pb', '237911851', '0064', 'qPNZo1sv6yWB7gAE', '0064.T-HIGH', 'esquentar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('6874a996-c265-41eb-adec-6474f618d9cd', 'pb', '237911851', '0064', 'fHtpTGAidEfMzns6', '0064.T-MEDIUM', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ef714569-5b44-4f6f-b5f7-04ca4a0eee29', 'pb', '237911851', '0064', 'wMrea3aJ4XakTu2d', '0064.T-LOW', 'esfriar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_homes (id, sigla_cliente, tuya_uid, home_id, nome_home) VALUES ('b33394de-4f58-42d6-b534-eebaea4a315a', 'pb', 'az1758202599342piVU9', '265046253', '[Cabedelo./PB] Auto Ori.') ON CONFLICT (sigla_cliente, home_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('e2b412e9-0765-4990-a0e5-a852aa78d98c', 'pb', '265046253', '0082 NP', 'Up9NhJQS8kHf1RAN', '0082.NP', '') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('21d43ae0-03ac-4968-84d2-2f711e61bcb0', 'pb', '265046253', '0082', 'wZsP8TIHuneQAXOK', '0082.T-Medium', 'ligar') ON CONFLICT (scene_id) DO NOTHING;
INSERT INTO tuya_clientes_cenas (id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao) VALUES ('ca9d9e62-6fb4-402f-a44d-69ba22fc56d0', 'pb', '265046253', '0082 T-OFF', 'Qx3CV4Yk7gG2WQ7A', '0082.T-OFF', '') ON CONFLICT (scene_id) DO NOTHING;


-- =============================================================================
-- 4. VINCULAÇÃO AUTOMÁTICA DE TUYA_HOME_ID NAS REVENDAS
-- =============================================================================

-- Mapeamento para o grupo de testes / Thiago
UPDATE mapa_revendas 
SET tuya_home_id = '265054363' 
WHERE id_grupo_wpp = '120363422455765261-group' OR nome_revenda ILIKE '%Thiago%' OR nome_revenda ILIKE '%Teste%';

-- Mapeamento automático entre mapa_revendas e tuya_clientes_homes por nome
UPDATE mapa_revendas m
SET tuya_home_id = h.home_id
FROM tuya_clientes_homes h
WHERE m.tuya_home_id IS NULL
  AND (
    h.nome_home ILIKE '%' || m.nome_revenda || '%' OR
    m.nome_revenda ILIKE '%' || h.nome_home || '%'
  );

COMMIT;

-- Relatório de validação pós-povoamento
SELECT 
    m.nome_revenda,
    m.id_grupo_wpp,
    m.tuya_home_id,
    COUNT(c.id) AS total_cenas_tuya
FROM mapa_revendas m
LEFT JOIN tuya_clientes_cenas c ON m.tuya_home_id = c.home_id
GROUP BY m.nome_revenda, m.id_grupo_wpp, m.tuya_home_id
ORDER BY m.nome_revenda;
