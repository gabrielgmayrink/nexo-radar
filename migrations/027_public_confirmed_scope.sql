begin;
-- Correct legacy installation metadata; IDs, membership and review history stay intact.
update public.radar_products set profile='Assessoria e preparação de documentos e apoio administrativo especializado; assessoria em gestão empresarial pública e privada; palestras e treinamento profissional e gerencial; ensino EAD profissionalizante, técnico, graduação e pós-graduação.'
 where id='public';
commit;
