begin;
alter table public.radar_opportunities add column catalog_seen_at timestamptz;
create index radar_opportunities_seen on public.radar_opportunities(catalog_seen_at);
create table public.radar_source_pages (
 id bigint generated always as identity primary key,
 execution_id bigint not null references public.radar_executions(id),
 pass_number integer not null,
 page_number integer not null,
 source_mode text not null default 'proposta',
 modality integer not null default 0,
 content_hash text not null,
 payload_gzip bytea not null,
 source_total integer,
 source_pages integer,
 transport_status integer,
 truncated boolean not null default false,
 captured_at timestamptz not null default now(),
 unique(execution_id,pass_number,page_number,source_mode,modality,content_hash)
);
create table public.radar_source_observations (
 capture_id bigint not null references public.radar_source_pages(id),
 ordinal integer not null,
 opportunity_id text,
 content_hash text not null,
 parse_state text not null check(parse_state in ('indexed','quarantined')),
 primary key(capture_id,ordinal)
);
create index radar_observation_membership on public.radar_source_observations(opportunity_id,capture_id);
alter table public.radar_national_pages add column capture_id bigint references public.radar_source_pages(id);
create table public.radar_quarantine (
 capture_id bigint not null references public.radar_source_pages(id),
 ordinal integer not null,
 reason text not null,
 attempts integer not null default 0,
 resolved_at timestamptz,
 created_at timestamptz not null default now(),
 primary key(capture_id,ordinal)
);
alter table public.radar_source_pages enable row level security;
alter table public.radar_source_observations enable row level security;
alter table public.radar_quarantine enable row level security;
revoke all on public.radar_source_pages,public.radar_source_observations,public.radar_quarantine from anon,authenticated;
grant select,insert,update,delete on public.radar_source_pages,public.radar_source_observations,public.radar_quarantine to service_role;
grant usage,select on sequence public.radar_source_pages_id_seq to service_role;
-- Historical count-based receipts stay readable but are not set-consistency proofs.
update public.radar_catalog_state set content=content || jsonb_build_object(
 'captureComplete',true,'coverageComplete',false,'consistency','legacy_count_check',
 'verificationPolicy','stable_sets_v1','indexingComplete',null)
 where id='open' and content->>'kind'='national_open';
-- Legacy head/tail checkpoints cannot be resumed as if they had full set proofs.
update public.radar_checkpoints set cursor=cursor || jsonb_build_object(
 'captureComplete',false,'coverageComplete',false,'consistency','legacy_count_check',
 'verificationPolicy','stable_sets_v1','completedFullPasses',0,'previousPassEvidence',null,
 'status','running','passNumber',coalesce((cursor->>'passNumber')::integer,1)+1,
 'partition',0,'page',1,'fingerprints','[]'::jsonb,'pending_tasks',
 jsonb_build_array(jsonb_build_object('mode','proposta','modality',0,'page',1,'fingerprints','[]'::jsonb)))
 where key='sync:national_open';
update public.radar_executions set metrics=metrics || jsonb_build_object('coverageComplete',false,
 'consistency','legacy_count_check','verificationPolicy','stable_sets_v1')
 where task='sync:national_open' and metrics->>'coverageComplete'='true';
commit;
