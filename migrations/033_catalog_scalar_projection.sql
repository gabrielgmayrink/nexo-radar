begin;
-- Counts and facets must not repeatedly decompress complete official documents.
-- The original JSON remains authoritative and is returned only for the selected page.
alter table public.radar_opportunities
 add column source_status text,
 add column instrument_code text,
 add column state_code text,
 add column modality_name text,
 add column estimated_value numeric;

create or replace function public.radar_project_catalog_search() returns trigger
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
 new.source_status:=new.payload->>'situacaoCompraId';
 new.instrument_code:=new.payload->>'tipoInstrumentoConvocatorioCodigo';
 new.state_code:=new.payload->'unidadeOrgao'->>'ufSigla';
 new.modality_name:=new.payload->>'modalidadeNome';
 new.estimated_value:=case when jsonb_typeof(new.payload->'valorTotalEstimado')='number'
  then (new.payload->>'valorTotalEstimado')::numeric else null end;
 return new;
end $$;
-- Populate only the new scalar columns; keep classification, captures and originals.
update public.radar_opportunities set
 source_status=payload->>'situacaoCompraId',
 instrument_code=payload->>'tipoInstrumentoConvocatorioCodigo',
 state_code=payload->'unidadeOrgao'->>'ufSigla',
 modality_name=payload->>'modalidadeNome',
 estimated_value=case when jsonb_typeof(payload->'valorTotalEstimado')='number'
  then (payload->>'valorTotalEstimado')::numeric else null end;
commit;
