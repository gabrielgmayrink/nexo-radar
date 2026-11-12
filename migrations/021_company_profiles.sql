begin;
create table public.radar_company_profiles (
 company_id text primary key check(company_id in ('public','gerico')),
 configuration jsonb not null,
 version integer not null default 1 check(version>0),
 actor text not null, updated_at timestamptz not null default now()
);
create table public.radar_profile_history (
 id bigint generated always as identity primary key,
 company_id text not null check(company_id in ('public','gerico')),
 configuration jsonb not null, version integer not null,
 actor text not null, created_at timestamptz not null default now()
);
alter table public.radar_company_profiles enable row level security;
alter table public.radar_profile_history enable row level security;
revoke all on public.radar_company_profiles,public.radar_profile_history from anon,authenticated;
grant all on public.radar_company_profiles,public.radar_profile_history to service_role;
grant usage,select on sequence public.radar_profile_history_id_seq to service_role;
create index radar_profile_history_company on public.radar_profile_history(company_id,created_at desc);
commit;
