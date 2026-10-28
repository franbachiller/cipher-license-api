"""
VPS-based streaming license system API server.

This package provides a Flask-based REST API for managing license keys,
authenticating users, streaming encrypted binaries, and tracking sessions.
"""

__version__ = '2.0.0'

from .app import create_app, app

__all__ = ['create_app', 'app']
