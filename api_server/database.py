"""
Database connection pooling and management using psycopg2.
"""

import psycopg2
from psycopg2 import pool, extras
from typing import Optional
import threading
from contextlib import contextmanager

from .config import Config


class DatabasePool:
    """Thread-safe PostgreSQL connection pool manager."""
    
    _instance: Optional['DatabasePool'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one pool exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the connection pool if not already initialized."""
        if not hasattr(self, '_pool'):
            self._pool = None
            self._initialized = False
    
    def initialize(self, database_url: Optional[str] = None) -> None:
        """
        Initialize the connection pool.
        
        Args:
            database_url: PostgreSQL connection URL. If None, uses Config.DATABASE_URL
        """
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            url = database_url or Config.DATABASE_URL
            
            try:
                self._pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=Config.DB_POOL_SIZE,
                    dsn=url,
                    connect_timeout=Config.DB_POOL_TIMEOUT
                )
                self._initialized = True
                print(f"Database connection pool initialized (size: {Config.DB_POOL_SIZE})")
            except Exception as e:
                print(f"Failed to initialize database pool: {e}")
                raise
    
    def get_connection(self):
        """
        Get a connection from the pool.
        
        Returns:
            psycopg2 connection object
            
        Raises:
            Exception: If pool is not initialized or no connections available
        """
        if not self._initialized or self._pool is None:
            raise Exception("Database pool not initialized. Call initialize() first.")
        
        try:
            return self._pool.getconn()
        except Exception as e:
            print(f"Failed to get connection from pool: {e}")
            raise
    
    def return_connection(self, conn) -> None:
        """
        Return a connection to the pool.
        
        Args:
            conn: psycopg2 connection object to return
        """
        if self._pool is not None:
            self._pool.putconn(conn)
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._initialized = False
            print("Database connection pool closed")
    
    @contextmanager
    def get_cursor(self, commit: bool = False):
        """
        Context manager for getting a database cursor.
        
        Args:
            commit: Whether to commit the transaction on success
            
        Yields:
            psycopg2 cursor object
            
        Example:
            with db_pool.get_cursor(commit=True) as cursor:
                cursor.execute("INSERT INTO licenses ...")
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)


# Global database pool instance
db_pool = DatabasePool()


def init_db(database_url: Optional[str] = None) -> None:
    """
    Initialize the database connection pool.
    
    Args:
        database_url: PostgreSQL connection URL. If None, uses Config.DATABASE_URL
    """
    db_pool.initialize(database_url)


def close_db() -> None:
    """Close the database connection pool."""
    db_pool.close_all()
