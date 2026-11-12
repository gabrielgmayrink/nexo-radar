begin;
create table public.radar_item_search (
 opportunity_id text not null references public.radar_opportunities(id),
 source_hash text not null,
 source_id text not null references public.radar_data_sources(source_id),
 item_number text not null,
 text_normalized text not null,
 primary key(opportunity_id,source_hash,source_id,item_number)
);
create index radar_item_search_text on public.radar_item_search using gin(text_normalized gin_trgm_ops);
create index radar_source_links_lookup on public.radar_source_links(opportunity_id,source_hash,source_id);
alter table public.radar_item_search enable row level security;
revoke all on public.radar_item_search from anon,authenticated;
grant select,insert,update,delete on public.radar_item_search to service_role,radar_collector;
grant select on public.radar_item_search to radar_web;
create policy radar_items_read on public.radar_item_search for select to radar_web using(true);
create policy radar_items_collect on public.radar_item_search to radar_collector using(true) with check(true);
commit;
