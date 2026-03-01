-- List all tables in the public schema
select tablename
from pg_tables
where schemaname = 'public'
order by tablename;
