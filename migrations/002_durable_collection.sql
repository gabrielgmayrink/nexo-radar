begin;
alter table public.radar_opportunities add column score integer not null default 0;
alter table public.radar_opportunities add column card jsonb;
alter table public.radar_opportunities add column source_updated_at timestamptz;
create index radar_candidate_score on public.radar_opportunities(score desc,id) where score>=40;
create table public.radar_catalog_state (
  id text primary key check(id in ('publications','open')),
  content jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.radar_catalog_state enable row level security;
revoke all on public.radar_catalog_state from anon,authenticated;
grant select,insert,update on public.radar_catalog_state to service_role;
create index radar_execution_task_started on public.radar_executions(task,started_at desc);
commit;
