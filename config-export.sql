-- 591 Monitor config export: search_profiles, commute_anchors, tag_rules
-- Import on new machine AFTER app is running:
--   docker exec -i 591-monitor-postgres-1 psql -U postgres -d monitor < config-export.sql

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET row_security = off;

--
-- commute_anchors
--

INSERT INTO public.commute_anchors VALUES ('349364e5-1650-422c-ae17-0e8127cd666b', '內湖', '台北捷運內湖站', 1, true, '2026-05-08 07:32:48.606791+00', '2026-05-08 07:32:48.606794+00') ON CONFLICT (id) DO NOTHING;


--
-- search_profiles
--

INSERT INTO public.search_profiles VALUES ('4f9c8f7b-d493-408d-b834-e46eb50611a2', '汐止區8平以上', true, 'new_taipei', '["27"]', 11000, 20000, '["獨立套房"]', '[]', '["限女"]', 30, '2026-05-12 08:07:57.139174+00', '2026-05-11 11:30:26.995207+00', '2026-05-12 08:07:57.146204+00', 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO public.search_profiles VALUES ('88e7845d-78e7-4ad2-be3a-4033a1b21c8e', '南港内湖8平以上', true, 'taipei', '["11", "10"]', 11000, 20000, '["獨立套房"]', '[]', '["限女"]', 30, '2026-05-12 08:08:15.848013+00', '2026-05-11 05:37:58.10504+00', '2026-05-12 08:08:15.852248+00', 8) ON CONFLICT (id) DO NOTHING;


--
-- tag_rules
--

INSERT INTO public.tag_rules VALUES ('85847cf5-805d-4254-88e7-88cacebccd96', '台電', '["台電"]', '[]', true, '2026-05-11 11:58:43.755568+00', '2026-05-11 11:58:43.755572+00') ON CONFLICT (id) DO NOTHING;
INSERT INTO public.tag_rules VALUES ('75e23929-8e92-4bce-801a-2c2ba6966974', '樓中樓', '["樓中樓"]', '[]', true, '2026-05-12 05:58:55.167145+00', '2026-05-12 05:58:55.167148+00') ON CONFLICT (id) DO NOTHING;
INSERT INTO public.tag_rules VALUES ('9ff89a8a-9b42-49b0-a7ea-fb8d071cb188', '喜來登', '["喜來登"]', '[]', true, '2026-05-12 06:10:07.315538+00', '2026-05-12 06:10:07.315543+00') ON CONFLICT (id) DO NOTHING;
