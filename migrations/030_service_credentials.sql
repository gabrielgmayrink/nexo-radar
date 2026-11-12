begin;
do $$ begin
 if not exists(select 1 from pg_roles where rolname='radar_api') then create role radar_api nologin nobypassrls; end if;
end $$;
grant usage on schema public to radar_api;
grant radar_web to radar_api;
grant execute on function public.radar_search_normalize(text),public.radar_safe_timestamp(text) to radar_collector;

-- Session validation needs a credential-change fingerprint, never the password
-- hash itself or write access to provider-managed Auth tables.
create view public.radar_auth_identities with(security_barrier=true) as
 select id,email,banned_until,md5(encrypted_password) as credential_fingerprint from auth.users;
create view public.radar_verified_mfa_users with(security_barrier=true) as
 select distinct user_id from auth.mfa_factors where status='verified';
revoke all on public.radar_auth_identities,public.radar_verified_mfa_users from public,anon,authenticated;
grant select on public.radar_auth_identities,public.radar_verified_mfa_users to radar_api,service_role;

do $$ declare t text; begin
 foreach t in array array['radar_opportunities','radar_products','radar_memberships','radar_catalog_state',
  'radar_review_state','radar_review_history','radar_company_profiles','radar_profile_history',
  'radar_executions','radar_checkpoints','radar_data_sources','radar_source_links','radar_documents',
  'radar_procurement_events','radar_item_search','radar_enrichment_jobs','radar_quarantine'] loop
  execute format('grant select on public.%I to radar_api',t);
  execute format('create policy radar_api_server_read on public.%I for select to radar_api using(true)',t);
 end loop;
 foreach t in array array['radar_team_sessions','radar_auth_attempts','radar_account_security',
  'radar_account_invites','radar_login_requests','radar_mfa_pending','radar_mail_outbox'] loop
  execute format('grant select,insert,update on public.%I to radar_api',t);
  execute format('create policy radar_api_auth_write on public.%I to radar_api using(true) with check(true)',t);
 end loop;
end $$;
grant delete on public.radar_auth_attempts to radar_api;
grant usage,select on sequence public.radar_auth_attempts_id_seq to radar_api;
grant select on public.radar_catalog_source,public.radar_learning_examples to radar_api;

-- Digest delivery revalidates public records through the collection service.
grant select on public.radar_memberships to radar_collector;
create policy radar_collector_memberships_read on public.radar_memberships for select to radar_collector using(true);
grant select,insert,update on public.radar_mail_outbox to radar_collector;
create policy radar_collector_mail_write on public.radar_mail_outbox to radar_collector using(true) with check(true);
commit;
