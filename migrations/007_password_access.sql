begin;
create table public.radar_account_invites (
 token_digest text primary key,
 email text not null,
 expires_at timestamptz not null,
 consumed_at timestamptz,
 created_at timestamptz not null default now()
);
create table public.radar_auth_attempts (
 id bigint generated always as identity primary key,
 subject_hash text not null,
 created_at timestamptz not null default now()
);
create index radar_auth_attempt_window on public.radar_auth_attempts(subject_hash,created_at);
alter table public.radar_account_invites enable row level security;
alter table public.radar_auth_attempts enable row level security;
revoke all on public.radar_account_invites,public.radar_auth_attempts from anon,authenticated;
grant select,insert,update,delete on public.radar_account_invites,public.radar_auth_attempts to service_role;
grant usage,select on sequence public.radar_auth_attempts_id_seq to service_role;
commit;
