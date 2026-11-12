begin;
-- PostgreSQL databases with C locale do not lowercase accented capitals.
create or replace function public.radar_search_normalize(value text) returns text
language sql immutable parallel safe set search_path=pg_catalog as $$
 select btrim(regexp_replace(translate(lower(coalesce(value,'')),
 'áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ',
 'aaaaaeeeeiiiiooooouuuucnaaaaaeeeeiiiiooooouuuucn'),'[^a-z0-9]+',' ','g'))
$$;
commit;
