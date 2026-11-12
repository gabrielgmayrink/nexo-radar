begin;
create table public.radar_data_sources (
 source_id text primary key,
 name text not null,
 documentation_url text not null,
 access_state text not null,
 enabled boolean not null default false,
 last_success_at timestamptz,
 last_error_code text,
 updated_at timestamptz not null default now()
);
insert into public.radar_data_sources(source_id,name,documentation_url,access_state,enabled) values
 ('pncp','PNCP','https://pncp.gov.br/api/consulta/swagger-ui/index.html','validated_sample',true),
 ('compras_gov','Compras.gov.br','https://dadosabertos.compras.gov.br/swagger-ui/index.html','validated_sample',true),
 ('querido_diario','Querido Diário','https://docs.queridodiario.ok.org.br/pt-br/latest/utilizando/api-publica.html','pending_live_validation',false),
 ('inlabs','INLABS · Diário Oficial da União','https://github.com/Imprensa-Nacional/inlabs','requires_authorization',false),
 ('compras_mg','Dados abertos de licitações MG','https://dados.mg.gov.br/pt_BR/dataset/portal_licitacoes_mg','evaluated_not_integrated',false),
 ('tcemg','TCE-MG · SICOM','https://dadosabertos.tce.mg.gov.br/','no_validated_api_access',false);
create table public.radar_source_receipts (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 source_id text not null references public.radar_data_sources(source_id),
 source_hash text not null,
 url text not null,
 content_hash text not null,
 payload_gzip bytea not null,
 captured_at timestamptz not null default now(),
 unique(opportunity_id,source_id,source_hash,url,content_hash)
);
create table public.radar_source_links (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 source_id text not null references public.radar_data_sources(source_id),
 source_hash text not null,
 external_id text not null,
 link_type text not null check(link_type in ('official_id','item_page','document_manifest')),
 url text not null,
 content_hash text not null,
 payload jsonb not null,
 captured_at timestamptz not null default now(),
 unique(opportunity_id,source_id,source_hash,external_id,content_hash)
);
create table public.radar_enrichment_jobs (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 source_hash text not null,
 task_type text not null check(task_type in ('pncp_items','compras_details','compras_items','pncp_documents','pdf')),
 job_key text not null default '',
 status text not null default 'pending' check(status in ('pending','processing','done','retry','blocked')),
 cursor jsonb not null default '{}',
 attempts integer not null default 0,
 next_attempt_at timestamptz not null default now(),
 lease_until timestamptz,
 last_error_code text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(opportunity_id,source_hash,task_type,job_key)
);
create index radar_enrichment_pending on public.radar_enrichment_jobs(status,next_attempt_at,lease_until);
create table public.radar_documents (
 id bigint generated always as identity primary key,
 opportunity_id text not null references public.radar_opportunities(id),
 source_hash text not null,
 document_key text not null,
 title text not null,
 url text not null,
 content_hash text,
 payload_gzip bytea,
 extraction_state text not null default 'pending',
 pages jsonb not null default '[]',
 extracted_at timestamptz,
 captured_at timestamptz not null default now(),
 unique(opportunity_id,source_hash,document_key)
);
do $$ declare t text; begin
 foreach t in array array['radar_data_sources','radar_source_receipts','radar_source_links','radar_enrichment_jobs','radar_documents'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select,insert,update,delete on public.%I to service_role',t);
 end loop;
end $$;
grant usage,select on sequence public.radar_source_receipts_id_seq,public.radar_source_links_id_seq,
 public.radar_enrichment_jobs_id_seq,public.radar_documents_id_seq to service_role;
commit;
