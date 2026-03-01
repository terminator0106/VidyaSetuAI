-- Common tables this backend typically creates
-- Run 01_list_tables.sql first if you're not sure what exists.

-- Users
select * from public.users order by id desc limit 50;

-- Textbooks
select * from public.textbooks order by id desc limit 50;

-- Sessions
select * from public.sessions order by id desc limit 50;
