begin;
-- FOR SHARE requires UPDATE privilege even though it does not change rows.
-- Expose only the public source read+lock, without granting web UPDATE access
-- to the canonical procurement table or bypassing private company RLS.
create function public.radar_lock_review_source(identifier text,product text)
 returns table(payload jsonb,content_hash text)
language sql volatile security definer set search_path=pg_catalog as $$
 select o.payload,o.content_hash from public.radar_opportunities o
 where o.id=identifier and product in ('Public','Gerico')
 and (coalesce((o.product_scores->>product)::int,0)>=40 or o.national_execution_id is not null)
 for share
$$;
revoke all on function public.radar_lock_review_source(text,text) from public,anon,authenticated;
grant execute on function public.radar_lock_review_source(text,text) to radar_web,service_role;
commit;
