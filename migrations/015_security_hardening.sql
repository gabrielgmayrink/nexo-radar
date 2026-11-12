begin;
alter table public.radar_memberships add column role text not null default 'owner'
 check(role in ('owner','admin','analyst','viewer'));
create table public.radar_account_security (
 email text primary key,
 generation bigint not null default 0,
 require_mfa boolean not null default false,
 disabled_at timestamptz,
 updated_at timestamptz not null default now()
);
alter table public.radar_team_sessions add column auth_generation bigint not null default 0;
alter table public.radar_team_sessions add column assurance_level text not null default 'aal1'
 check(assurance_level in ('aal1','aal2'));
alter table public.radar_team_sessions add column credential_fingerprint text;
alter table public.radar_team_sessions add column last_seen_at timestamptz;
create index radar_team_sessions_user on public.radar_team_sessions(email,expires_at);
create table public.radar_mfa_pending (
 token_digest text primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 email text not null,
 auth_generation bigint not null,
 encrypted_access_token bytea not null,
 factors jsonb not null default '[]',
 enrollment_required boolean not null default false,
 attempts integer not null default 0,
 expires_at timestamptz not null,
 consumed_at timestamptz,
 created_at timestamptz not null default now()
);
create index radar_mfa_pending_email on public.radar_mfa_pending(email,expires_at);
alter table public.radar_review_state add column owner text not null default '';
alter table public.radar_review_state add column checklist jsonb not null default '[]';
alter table public.radar_account_security enable row level security;
alter table public.radar_mfa_pending enable row level security;
revoke all on public.radar_account_security,public.radar_mfa_pending from anon,authenticated;
grant select,insert,update,delete on public.radar_account_security,public.radar_mfa_pending to service_role;
-- Existing opaque sessions predate credential fingerprints; require a fresh login.
update public.radar_team_sessions set expires_at=least(expires_at,now()) where credential_fingerprint is null;
commit;
