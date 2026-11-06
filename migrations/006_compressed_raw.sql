begin;
alter table public.radar_raw add column payload_gzip bytea;
alter table public.radar_raw alter column payload drop not null;
alter table public.radar_raw add constraint radar_raw_one_payload
 check(num_nonnulls(payload,payload_gzip)=1);
comment on column public.radar_raw.payload_gzip is 'Lossless gzip of sorted UTF-8 JSON; decode and verify content_hash with radar.raw_codec.';
commit;
