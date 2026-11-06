begin;
create table public.radar_mail_outbox (
 id uuid primary key,
 dedupe_key text not null unique,
 recipient text not null,
 kind text not null check(kind in ('login','weekly','urgent','test')),
 status text not null default 'reserved' check(status in ('reserved','sent','failed','unknown')),
 provider_id text,
 error_code integer,
 created_at timestamptz not null default now(),
 sent_at timestamptz
);
create index radar_mail_budget on public.radar_mail_outbox(created_at,recipient,kind);
create table public.radar_login_requests (
 token_digest text primary key,
 email text not null,
 verification_type text not null check(verification_type in ('magiclink','signup','email')),
 expires_at timestamptz not null,
 consumed_at timestamptz,
 created_at timestamptz not null default now()
);
create table public.radar_team_sessions (
 token_digest text primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 email text not null,
 expires_at timestamptz not null,
 created_at timestamptz not null default now()
);
create table public.radar_review_state (
 opportunity_id text primary key references public.radar_opportunities(id),
 offer text not null check(offer in ('','Public','Gerico','Ambas','Nenhuma','Revisar')),
 status text not null check(status in ('Nova','Em avaliação','Vou participar','Descartada','Ganhou','Perdeu')),
 reason text not null check(length(reason)<=2000),
 actor text not null,
 version integer not null default 1,
 updated_at timestamptz not null default now()
);
create table public.radar_review_history (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 actor text not null,
 payload jsonb not null,
 created_at timestamptz not null default now()
);
alter table public.radar_mail_outbox enable row level security;
alter table public.radar_login_requests enable row level security;
alter table public.radar_team_sessions enable row level security;
alter table public.radar_review_state enable row level security;
alter table public.radar_review_history enable row level security;
revoke all on public.radar_mail_outbox,public.radar_login_requests,public.radar_team_sessions,
 public.radar_review_state,public.radar_review_history from anon,authenticated;
grant select,insert,update,delete on public.radar_mail_outbox,public.radar_login_requests,public.radar_team_sessions,
 public.radar_review_state,public.radar_review_history to service_role;
grant usage,select on sequence public.radar_review_history_id_seq to service_role;
commit;
