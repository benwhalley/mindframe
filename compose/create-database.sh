#!/bin/bash
set -e
trap 'echo "Error occurred at line $LINENO"; exit 1' ERR

# Ensure the required arguments are provided
if [ $# -ne 3 ]; then
    echo "Usage: $0 USER_NAME DB_NAME PASSWORD"
    exit 1
fi

USER_NAME=$1
DB_NAME=$2
PASSWORD=$3

echo "Creating database: $DB_NAME and user: $USER_NAME (if not already exists)"

# Check if the database exists, create it if not
DB_EXISTS=$(psql --username "$POSTGRES_USER" -t -c "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" | xargs)
if [[ -z "$DB_EXISTS" ]]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE \"$DB_NAME\";"
    echo "Database $DB_NAME created."
else
    echo "Database $DB_NAME already exists."
fi

# Create the user and set up privileges/extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the user if it does not exist
    DO \$\$
    BEGIN
        IF NOT EXISTS (
            SELECT FROM pg_catalog.pg_roles
            WHERE rolname = '$USER_NAME'
        ) THEN
            CREATE USER "$USER_NAME" WITH PASSWORD '$PASSWORD';
        END IF;
    END
    \$\$;

    -- Grant all privileges on the database to the user
    GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$USER_NAME";
EOSQL

# Switch to the target database to configure extensions and schema permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
    -- Add extensions if supported
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Ensure the user can manage objects in the public schema
    GRANT USAGE ON SCHEMA public TO "$USER_NAME";
    GRANT CREATE ON SCHEMA public TO "$USER_NAME";
    ALTER SCHEMA public OWNER TO "$USER_NAME";
EOSQL

echo "Database $DB_NAME and user $USER_NAME created and configured successfully (if they did not already exist)."
