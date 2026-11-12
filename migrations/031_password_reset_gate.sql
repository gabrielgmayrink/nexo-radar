begin;
alter table public.radar_account_security add column password_reset_required boolean not null default false;
commit;
