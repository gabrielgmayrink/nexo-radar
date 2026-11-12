begin;
-- Prepare immutable text once on insert/payload change, instead of normalizing
-- the entire national catalog for every count, facet and result page.
alter table public.radar_opportunities
 add column search_text text not null default '',
 add column object_normalized_length integer not null default 0,
 add column city_text text not null default '',
 add column organization_text text not null default '',
 add column proposal_deadline timestamptz,
 add column publication_time timestamptz;

create function public.radar_project_catalog_search() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 new.search_text:=public.radar_search_normalize(
  coalesce(new.payload->>'objetoCompra','')||' '||coalesce(new.payload->>'informacaoComplementar','')||' '||
  coalesce(new.payload->'orgaoEntidade'->>'razaoSocial','')||' '||
  coalesce(new.payload->'unidadeOrgao'->>'municipioNome','')||' '||
  coalesce(new.payload->'unidadeOrgao'->>'ufSigla','')||' '||new.id);
 new.object_normalized_length:=length(public.radar_search_normalize(new.payload->>'objetoCompra'));
 new.city_text:=public.radar_search_normalize(new.payload->'unidadeOrgao'->>'municipioNome');
 new.organization_text:=public.radar_search_normalize(new.payload->'orgaoEntidade'->>'razaoSocial');
 new.proposal_deadline:=public.radar_safe_timestamp(new.payload->>'dataEncerramentoProposta');
 new.publication_time:=public.radar_safe_timestamp(new.payload->>'dataPublicacaoPncp');
 return new;
end $$;
revoke all on function public.radar_project_catalog_search() from public,anon,authenticated;
grant execute on function public.radar_project_catalog_search() to service_role,radar_collector;
create trigger radar_catalog_search_projection before insert or update of id,payload
 on public.radar_opportunities for each row execute function public.radar_project_catalog_search();
-- Backfill also exercises the same trigger used by new captures and amendments.
update public.radar_opportunities set payload=payload;
commit;
