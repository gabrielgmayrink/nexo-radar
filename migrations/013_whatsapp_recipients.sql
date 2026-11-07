begin;
create table public.radar_whatsapp_recipients (
 company_id text not null references public.radar_products(id),
 phone_e164 text not null check (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
 enabled boolean not null default false,
 created_at timestamptz not null default now(),
 primary key(company_id,phone_e164)
);
alter table public.radar_whatsapp_recipients enable row level security;
revoke all on public.radar_whatsapp_recipients from anon,authenticated;
grant select,insert,update,delete on public.radar_whatsapp_recipients to service_role;
commit;
