begin;
-- Presentation cards are reproducible from the intact official payload. The
-- paginated discovery/review paths regenerate them for the requested page.
-- Keep source bytes, hashes, scores, observations and team decisions unchanged.
update public.radar_opportunities set card=null where score<40 and card is not null;
commit;
