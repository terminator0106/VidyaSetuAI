-- Approx row counts for each user table (fast)
select
  schemaname,
  relname as table_name,
  n_live_tup as approx_rows
from pg_stat_user_tables
order by approx_rows desc;
