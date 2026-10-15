-- Runtime roles: non-superusers without row-level-security bypass.
CREATE ROLE cp_app LOGIN PASSWORD 'cp_app_local' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE cp_dispatcher LOGIN PASSWORD 'cp_dispatcher_local' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE caseproof TO cp_app, cp_dispatcher;
CREATE DATABASE caseproof_test OWNER cp_owner;
GRANT CONNECT ON DATABASE caseproof_test TO cp_app, cp_dispatcher;
