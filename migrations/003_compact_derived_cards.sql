begin;
alter table public.radar_opportunities add column content_hash text;
-- Cards are a reproducible presentation cache. Preserve every original payload.
update public.radar_opportunities set card=null where score<40 and card is not null;
commit;
