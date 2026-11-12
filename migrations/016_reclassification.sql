begin;
alter table public.radar_opportunities add column classification_version text not null default '';
create index radar_classification_pending on public.radar_opportunities(classification_version,id);
commit;
