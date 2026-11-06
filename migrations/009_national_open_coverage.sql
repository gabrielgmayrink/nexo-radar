begin;
alter table public.radar_opportunities add column national_execution_id bigint references public.radar_executions(id);
alter table public.radar_opportunities add column national_pass integer not null default 0;
create index radar_opportunities_national on public.radar_opportunities(national_execution_id,national_pass);
create table public.radar_national_pages (
 execution_id bigint not null references public.radar_executions(id),
 pass_number integer not null,
 page_number integer not null,
 content_hash text not null,
 record_count integer not null,
 source_total integer not null,
 source_pages integer not null,
 committed_at timestamptz not null default now(),
 primary key(execution_id,pass_number,page_number)
);
alter table public.radar_national_pages enable row level security;
revoke all on public.radar_national_pages from anon,authenticated;
grant select,insert,update,delete on public.radar_national_pages to service_role;
create view public.radar_national_candidates with (security_invoker=true) as
 select o.id,o.card,o.score,o.product_scores from public.radar_opportunities o
 where o.national_execution_id > coalesce((select (content->>'executionId')::bigint from public.radar_catalog_state where id='open'),0)
    or (o.national_execution_id = (select (content->>'executionId')::bigint from public.radar_catalog_state where id='open')
        and o.national_pass >= coalesce((select (content->>'passNumber')::int from public.radar_catalog_state where id='open'),1));
revoke all on public.radar_national_candidates from anon,authenticated;
grant select on public.radar_national_candidates to service_role;
update public.radar_products set profile='Assessoria e preparação de documentos; apoio administrativo; gestão empresarial pública e privada; palestras e capacitação profissional e gerencial; ensino EAD.' where id='public';
commit;
