begin;
alter table public.radar_enrichment_jobs add column lease_token text;
alter table public.radar_source_receipts add column http_status integer not null default 200;
alter table public.radar_source_receipts add column truncated boolean not null default false;
commit;
