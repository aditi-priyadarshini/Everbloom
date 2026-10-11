do $$ begin if not exists(select 1 from pg_roles where rolname='authenticator') then create role authenticator login noinherit password 'pw'; end if; end $$;
grant anon, service_role to authenticator;
grant usage on schema public to anon, service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;
