begin;
create table public.radar_procurement_events (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 event_key text not null unique,
 kind text not null,
 old_value jsonb,
 new_value jsonb,
 source text not null,
 detected_at timestamptz not null default now()
);
create index radar_procurement_events_timeline on public.radar_procurement_events(opportunity_id,detected_at desc,id desc);
alter table public.radar_procurement_events enable row level security;
revoke all on public.radar_procurement_events from anon,authenticated;
grant select,insert on public.radar_procurement_events to service_role;
grant usage,select on sequence public.radar_procurement_events_id_seq to service_role;
commit;
