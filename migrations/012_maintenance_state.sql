begin;
alter table public.radar_catalog_state drop constraint radar_catalog_state_id_check;
alter table public.radar_catalog_state add constraint radar_catalog_state_id_check
 check (id in ('publications','open','maintenance'));
commit;
