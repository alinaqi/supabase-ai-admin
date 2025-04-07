#!/usr/bin/env python3
import os
import requests
import json
import subprocess
import tempfile
import time
import argparse
from dotenv import load_dotenv
import anthropic
import sys
from tqdm import tqdm

# Load environment variables from .env file (if it exists)
load_dotenv()

# Configuration for production
PROD_SUPABASE_URL = os.getenv("PROD_SUPABASE_URL")
PROD_SUPABASE_PUBLIC_KEY = os.getenv("PROD_SUPABASE_PUBLIC_KEY")
PROD_SUPABASE_SERVICE_KEY = os.getenv("PROD_SUPABASE_SERVICE_KEY")

# Configuration for staging
STAGING_SUPABASE_URL = os.getenv("STAGING_SUPABASE_URL")
STAGING_SUPABASE_PUBLIC_KEY = os.getenv("STAGING_SUPABASE_PUBLIC_KEY")
STAGING_SUPABASE_SERVICE_KEY = os.getenv("STAGING_SUPABASE_SERVICE_KEY")

# Configuration for local PostgreSQL
LOCAL_PG_CONNECTION = os.getenv("LOCAL_PG_CONNECTION", "postgresql://postgres:postgres@localhost:5432/postgres")

# Anthropic API Key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def check_environment_vars(mode):
    """Check if all required environment variables are set based on the mode."""
    if mode in ["prod-to-staging", "staging-to-prod", "both"]:
        required_vars = [
            "PROD_SUPABASE_URL", "PROD_SUPABASE_SERVICE_KEY",
            "STAGING_SUPABASE_URL", "STAGING_SUPABASE_SERVICE_KEY"
        ]
    elif mode == "prod-to-local":
        required_vars = ["PROD_SUPABASE_URL", "PROD_SUPABASE_SERVICE_KEY"]
    elif mode == "staging-to-local":
        required_vars = ["STAGING_SUPABASE_URL", "STAGING_SUPABASE_SERVICE_KEY"]
    else:
        print(f"Unsupported mode: {mode}")
        exit(1)
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set these variables in your environment or create a .env file with the following format:")
        print("\n".join([f"{var}=your_{var.lower()}_value" for var in missing_vars]))
        exit(1)

def get_db_connection_string(url, service_key):
    """Extract host and database from Supabase URL and create a PostgreSQL connection string."""
    if not url or not service_key:
        return None
        
    # Extract the host from the URL (remove https:// and trailing slash if present)
    host = url.replace("https://", "").strip("/").split(".")[0]
    db_host = f"{host}.supabase.co"
    db_port = 5432
    db_name = "postgres"
    db_user = "postgres"
    db_password = service_key
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def get_tables(connection_string):
    """Get all user-defined tables in the public schema."""
    cmd = [
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-acl",
        "--schema=public",
        connection_string
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error executing pg_dump: {result.stderr}")
        exit(1)
    
    schema_dump = result.stdout
    
    # Write the schema to a temporary file for analysis
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sql') as temp_file:
        temp_file.write(schema_dump)
        temp_file_path = temp_file.name
    
    # Extract table names using grep
    grep_cmd = ["grep", "-E", "^CREATE TABLE public\\.", temp_file_path]
    grep_result = subprocess.run(grep_cmd, capture_output=True, text=True)
    
    # Clean up the temporary file
    os.unlink(temp_file_path)
    
    if grep_result.returncode > 1:  # grep returns 0 for match, 1 for no match, >1 for error
        print(f"Error extracting table names: {grep_result.stderr}")
        return []
    
    table_lines = grep_result.stdout.strip().split('\n')
    tables = []
    
    # Handle the case where no tables are found
    if table_lines == ['']:
        return []
    
    for line in table_lines:
        if line:
            # Extract table name from CREATE TABLE statement
            # Example: CREATE TABLE public.users (
            table_name = line.split('CREATE TABLE public.')[1].split(' ')[0].strip('(').strip()
            tables.append(table_name)
    
    return tables

def get_table_schema(connection_string, table_name):
    """Get the schema for a specific table."""
    cmd = [
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-acl",
        "--table=public." + table_name,
        connection_string
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error getting schema for table {table_name}: {result.stderr}")
        return None
    
    return result.stdout

def get_full_schema(connection_string):
    """Get the full schema of the database."""
    cmd = [
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-acl",
        "--schema=public",
        connection_string
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error executing pg_dump: {result.stderr}")
        exit(1)
    
    return result.stdout

def execute_sql(connection_string, sql):
    """Execute SQL commands against a database."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sql') as temp_file:
        temp_file.write(sql)
        temp_file_path = temp_file.name
    
    cmd = [
        "psql",
        connection_string,
        "-f", temp_file_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Clean up the temporary file
    os.unlink(temp_file_path)
    
    if result.returncode != 0:
        print(f"Error executing SQL: {result.stderr}")
        return False
    
    return True

def sync_schema(source_conn, target_conn, only_missing=False):
    """
    Sync schema from source to target.
    
    Parameters:
    - source_conn: Connection string for the source database
    - target_conn: Connection string for the target database
    - only_missing: If True, only add tables that don't exist in the target
    
    Returns:
    - list of tables that were synced
    """
    source_tables = get_tables(source_conn)
    
    if not source_tables:
        print("No tables found in the source database.")
        return []
    
    target_tables = get_tables(target_conn)
    
    tables_to_sync = []
    
    if only_missing:
        # Only sync tables that don't exist in the target
        tables_to_sync = [t for t in source_tables if t not in target_tables]
    else:
        # Sync all tables from source
        tables_to_sync = source_tables
    
    synced_tables = []
    
    # Use tqdm for progress bar
    for table in tqdm(tables_to_sync, desc="Syncing tables"):
        print(f"Syncing table: {table}")
        
        # Get the table schema from source
        schema_sql = get_table_schema(source_conn, table)
        
        if not schema_sql:
            print(f"Skipping table {table} due to error getting schema")
            continue
        
        # If the table exists in target and we're not only syncing missing tables,
        # we need to drop it first to avoid conflicts
        if table in target_tables and not only_missing:
            drop_sql = f"DROP TABLE IF EXISTS public.{table} CASCADE;"
            if not execute_sql(target_conn, drop_sql):
                print(f"Failed to drop table {table} in target database")
                continue
        
        # Apply the schema to the target
        if execute_sql(target_conn, schema_sql):
            synced_tables.append(table)
            print(f"Successfully synced table: {table}")
        else:
            print(f"Failed to sync table: {table}")
    
    return synced_tables

def clone_full_schema(source_conn, target_conn):
    """
    Clone the entire schema from source to target.
    
    Parameters:
    - source_conn: Connection string for the source database
    - target_conn: Connection string for the target database
    
    Returns:
    - True if successful, False otherwise
    """
    # Get the source schema
    schema_sql = get_full_schema(source_conn)
    
    if not schema_sql:
        print("Failed to get source schema")
        return False
    
    # Drop all existing tables in the target database
    drop_sql = """
    DO $$ 
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
            EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
    END $$;
    """
    
    if not execute_sql(target_conn, drop_sql):
        print("Failed to drop existing tables in target database")
        return False
    
    # Apply the schema to the target
    if not execute_sql(target_conn, schema_sql):
        print("Failed to apply schema to target database")
        return False
    
    print("Successfully cloned the full schema to the target database")
    return True

def clone_data(source_conn, target_conn, table_name):
    """
    Clone data from source to target for a specific table.
    
    Parameters:
    - source_conn: Connection string for the source database
    - target_conn: Connection string for the target database
    - table_name: Name of the table to clone data from
    
    Returns:
    - True if successful, False otherwise
    """
    # First, truncate the target table to avoid duplicate entries
    truncate_sql = f"TRUNCATE TABLE public.{table_name} CASCADE;"
    if not execute_sql(target_conn, truncate_sql):
        print(f"Failed to truncate table {table_name} in target database")
        return False
    
    # Dump data from source table
    dump_cmd = [
        "pg_dump",
        "--data-only",
        "--no-owner",
        "--no-acl",
        "--table=public." + table_name,
        source_conn
    ]
    
    dump_result = subprocess.run(dump_cmd, capture_output=True, text=True)
    
    if dump_result.returncode != 0:
        print(f"Error dumping data for table {table_name}: {dump_result.stderr}")
        return False
    
    data_sql = dump_result.stdout
    
    # Apply data to target
    if not execute_sql(target_conn, data_sql):
        print(f"Failed to import data for table {table_name} to target database")
        return False
    
    print(f"Successfully cloned data for table {table_name}")
    return True

def clone_full_data(source_conn, target_conn, tables=None):
    """
    Clone data for all tables or a specific list of tables.
    
    Parameters:
    - source_conn: Connection string for the source database
    - target_conn: Connection string for the target database
    - tables: Optional list of tables to clone data from. If None, all tables are used.
    
    Returns:
    - list of tables that were successfully cloned
    """
    if tables is None:
        tables = get_tables(source_conn)
    
    if not tables:
        print("No tables to clone data from")
        return []
    
    cloned_tables = []
    
    for table in tables:
        if clone_data(source_conn, target_conn, table):
            cloned_tables.append(table)
    
    return cloned_tables

def get_anthropic_guidance():
    """Get guidance from Anthropic on how to use the script."""
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set in the .env file.")
        return

    client = anthropic.Client(api_key=ANTHROPIC_API_KEY)
    prompt = "How do I use the Supabase administration script?"
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    print(response.content)

def main():
    parser = argparse.ArgumentParser(description="AI-Powered Supabase Administration Script")
    parser.add_argument("--mode", choices=["prod-to-staging", "staging-to-prod", "prod-to-local", "staging-to-local", "both"], default="both", help="Operation mode")
    parser.add_argument("--with-data", action="store_true", help="Include data when cloning to a local database")
    parser.add_argument("--only-missing", action="store_true", help="Only add tables that don't exist in the target")
    parser.add_argument("--guide", action="store_true", help="Get guidance from Anthropic on how to use the script")
    args = parser.parse_args()

    if args.guide:
        get_anthropic_guidance()
        return

    # If no arguments are provided, prompt the user for their desired action
    if len(sys.argv) == 1:
        print("Welcome to the AI-Powered Supabase Administration Script!")
        print("What would you like to do?")
        print("1. Sync schema between production and staging")
        print("2. Clone production schema to local PostgreSQL")
        print("3. Clone staging schema to local PostgreSQL")
        print("4. Get guidance from Anthropic")
        choice = input("Enter your choice (1-4): ")

        if choice == "1":
            args.mode = "both"
        elif choice == "2":
            args.mode = "prod-to-local"
        elif choice == "3":
            args.mode = "staging-to-local"
        elif choice == "4":
            get_anthropic_guidance()
            return
        else:
            print("Invalid choice. Exiting.")
            return

    # Check environment variables based on the mode
    check_environment_vars(args.mode)

    # Execute the corresponding sync or clone operation based on the mode
    if args.mode == "prod-to-staging":
        source_conn = get_db_connection_string(PROD_SUPABASE_URL, PROD_SUPABASE_SERVICE_KEY)
        target_conn = get_db_connection_string(STAGING_SUPABASE_URL, STAGING_SUPABASE_SERVICE_KEY)
        sync_schema(source_conn, target_conn, args.only_missing)
    elif args.mode == "staging-to-prod":
        source_conn = get_db_connection_string(STAGING_SUPABASE_URL, STAGING_SUPABASE_SERVICE_KEY)
        target_conn = get_db_connection_string(PROD_SUPABASE_URL, PROD_SUPABASE_SERVICE_KEY)
        sync_schema(source_conn, target_conn, args.only_missing)
    elif args.mode == "prod-to-local":
        source_conn = get_db_connection_string(PROD_SUPABASE_URL, PROD_SUPABASE_SERVICE_KEY)
        clone_full_schema(source_conn, LOCAL_PG_CONNECTION)
        if args.with_data:
            clone_data(source_conn, LOCAL_PG_CONNECTION)
    elif args.mode == "staging-to-local":
        source_conn = get_db_connection_string(STAGING_SUPABASE_URL, STAGING_SUPABASE_SERVICE_KEY)
        clone_full_schema(source_conn, LOCAL_PG_CONNECTION)
        if args.with_data:
            clone_data(source_conn, LOCAL_PG_CONNECTION)
    elif args.mode == "both":
        source_conn = get_db_connection_string(PROD_SUPABASE_URL, PROD_SUPABASE_SERVICE_KEY)
        target_conn = get_db_connection_string(STAGING_SUPABASE_URL, STAGING_SUPABASE_SERVICE_KEY)
        sync_schema(source_conn, target_conn, args.only_missing)
        sync_schema(target_conn, source_conn, args.only_missing)

if __name__ == "__main__":
    main()