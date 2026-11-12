-- No login, password, browser grant, or role switch is created by this migration.
-- The owner must attach these roles to separate server-only credentials later.
begin;
do $$ begin
 if not exists(select 1 from pg_roles where rolname='radar_web') then create role radar_web nologin nobypassrls; end if;
 if not exists(select 1 from pg_roles where rolname='radar_collector') then create role radar_collector nologin nobypassrls; end if;
end $$;
grant usage on schema public to radar_web,radar_collector;
do $$ declare t text; begin
 foreach t in array array['radar_opportunities','radar_catalog_state','radar_procurement_events','radar_data_sources',
   'radar_source_links','radar_documents'] loop
  if to_regclass('public.'||t) is not null then
   execute format('grant select on public.%I to radar_web',t);
   execute format('create policy radar_web_public_read on public.%I for select to radar_web using (true)',t);
  end if;
 end loop;
 foreach t in array array['radar_review_state','radar_review_history','radar_company_profiles','radar_profile_history'] loop
  execute format('grant select,insert on public.%I to radar_web',t);
  if t in ('radar_review_state','radar_company_profiles') then execute format('grant update on public.%I to radar_web',t); end if;
  execute format('create policy radar_web_company_scope on public.%I to radar_web using
   (company_id=current_setting(''radar.company_id'',true) and exists
    (select 1 from public.radar_memberships m where m.company_id=%I.company_id and m.email=current_setting(''radar.actor_email'',true)))
   with check (company_id=current_setting(''radar.company_id'',true) and exists
    (select 1 from public.radar_memberships m where m.company_id=%I.company_id and m.email=current_setting(''radar.actor_email'',true)
     and m.role=any(%L::text[])))',t,t,t,
     case when t in ('radar_company_profiles','radar_profile_history') then '{owner,admin}' else '{owner,admin,analyst}' end);
 end loop;
end $$;
grant select on public.radar_memberships to radar_web;
create policy radar_web_own_membership on public.radar_memberships for select to radar_web
 using(email=current_setting('radar.actor_email',true) and company_id=current_setting('radar.company_id',true));
grant select on public.radar_products to radar_web;
create policy radar_web_own_product on public.radar_products for select to radar_web
 using(id=current_setting('radar.company_id',true));
grant select on public.radar_catalog_source,public.radar_learning_examples to radar_web;
grant execute on function public.radar_search_normalize(text),public.radar_safe_timestamp(text) to radar_web;
grant usage,select on sequence public.radar_review_history_id_seq,public.radar_profile_history_id_seq to radar_web;
do $$ declare t text; begin
 foreach t in array array['radar_opportunities','radar_raw','radar_executions','radar_checkpoints','radar_catalog_state','radar_national_pages',
  'radar_raw_payloads','radar_source_pages','radar_source_observations','radar_quarantine','radar_reclassification_jobs',
  'radar_procurement_events','radar_procurement_items','radar_item_snapshots','radar_item_pages',
  'radar_data_sources','radar_source_receipts','radar_source_links','radar_enrichment_jobs','radar_documents'] loop
  if to_regclass('public.'||t) is not null then
   execute format('grant select,insert,update,delete on public.%I to radar_collector',t);
   execute format('create policy radar_collector_write on public.%I to radar_collector using (true) with check (true)',t);
  end if;
 end loop;
end $$;
grant select on public.radar_products,public.radar_review_state,public.radar_company_profiles to radar_collector;
create policy radar_collector_products on public.radar_products for select to radar_collector using(true);
create policy radar_collector_reviews on public.radar_review_state for select to radar_collector using(true);
create policy radar_collector_profiles on public.radar_company_profiles for select to radar_collector using(true);
-- Identity sequence permissions follow the granted tables only.
do $$ declare sequence_name text; table_name text; begin
 for sequence_name,table_name in select quote_ident(n.nspname)||'.'||quote_ident(s.relname),t.relname
  from pg_class s join pg_namespace n on n.oid=s.relnamespace
  join pg_depend d on d.objid=s.oid and d.deptype in ('a','i')
  join pg_class t on t.oid=d.refobjid where s.relkind='S' and n.nspname='public' loop
  if has_table_privilege('radar_collector','public.'||quote_ident(table_name),'INSERT') then
   execute 'grant usage,select on sequence '||sequence_name||' to radar_collector';
  end if;
 end loop;
end $$;
commit;
