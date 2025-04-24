-- Allow usage of the public schema
GRANT USAGE ON SCHEMA public TO mf;

-- All existing tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mf;

-- All existing sequences (needed for autoincrement columns)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mf;

-- All existing functions (optional, e.g. if using stored procs)
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO mf;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mf;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO mf;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO mf;
