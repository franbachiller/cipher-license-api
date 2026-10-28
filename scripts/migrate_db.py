#!/usr/bin/env python3
"""
Database Migration Script for VPS-Based Streaming License System
Initializes PostgreSQL database with required schema

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_db_config():
    """
    Load database configuration from environment variables.
    
    Required environment variables:
    - DB_HOST: PostgreSQL host (default: localhost)
    - DB_PORT: PostgreSQL port (default: 5432)
    - DB_NAME: Database name (default: cipher_license)
    - DB_USER: Database user (default: postgres)
    - DB_PASSWORD: Database password (required)
    """
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'cipher_license'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD')
    }


def create_database_if_not_exists(config):
    """
    Create the database if it doesn't exist.
    
    Args:
        config: Database configuration dictionary
    """
    # Connect to PostgreSQL server (not specific database)
    conn = psycopg2.connect(
        host=config['host'],
        port=config['port'],
        user=config['user'],
        password=config['password'],
        database='postgres'  # Connect to default database
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (config['database'],)
        )
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database '{config['database']}'...")
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(config['database'])
                )
            )
            print(f"Database '{config['database']}' created successfully!")
        else:
            print(f"Database '{config['database']}' already exists.")
    
    finally:
        cursor.close()
        conn.close()


def run_migration(config):
    """
    Run the database migration by executing schema.sql.
    
    Args:
        config: Database configuration dictionary
    """
    # Read schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    
    if not os.path.exists(schema_path):
        print(f"Error: schema.sql not found at {schema_path}")
        sys.exit(1)
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Connect to the target database
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    try:
        print("Running database migration...")
        
        # Execute schema SQL
        cursor.execute(schema_sql)
        conn.commit()
        
        print("Migration completed successfully!")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print("\nCreated tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Verify indexes were created
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY indexname
        """)
        indexes = cursor.fetchall()
        
        print(f"\nCreated indexes: {len(indexes)} total")
        for index in indexes:
            print(f"  - {index[0]}")
    
    except psycopg2.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        cursor.close()
        conn.close()


def verify_schema(config):
    """
    Verify that the schema was created correctly.
    
    Args:
        config: Database configuration dictionary
    """
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    try:
        print("\nVerifying schema...")
        
        # Check licenses table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'licenses'
            ORDER BY ordinal_position
        """)
        licenses_columns = cursor.fetchall()
        
        print("\nLicenses table columns:")
        for col in licenses_columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
        
        # Check sessions table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'sessions'
            ORDER BY ordinal_position
        """)
        sessions_columns = cursor.fetchall()
        
        print("\nSessions table columns:")
        for col in sessions_columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
        
        # Check foreign key constraints
        cursor.execute("""
            SELECT
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'sessions'
        """)
        foreign_keys = cursor.fetchall()
        
        print("\nForeign key constraints:")
        for fk in foreign_keys:
            print(f"  - {fk[0]}: {fk[1]}.{fk[2]} -> {fk[3]}.{fk[4]}")
        
        # Check unique constraints
        cursor.execute("""
            SELECT constraint_name, table_name
            FROM information_schema.table_constraints
            WHERE constraint_type = 'UNIQUE'
            AND table_name IN ('licenses', 'sessions')
        """)
        unique_constraints = cursor.fetchall()
        
        print("\nUnique constraints:")
        for uc in unique_constraints:
            print(f"  - {uc[0]} on {uc[1]}")
        
        print("\n✓ Schema verification complete!")
    
    finally:
        cursor.close()
        conn.close()


def main():
    """Main migration function."""
    print("=" * 60)
    print("VPS-Based Streaming License System - Database Migration")
    print("=" * 60)
    
    # Load configuration
    config = get_db_config()
    
    # Check if password is provided
    if not config['password']:
        print("Error: DB_PASSWORD environment variable is required")
        print("\nUsage:")
        print("  export DB_PASSWORD='your_password'")
        print("  python migrate_db.py")
        sys.exit(1)
    
    print(f"\nDatabase Configuration:")
    print(f"  Host: {config['host']}")
    print(f"  Port: {config['port']}")
    print(f"  Database: {config['database']}")
    print(f"  User: {config['user']}")
    print()
    
    try:
        # Step 1: Create database if it doesn't exist
        create_database_if_not_exists(config)
        
        # Step 2: Run migration
        run_migration(config)
        
        # Step 3: Verify schema
        verify_schema(config)
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
    
    except psycopg2.Error as e:
        print(f"\nDatabase error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
