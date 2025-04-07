# Supabase Schema Sync

A Python utility for syncing and cloning schemas between Supabase projects and local PostgreSQL databases.

## Features

- Sync schema between Supabase projects (production ↔ staging)
- Clone Supabase projects to a local PostgreSQL database
- Selectively sync only tables that don't exist in the target
- Option to include data when cloning to a local database
- Preserves complete database structure:
  - Tables, columns, and constraints
  - Row Level Security (RLS) policies
  - Functions and stored procedures
  - Triggers
  - Custom types

## Prerequisites

- Python 3.6 or higher
- PostgreSQL client tools (`pg_dump` and `psql`) installed and available in your PATH
- `python-dotenv` package

## Installation

1. Clone or download this repository
2. Run the prerequisites check script to ensure all dependencies are installed:
   ```bash
   python check_prerequisites.py
   ```
   This script will:
   - Check if PostgreSQL client tools (`psql` and `pg_dump`) are installed
   - Install them automatically if they're missing (on supported platforms)
   - Verify and install required Python packages
3. Create a `.env` file based on the template (see Configuration section)
4. Make the main script executable:
   ```bash
   chmod +x supabase-sync-script.py
   ```

## Configuration

Create a `.env` file with the following variables:

```
# Production Supabase Configuration
PROD_SUPABASE_URL=https://your-production-project-id.supabase.co
PROD_SUPABASE_PUBLIC_KEY=your_production_public_key
PROD_SUPABASE_SERVICE_KEY=your_production_service_key

# Staging Supabase Configuration
STAGING_SUPABASE_URL=https://your-staging-project-id.supabase.co
STAGING_SUPABASE_PUBLIC_KEY=your_staging_public_key
STAGING_SUPABASE_SERVICE_KEY=your_staging_service_key

# Local PostgreSQL Configuration
# Format: postgresql://username:password@hostname:port/database_name
LOCAL_PG_CONNECTION=postgresql://postgres:postgres@localhost:5432/postgres
```

Notes:
- Get your Supabase URL and keys from the Supabase dashboard (Project Settings > API)
- The Service Key (aka "service_role key") is required for schema operations
- Update the local PostgreSQL connection string according to your setup

## Usage

### Basic Usage

To sync schema between production and staging (default mode):

```bash
python supabase-sync-script.py
```

This will:
1. Sync tables from production to staging that don't exist in staging
2. Sync tables from staging to production that don't exist in production

### Operation Modes

The script supports several operation modes:

```bash
python supabase-sync-script.py --mode MODE [--with-data] [--only-missing]
```

Available modes:
- `both` (default): Sync production to staging and staging to production
- `prod-to-staging`: Sync from production to staging
- `staging-to-prod`: Sync from staging to production
- `prod-to-local`: Clone production schema to local PostgreSQL
- `staging-to-local`: Clone staging schema to local PostgreSQL
- `clone-prod`: Complete clone of production (schema and optionally data)
- `clone-staging`: Complete clone of staging (schema and optionally data)

### Additional Options

- `--with-data`: Include data when cloning to a local database (only works with local cloning modes)
- `--only-missing`: Only add tables that don't exist in the target

### Examples

Clone production to local PostgreSQL with data:
```bash
python supabase-sync-script.py --mode prod-to-local --with-data
```

Clone staging to local PostgreSQL with data:
```bash
python supabase-sync-script.py --mode staging-to-local --with-data
```

Only sync new tables from production to staging:
```bash
python supabase-sync-script.py --mode prod-to-staging --only-missing
```

Only sync new tables from staging to production:
```bash
python supabase-sync-script.py --mode staging-to-prod --only-missing
```

## How It Works

The script:
1. Connects to the source and target databases
2. Extracts schema using `pg_dump`
3. Identifies tables to sync based on your options
4. Drops tables in the target if needed 
5. Applies schema to the target database
6. Optionally copies data (for local cloning operations)

## Troubleshooting

### Common Issues

- **Connection errors**: Check your Supabase URL, service keys, and local PostgreSQL connection string
- **Missing `pg_dump` or `psql`**: Run `python check_prerequisites.py` to install PostgreSQL client tools
- **Permission issues**: Check that your service keys have sufficient permissions
- **Local database connection**: Verify the local PostgreSQL server is running and accessible
- **Installation errors on Windows**: If automatic installation fails on Windows, download and install PostgreSQL tools manually from the [official website](https://www.postgresql.org/download/windows/)

### Debug Tips

- Check the output for specific error messages
- Try connecting to both source and target databases manually using `psql`
- Verify your connection strings are correctly formatted

## Notes

- This script is designed for development and testing purposes
- Always back up your data before running schema synchronization
- The script includes full database schema transfer including:
  - Tables and constraints
  - Row Level Security (RLS) policies
  - Functions and stored procedures
  - Triggers
  - Custom types
- Use caution when syncing production environments