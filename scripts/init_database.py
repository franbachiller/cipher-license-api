#!/usr/bin/env python3
"""
Database initialization script for VPS-Based Streaming License System.

This script creates the database schema and verifies the setup.
Run this after setting up your PostgreSQL database or Supabase project.

Usage:
    python init_database.py [--schema-file SCHEMA_FILE]

Requirements: 8.1, 8.2, 27.4
"""

import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), 'api_server', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

# Import after loading env
import psycopg2
from psycopg2 import sql


def read_schema_file(schema_file: str) -> str:
    """
    Read SQL schema file.
    
    Args:
        schema_file: Path to schema SQL file
    
    Returns:
        SQL content as string
    """
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Schema file not found: {schema_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading schema file: {e}")
        sys.exit(1)


def execute_schema(conn, schema_sql: str) -> None:
    """
    Execute schema SQL statements.
    
    Args:
        conn: Database connection
        schema_sql: SQL statements to execute
    """
    cursor = conn.cursor()
    try:
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        
        for statement in statements:
            # Skip comments and empty lines
            if statement.startswith('--') or not statement:
                continue
            
            # Skip psql-specific commands
            if statement.startswith('\\'):
                continue
            
            try:
                cursor.execute(statement)
                print(f"✓ Executed: {statement[:60]}...")
            except psycopg2.errors.DuplicateTable:
                print(f"⚠ Table already exists, skipping: {statement[:60]}...")
                conn.rollback()
            except Exception as e:
                print(f"✗ Error executing statement: {e}")
                print(f"  Statement: {statement[:100]}...")
                conn.rollback()
                raise
        
        conn.commit()
        print("\n✓ Schema executed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Failed to execute schema: {e}")
        raise
    finally:
        cursor.close()


def verify_schema(conn) -> bool:
    """
    Verify that all required tables exist.
    
    Args:
        conn: Database connection
    
    Returns:
        True if all tables exist, False otherwise
    """
    cursor = conn.cursor()
    try:
        # Check for required tables
        required_tables = ['licenses', 'sessions', 'auth_logs']
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print("\n" + "=" * 60)
        print("DATABASE SCHEMA VERIFICATION")
        print("=" * 60)
        
        print(f"\nExisting tables ({len(existing_tables)}):")
        for table in existing_tables:
            print(f"  ✓ {table}")
        
        missing_tables = [t for t in required_tables if t not in existing_tables]
        
        if missing_tables:
            print(f"\n✗ Missing required tables:")
            for table in missing_tables:
                print(f"  ✗ {table}")
            return False
        
        print(f"\n✓ All required tables exist")
        
        # Verify indexes
        cursor.execute("""
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        indexes = cursor.fetchall()
        print(f"\nIndexes ({len(indexes)}):")
        for idx_name, table_name in indexes:
            print(f"  ✓ {table_name}.{idx_name}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        return False
    finally:
        cursor.close()


def main():
    """Main initialization function."""
    parser = argparse.ArgumentParser(
        description='Initialize database schema for VPS-Based Streaming License System'
    )
    parser.add_argument(
        '--schema-file',
        default='schema_supabase.sql',
        help='Path to schema SQL file (default: schema_supabase.sql)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("DATABASE INITIALIZATION")
    print("=" * 60)
    
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("\n✗ Error: DATABASE_URL environment variable not set")
        print("  Make sure api_server/.env file exists and contains DATABASE_URL")
        sys.exit(1)
    
    # Mask password in URL for display
    display_url = database_url
    if '@' in display_url:
        parts = display_url.split('@')
        if ':' in parts[0]:
            user_pass = parts[0].split(':')
            display_url = f"{user_pass[0]}:****@{parts[1]}"
    
    print(f"\nDatabase URL: {display_url}")
    
    # Read schema file
    print(f"\nReading schema file: {args.schema_file}")
    schema_sql = read_schema_file(args.schema_file)
    print(f"✓ Schema file loaded ({len(schema_sql)} characters)")
    
    # Connect to database
    print("\nConnecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        print("✓ Connected successfully")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    try:
        # Execute schema
        print("\nExecuting schema...")
        execute_schema(conn, schema_sql)
        
        # Verify schema
        if verify_schema(conn):
            print("\n" + "=" * 60)
            print("✓ DATABASE INITIALIZATION COMPLETE")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Create a test license: python admin.py create --expires '2025-12-31' --sessions 1")
            print("2. Start the API server: python api_server/app.py")
            print("3. Test authentication: curl -X POST http://localhost:5000/api/auth -H 'Content-Type: application/json' -d '{\"license_key\":\"YOUR_KEY\"}'")
        else:
            print("\n" + "=" * 60)
            print("✗ DATABASE INITIALIZATION INCOMPLETE")
            print("=" * 60)
            print("\nSome tables or indexes are missing. Check the errors above.")
            sys.exit(1)
            
    finally:
        conn.close()


if __name__ == '__main__':
    main()
