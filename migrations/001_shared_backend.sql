-- Apply only to the NEW Radar Supabase project after configuration approval.
begin;
create extension if not exists pg_trgm;
create table public.radar_products (
  id text primary key check(id in ('public','gerico')),
  name text not null,
  profile text not null,
  active boolean not null default false
);
insert into public.radar_products(id,name,profile,active) values
 ('public','Public','Assessoria administrativa e de gestão; capacitação profissional e gerencial; ensino EAD; desenvolvimento de sistemas e serviços de TI.',true),
 ('gerico','Gerico','Aguardando definição dos produtos e serviços.',false);
create table public.radar_opportunities (
  id text primary key,
  payload jsonb not null,
  product_scores jsonb not null default '{}',
  rule_version text not null,
  updated_at timestamptz not null default now()
);
create table public.radar_raw (
  opportunity_id text not null,
  content_hash text not null,
  payload jsonb not null,
  collected_at timestamptz not null default now(),
  primary key(opportunity_id,content_hash)
);
create table public.radar_feedback (
  event_id uuid primary key,
  opportunity_id text not null references public.radar_opportunities(id),
  product_id text not null references public.radar_products(id),
  label text not null check(label in ('relevante','irrelevante','vai_participar','ganhou','perdeu')),
  created_at timestamptz not null default now()
);
create index radar_feedback_latest on public.radar_feedback(opportunity_id,product_id,created_at desc);
create table public.radar_executions (
  id bigint generated always as identity primary key,
  task text not null,
  status text not null check(status in ('running','ok','partial','failed')),
  metrics jsonb not null default '{}',
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create table public.radar_checkpoints (
  key text primary key,
  cursor jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.radar_products enable row level security;
alter table public.radar_opportunities enable row level security;
alter table public.radar_raw enable row level security;
alter table public.radar_feedback enable row level security;
alter table public.radar_executions enable row level security;
alter table public.radar_checkpoints enable row level security;
revoke all on public.radar_products,public.radar_opportunities,public.radar_raw,
  public.radar_feedback,public.radar_executions,public.radar_checkpoints from anon,authenticated;
grant select,insert,update,delete on public.radar_products,public.radar_opportunities,
  public.radar_raw,public.radar_feedback,public.radar_executions,public.radar_checkpoints to service_role;
grant usage,select on sequence public.radar_executions_id_seq to service_role;
commit;
