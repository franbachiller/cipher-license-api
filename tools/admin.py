#!/usr/bin/env python3
"""
Admin CLI Tool for VPS-Based Streaming License System

This tool provides command-line interface for managing licenses and sessions
in the new license key-based system (not HWID-based).

Usage:
    python admin.py create --expires YYYY-MM-DD --sessions N [--note "text"]
    python admin.py revoke --key LICENSE_KEY
    python admin.py extend --key LICENSE_KEY --expires YYYY-MM-DD
    python admin.py list [--status STATUS] [--limit N]
    python admin.py sessions [--key LICENSE_KEY]

Requirements: 10.1, 10.2, 10.3
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def init_database():
    """Initialize database connection pool."""
    # Import here to avoid initialization on module load
    from api_server.database import db_pool
    from api_server.config import Config
    
    try:
        db_pool.initialize()
        return db_pool, Config
    except Exception as e:
        print(f"Error: Failed to connect to database: {e}")
        from api_server.config import Config
        print(f"Database URL: {Config.DATABASE_URL}")
        sys.exit(1)


def parse_date(date_str: str) -> datetime:
    """
    Parse date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object
        
    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")


def cmd_create(args):
    """
    Create a new license key.
    
    Args:
        args: Parsed command-line arguments
    """
    from api_server.models import License
    from api_server.utils.key_generator import generate_license_key
    from api_server.database import db_pool
    
    try:
        # Parse expiration date
        expires_at = parse_date(args.expires)
        
        # Validate max_sessions
        if args.sessions < 1:
            print("Error: --sessions must be at least 1")
            sys.exit(1)
        
        # Generate unique license key
        license_key = generate_license_key()
        
        # Create license in database
        with db_pool.get_cursor(commit=True) as cursor:
            license = License.create(
                cursor=cursor,
                key=license_key,
                expires_at=expires_at,
                max_sessions=args.sessions,
                note=args.note or ''
            )
        
        # Display success message
        print("\n✅ License created successfully!")
        print(f"   License Key:  {license.key}")
        print(f"   Status:       {license.status}")
        print(f"   Expires:      {license.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Max Sessions: {license.max_sessions}")
        if license.note:
            print(f"   Note:         {license.note}")
        print()
        
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to create license: {e}")
        sys.exit(1)


def cmd_revoke(args):
    """
    Revoke a license key and terminate all active sessions.
    
    Args:
        args: Parsed command-line arguments
    """
    from api_server.models import License, Session
    from api_server.database import db_pool
    
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            # Check if license exists
            license = License.find_by_key(cursor, args.key)
            if not license:
                print(f"Error: License key '{args.key}' not found")
                sys.exit(1)
            
            # Update license status to revoked
            License.update_status(cursor, args.key, 'revoked')
            
            # Terminate all active sessions
            sessions_terminated = Session.delete_by_license_key(cursor, args.key)
        
        print(f"\n✅ License revoked successfully!")
        print(f"   License Key:        {args.key}")
        print(f"   Sessions Terminated: {sessions_terminated}")
        print()
        
    except Exception as e:
        print(f"Error: Failed to revoke license: {e}")
        sys.exit(1)


def cmd_extend(args):
    """
    Extend a license expiration date.
    
    Args:
        args: Parsed command-line arguments
    """
    from api_server.models import License
    from api_server.database import db_pool
    
    try:
        # Parse new expiration date
        new_expires_at = parse_date(args.expires)
        
        with db_pool.get_cursor(commit=True) as cursor:
            # Check if license exists
            license = License.find_by_key(cursor, args.key)
            if not license:
                print(f"Error: License key '{args.key}' not found")
                sys.exit(1)
            
            # Update expiration date
            License.update_expires_at(cursor, args.key, new_expires_at)
        
        print(f"\n✅ License extended successfully!")
        print(f"   License Key:     {args.key}")
        print(f"   Old Expiration:  {license.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   New Expiration:  {new_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to extend license: {e}")
        sys.exit(1)


def cmd_list(args):
    """
    List all licenses with optional filtering.
    
    Args:
        args: Parsed command-line arguments
    """
    from api_server.models import License, Session
    from api_server.database import db_pool
    
    try:
        with db_pool.get_cursor() as cursor:
            # Get licenses with optional status filter
            licenses = License.list_all(
                cursor=cursor,
                status=args.status,
                limit=args.limit,
                offset=0
            )
            
            if not licenses:
                print("\nNo licenses found.")
                if args.status:
                    print(f"(Filter: status={args.status})")
                print()
                return
            
            # Display header
            print(f"\n{'License Key':<27} {'Status':<10} {'Expires':<20} {'Sessions':<10} {'Note':<30}")
            print("-" * 100)
            
            # Display each license
            for license in licenses:
                # Get active session count
                active_sessions = Session.count_active(cursor, license.key)
                
                # Format expiration date
                expires_str = license.expires_at.strftime('%Y-%m-%d %H:%M:%S') if license.expires_at else 'Never'
                
                # Format sessions
                sessions_str = f"{active_sessions}/{license.max_sessions}"
                
                # Truncate note if too long
                note = (license.note[:27] + '...') if license.note and len(license.note) > 30 else (license.note or '')
                
                print(f"{license.key:<27} {license.status:<10} {expires_str:<20} {sessions_str:<10} {note:<30}")
            
            # Display summary
            print("-" * 100)
            print(f"Total: {len(licenses)} license(s)")
            if args.status:
                print(f"Filter: status={args.status}")
            print()
        
    except Exception as e:
        print(f"Error: Failed to list licenses: {e}")
        sys.exit(1)


def cmd_sessions(args):
    """
    View active sessions, optionally filtered by license key.
    
    Args:
        args: Parsed command-line arguments
    """
    from api_server.models import Session
    from api_server.database import db_pool
    
    try:
        with db_pool.get_cursor() as cursor:
            if args.key:
                # Get sessions for specific license key
                sessions = Session.get_by_license_key(cursor, args.key)
                title = f"Sessions for License Key: {args.key}"
            else:
                # Get all sessions
                cursor.execute("""
                    SELECT * FROM sessions 
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                """)
                rows = cursor.fetchall()
                sessions = [Session(row) for row in rows]
                title = "All Active Sessions"
            
            if not sessions:
                print(f"\nNo active sessions found.")
                if args.key:
                    print(f"(License Key: {args.key})")
                print()
                return
            
            # Display header
            print(f"\n{title}")
            print(f"\n{'ID':<6} {'License Key':<27} {'IP Address':<16} {'Last Seen':<20} {'Expires':<20}")
            print("-" * 100)
            
            # Display each session
            for session in sessions:
                last_seen_str = session.last_seen.strftime('%Y-%m-%d %H:%M:%S') if session.last_seen else 'Never'
                expires_str = session.expires_at.strftime('%Y-%m-%d %H:%M:%S') if session.expires_at else 'Never'
                
                print(f"{session.id:<6} {session.license_key:<27} {session.ip_address:<16} {last_seen_str:<20} {expires_str:<20}")
            
            # Display summary
            print("-" * 100)
            print(f"Total: {len(sessions)} active session(s)")
            print()
        
    except Exception as e:
        print(f"Error: Failed to retrieve sessions: {e}")
        sys.exit(1)


def main():
    """Main entry point for the admin CLI tool."""
    # Create main parser
    parser = argparse.ArgumentParser(
        description='Admin CLI Tool for VPS-Based Streaming License System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a license that expires in 30 days with 1 concurrent session
  python admin.py create --expires 2024-12-31 --sessions 1 --note "Customer #12345"
  
  # Revoke a license
  python admin.py revoke --key ABCD1234EFGH5678IJKL90MNO
  
  # Extend a license to a new date
  python admin.py extend --key ABCD1234EFGH5678IJKL90MNO --expires 2025-12-31
  
  # List all active licenses
  python admin.py list --status active
  
  # View all active sessions
  python admin.py sessions
  
  # View sessions for a specific license
  python admin.py sessions --key ABCD1234EFGH5678IJKL90MNO
        """
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.required = True
    
    # Create command
    parser_create = subparsers.add_parser('create', help='Create a new license key')
    parser_create.add_argument('--expires', required=True, help='Expiration date (YYYY-MM-DD)')
    parser_create.add_argument('--sessions', type=int, required=True, help='Maximum concurrent sessions')
    parser_create.add_argument('--note', help='Optional admin note')
    parser_create.set_defaults(func=cmd_create)
    
    # Revoke command
    parser_revoke = subparsers.add_parser('revoke', help='Revoke a license key')
    parser_revoke.add_argument('--key', required=True, help='License key to revoke')
    parser_revoke.set_defaults(func=cmd_revoke)
    
    # Extend command
    parser_extend = subparsers.add_parser('extend', help='Extend license expiration date')
    parser_extend.add_argument('--key', required=True, help='License key to extend')
    parser_extend.add_argument('--expires', required=True, help='New expiration date (YYYY-MM-DD)')
    parser_extend.set_defaults(func=cmd_extend)
    
    # List command
    parser_list = subparsers.add_parser('list', help='List all licenses')
    parser_list.add_argument('--status', choices=['active', 'expired', 'revoked'], help='Filter by status')
    parser_list.add_argument('--limit', type=int, default=100, help='Maximum number of results (default: 100)')
    parser_list.set_defaults(func=cmd_list)
    
    # Sessions command
    parser_sessions = subparsers.add_parser('sessions', help='View active sessions')
    parser_sessions.add_argument('--key', help='Filter by license key')
    parser_sessions.set_defaults(func=cmd_sessions)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Initialize database
    init_database()
    
    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()
