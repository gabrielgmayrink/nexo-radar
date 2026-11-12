begin;
alter table public.radar_opportunities add column object_hash text;
create index radar_opportunities_object_hash on public.radar_opportunities(object_hash);
create or replace function public.radar_search_normalize(value text) returns text
language sql immutable parallel safe set search_path=pg_catalog as $$
 select btrim(regexp_replace(translate(lower(coalesce(value,'')),
 'áàâãäéèêëíìîïóòôõöúùûüçñ','aaaaaeeeeiiiiooooouuuucn'),'[^a-z0-9]+',' ','g'))
$$;
create or replace function public.radar_safe_timestamp(value text) returns timestamptz
language plpgsql stable set search_path=pg_catalog as $$
begin
 if nullif(btrim(value),'') is null then return null; end if;
 if value ~ '(Z|z|[+-][0-9]{2}:[0-9]{2})$' then return value::timestamptz; end if;
 return value::timestamp at time zone 'America/Sao_Paulo';
exception when invalid_datetime_format or datetime_field_overflow then return null;
end $$;
revoke all on function public.radar_search_normalize(text) from public,anon,authenticated;
revoke all on function public.radar_safe_timestamp(text) from public,anon,authenticated;
grant execute on function public.radar_search_normalize(text),public.radar_safe_timestamp(text) to service_role;
create or replace view public.radar_catalog_source with (security_invoker=true) as
 select o.id,o.payload,o.card,o.score,o.product_scores,o.rule_version,o.content_hash,o.catalog_archive_reason,o.classification_version,o.object_hash
 from public.radar_opportunities o where (
 o.catalog_seen_at >= (select (content->>'completedAt')::timestamptz from public.radar_catalog_state where id='open')
 or o.national_execution_id > coalesce((select (content->>'executionId')::bigint from public.radar_catalog_state where id='open'),0)
 or (o.national_execution_id=(select (content->>'executionId')::bigint from public.radar_catalog_state where id='open')
     and o.national_pass>=coalesce((select (content->>'minimumPass')::int from public.radar_catalog_state where id='open'),1)));
revoke all on public.radar_catalog_source from anon,authenticated;
grant select on public.radar_catalog_source to service_role;
create index if not exists radar_review_company_order on public.radar_review_state(company_id,updated_at desc,opportunity_id);
create index if not exists radar_review_company_object on public.radar_review_state(company_id,object_hash,updated_at desc);
commit;
