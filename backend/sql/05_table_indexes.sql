-- Show indexes for a specific table
-- Replace 'users' with your table name
select
  indexname,
  indexdef
from pg_indexes
where schemaname = 'public'
  and tablename = 'users'
order by indexname;
