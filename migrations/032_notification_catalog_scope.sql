begin;
-- Notifications and legacy reads use the same preserved national union as UI.
create or replace view public.radar_national_candidates with(security_invoker=true) as
 select c.id,c.card,c.score,c.product_scores from public.radar_catalog_source c;
grant select on public.radar_national_candidates,public.radar_catalog_source,public.radar_learning_examples to radar_collector;
grant select on public.radar_national_candidates to radar_api;
commit;
