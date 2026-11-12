begin;
-- An incremental may arrive before the first completed national sweep.
-- Keep those captured rows reviewable without claiming national completeness.
create or replace view public.radar_catalog_source with (security_invoker=true) as
 select o.id,o.payload,o.card,o.score,o.product_scores,o.rule_version,o.content_hash,o.catalog_archive_reason,o.classification_version,o.object_hash
 from public.radar_opportunities o where (
 o.catalog_seen_at >= coalesce((select (content->>'completedAt')::timestamptz from public.radar_catalog_state where id='open'),'-infinity'::timestamptz)
 or o.national_execution_id > coalesce((select (content->>'executionId')::bigint from public.radar_catalog_state where id='open'),0)
 or (o.national_execution_id=(select (content->>'executionId')::bigint from public.radar_catalog_state where id='open')
     and o.national_pass>=coalesce((select (content->>'minimumPass')::int from public.radar_catalog_state where id='open'),1)));
revoke all on public.radar_catalog_source from anon,authenticated;
grant select on public.radar_catalog_source to service_role,radar_web;
commit;
