begin;
alter table public.radar_opportunities add column catalog_archived_at timestamptz;
alter table public.radar_opportunities add column catalog_archive_reason text
 check (catalog_archive_reason in ('expired','inactive','outside_profile'));
create index radar_opportunities_active on public.radar_opportunities(score) where catalog_archived_at is null;
create or replace view public.radar_national_candidates with (security_invoker=true) as
 select o.id,o.card,o.score,o.product_scores from public.radar_opportunities o
 where o.catalog_archived_at is null and (
   o.national_execution_id > coalesce((select (content->>'executionId')::bigint from public.radar_catalog_state where id='open'),0)
   or (o.national_execution_id = (select (content->>'executionId')::bigint from public.radar_catalog_state where id='open')
       and o.national_pass >= coalesce((select (content->>'minimumPass')::int from public.radar_catalog_state where id='open'),1)));
revoke all on public.radar_national_candidates from anon,authenticated;
grant select on public.radar_national_candidates to service_role;
commit;
