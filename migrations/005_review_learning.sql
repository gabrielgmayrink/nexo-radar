begin;
alter table public.radar_review_state add column reason_code text not null default ''
 check(reason_code in ('','produto_diferente','nao_contrata_sistema','mencao_incidental','escopo_fora','edital_insuficiente','aderente','outro'));
alter table public.radar_review_state add column expected_scope text not null default '' check(length(expected_scope)<=500);
alter table public.radar_review_state add column source_content_hash text;
alter table public.radar_review_state add column object_hash text;
alter table public.radar_review_state add column example_object text;
alter table public.radar_review_state add column example_additional text;
create view public.radar_learning_examples with (security_invoker=true) as
 select r.opportunity_id,r.offer,r.reason_code,r.object_hash,r.example_object,r.example_additional
 from public.radar_review_state r join public.radar_opportunities o on o.id=r.opportunity_id
 where r.example_object=o.payload->>'objetoCompra'
 and r.example_additional=coalesce(o.payload->>'informacaoComplementar','');
revoke all on public.radar_learning_examples from anon,authenticated;
grant select on public.radar_learning_examples to service_role;
commit;
