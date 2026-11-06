begin;
create table public.radar_memberships (
 email text not null check(email=lower(email)),
 company_id text not null check(company_id in ('public','gerico')),
 primary key(email,company_id)
);
alter table public.radar_memberships enable row level security;
revoke all on public.radar_memberships from anon,authenticated;
grant select,insert,update,delete on public.radar_memberships to service_role;

alter table public.radar_review_state add column company_id text not null default 'public' check(company_id in ('public','gerico'));
alter table public.radar_review_state drop constraint radar_review_state_pkey;
alter table public.radar_review_state add primary key(opportunity_id,company_id);
alter table public.radar_review_history add column company_id text not null default 'public' check(company_id in ('public','gerico'));
create or replace view public.radar_learning_examples with (security_invoker=true) as
 select r.opportunity_id,r.offer,r.reason_code,r.object_hash,r.example_object,r.example_additional,r.company_id
 from public.radar_review_state r join public.radar_opportunities o on o.id=r.opportunity_id
 where r.example_object=o.payload->>'objetoCompra'
 and r.example_additional=coalesce(o.payload->>'informacaoComplementar','');
revoke all on public.radar_learning_examples from anon,authenticated;
grant select on public.radar_learning_examples to service_role;
commit;
