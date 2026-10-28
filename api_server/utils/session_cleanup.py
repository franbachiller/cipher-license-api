"""
Session cleanup background task.

This module implements a background task that periodically removes expired sessions
from the database. Sessions are considered expired if:
1. The expires_at timestamp has passed (JWT expiration)
2. The last_seen timestamp is more than 90 seconds old (missed heartbeats)

The cleanup task runs every 5 minutes to maintain database hygiene and enforce
session timeout policies.

Requirements: 3.4, 3.6
"""

import threading
import time
from datetime import datetime
from typing import Optional

from ..database import db_pool
from ..models import Session
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SessionCleanupTask:
    """
    Background task for cleaning up expired sessions.
    
    This task runs in a separate thread and periodically removes expired sessions
    from the database. It can be started and stopped gracefully.
    
    Attributes:
        interval: Cleanup interval in seconds (default: 300 = 5 minutes)
        running: Flag indicating if the task is running
        thread: Background thread running the cleanup loop
    """
    
    def __init__(self, interval: int = 300):
        """
        Initialize the cleanup task.
        
        Args:
            interval: Cleanup interval in seconds (default: 300 = 5 minutes)
        """
        self.interval = interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """
        Start the cleanup task in a background thread.
        
        If the task is already running, this method does nothing.
        """
        if self.running:
            logger.warning("Session cleanup task is already running")
            return
        
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_cleanup_loop, daemon=True)
        self.thread.start()
        logger.info(f"Session cleanup task started (interval: {self.interval}s)")
    
    def stop(self) -> None:
        """
        Stop the cleanup task gracefully.
        
        This method signals the background thread to stop and waits for it to finish.
        """
        if not self.running:
            logger.warning("Session cleanup task is not running")
            return
        
        logger.info("Stopping session cleanup task...")
        self.running = False
        self._stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        
        logger.info("Session cleanup task stopped")
    
    def _run_cleanup_loop(self) -> None:
        """
        Main cleanup loop that runs in the background thread.
        
        This method runs continuously until stop() is called, performing cleanup
        at the specified interval.
        """
        logger.info("Session cleanup loop started")
        
        while self.running:
            try:
                # Perform cleanup
                self._cleanup_expired_sessions()
                
                # Wait for next interval or stop signal
                # Use wait() instead of sleep() to allow immediate stop
                if self._stop_event.wait(timeout=self.interval):
                    # Stop event was set, exit loop
                    break
                    
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}", exc_info=True)
                # Continue running even if cleanup fails
                time.sleep(60)  # Wait 1 minute before retrying
        
        logger.info("Session cleanup loop exited")
    
    def _cleanup_expired_sessions(self) -> None:
        """
        Remove expired sessions from the database.
        
        Sessions are deleted if:
        1. expires_at < current time (JWT expired)
        2. last_seen < current time - 90 seconds (missed heartbeats)
        
        Requirements: 3.4, 3.6
        """
        try:
            with db_pool.get_cursor(commit=True) as cursor:
                deleted_count = Session.delete_expired(cursor)
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired session(s)")
                else:
                    logger.debug("No expired sessions to clean up")
                    
        except Exception as e:
            logger.error(f"Failed to clean up expired sessions: {e}", exc_info=True)
            raise


# Global cleanup task instance
_cleanup_task: Optional[SessionCleanupTask] = None


def start_cleanup_task(interval: int = 300) -> SessionCleanupTask:
    """
    Start the global session cleanup task.
    
    Args:
        interval: Cleanup interval in seconds (default: 300 = 5 minutes)
    
    Returns:
        The started cleanup task instance
    """
    global _cleanup_task
    
    if _cleanup_task is not None and _cleanup_task.running:
        logger.warning("Session cleanup task is already running")
        return _cleanup_task
    
    _cleanup_task = SessionCleanupTask(interval=interval)
    _cleanup_task.start()
    return _cleanup_task


def stop_cleanup_task() -> None:
    """
    Stop the global session cleanup task.
    """
    global _cleanup_task
    
    if _cleanup_task is not None:
        _cleanup_task.stop()
        _cleanup_task = None


def get_cleanup_task() -> Optional[SessionCleanupTask]:
    """
    Get the global cleanup task instance.
    
    Returns:
        The cleanup task instance, or None if not started
    """
    return _cleanup_task
