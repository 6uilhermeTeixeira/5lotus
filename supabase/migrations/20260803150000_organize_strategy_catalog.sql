-- Present strategy titles without their internal bot identifiers.
-- The operation is idempotent and applies to active and archived records.
update public.bots
set name = regexp_replace(name, '^Bot [0-9]+[[:space:]]+(—|-)[[:space:]]+', '')
where name ~ '^Bot [0-9]+[[:space:]]+(—|-)[[:space:]]+';
