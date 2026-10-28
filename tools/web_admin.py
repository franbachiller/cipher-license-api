#!/usr/bin/env python3
"""
Web Admin Panel for VPS-Based Streaming License System

This module provides a Flask-based web interface for managing licenses and sessions.
Includes authentication, dashboard, license management, and session monitoring.

Requirements: 10.1, 10.5, 10.6
"""

import os
import sys
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from api_server.database import db_pool
from api_server.models import License, Session as DBSession
from api_server.utils.key_generator import generate_license_key
from api_server.config import Config

# Initialize Flask app with correct template folder
template_folder = os.path.join(parent_dir, 'templates')
app = Flask(__name__, template_folder=template_folder)
# Strong random secret — regenerates each run; sessions invalidated on restart (intended)
app.secret_key = os.environ.get('ADMIN_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

# ── LOCALHOST-ONLY MIDDLEWARE ──────────────────────────────────────────────────
ALLOWED_HOSTS = {'127.0.0.1', '::1', 'localhost'}

@app.before_request
def restrict_to_localhost():
    remote = request.remote_addr
    if remote not in ALLOWED_HOSTS:
        return jsonify({'error': 'Forbidden'}), 403

# ── LOGIN BRUTE-FORCE PROTECTION ──────────────────────────────────────────────
_fail_counts  = defaultdict(int)    # ip -> fail count
_lockout_until = defaultdict(float) # ip -> unlock timestamp
MAX_ATTEMPTS  = 5
LOCKOUT_SECS  = 300  # 5 minutes

def check_brute_force():
    ip = request.remote_addr
    if time.time() < _lockout_until[ip]:
        remaining = int(_lockout_until[ip] - time.time())
        return f'Too many failed attempts. Try again in {remaining}s.'
    return None

def record_fail():
    ip = request.remote_addr
    _fail_counts[ip] += 1
    if _fail_counts[ip] >= MAX_ATTEMPTS:
        _lockout_until[ip] = time.time() + LOCKOUT_SECS
        _fail_counts[ip] = 0

def record_success():
    ip = request.remote_addr
    _fail_counts[ip] = 0
    _lockout_until[ip] = 0


@app.context_processor
def inject_globals():
    return {'now_utc': datetime.utcnow()}


# Admin credentials (in production, use proper authentication)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    if request.method == 'POST':
        locked = check_brute_force()
        if locked:
            flash(locked, 'danger')
            return render_template('login.html')

        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            record_success()
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            record_fail()
            ip = request.remote_addr
            remaining = MAX_ATTEMPTS - _fail_counts[ip]
            if remaining > 0:
                flash(f'Invalid credentials. {remaining} attempt(s) left.', 'danger')
            else:
                flash(f'Account locked for {LOCKOUT_SECS // 60} minutes.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    """
    Dashboard showing license and session statistics.
    
    Requirements: 10.1, 10.5
    """
    try:
        with db_pool.get_cursor() as cursor:
            # Get license statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired,
                    SUM(CASE WHEN status = 'revoked' THEN 1 ELSE 0 END) as revoked
                FROM licenses
            """)
            license_stats = cursor.fetchone()
            
            # Get session statistics
            cursor.execute("""
                SELECT COUNT(*) as active_sessions
                FROM sessions
                WHERE expires_at > CURRENT_TIMESTAMP
            """)
            session_stats = cursor.fetchone()
            
            # Get recent licenses (last 10)
            cursor.execute("""
                SELECT * FROM licenses
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_licenses = [License(row) for row in cursor.fetchall()]
            
            # Get active sessions count for each recent license
            for lic in recent_licenses:
                lic.active_sessions = DBSession.count_active(cursor, lic.key)
        
        stats = {
            'total_licenses': license_stats['total'] or 0,
            'active_licenses': license_stats['active'] or 0,
            'expired_licenses': license_stats['expired'] or 0,
            'revoked_licenses': license_stats['revoked'] or 0,
            'active_sessions': session_stats['active_sessions'] or 0
        }
        
        return render_template('dashboard.html', stats=stats, recent_licenses=recent_licenses)
        
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('dashboard.html', stats={}, recent_licenses=[])


@app.route('/licenses')
@login_required
def licenses():
    try:
        status_filter = request.args.get('status', None)
        search        = request.args.get('q', '').strip()
        page          = int(request.args.get('page', 1))
        per_page      = 50
        offset        = (page - 1) * per_page

        with db_pool.get_cursor() as cursor:
            params_list  = []
            params_count = []
            where_parts  = []

            if status_filter:
                where_parts.append("status = %s")
                params_list.append(status_filter)
                params_count.append(status_filter)

            if search:
                where_parts.append("(key ILIKE %s OR note ILIKE %s)")
                like = f'%{search}%'
                params_list += [like, like]
                params_count += [like, like]

            where_clause = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

            cursor.execute(
                f"SELECT * FROM licenses {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params_list + [per_page, offset]
            )
            license_list = [License(row) for row in cursor.fetchall()]

            cursor.execute(f"SELECT COUNT(*) as count FROM licenses {where_clause}", params_count)
            total_count = cursor.fetchone()['count']

            for lic in license_list:
                lic.active_sessions = DBSession.count_active(cursor, lic.key)

        total_pages = (total_count + per_page - 1) // per_page

        return render_template('licenses.html',
                               licenses=license_list,
                               status_filter=status_filter,
                               search=search,
                               page=page,
                               total_pages=total_pages,
                               total_count=total_count)
    except Exception as e:
        flash(f'Error loading licenses: {str(e)}', 'danger')
        return render_template('licenses.html', licenses=[], page=1,
                               total_pages=1, total_count=0,
                               status_filter=None, search='')



@app.route('/licenses/create', methods=['GET', 'POST'])
@login_required
def create_license():
    """
    Create new license form and handler.
    
    Requirements: 10.6
    """
    if request.method == 'POST':
        try:
            data         = request.get_json() or {}
            expires_days = int(data.get('expires_days', request.form.get('expires_days', 30)))
            max_sessions = int(data.get('max_sessions', request.form.get('max_sessions', 1)))
            note         = (data.get('note') or request.form.get('note', '')).strip()
            expires_at   = datetime.utcnow() + timedelta(days=expires_days)
            license_key  = generate_license_key()

            with db_pool.get_cursor(commit=True) as cursor:
                lic = License.create(cursor=cursor, key=license_key,
                                     expires_at=expires_at,
                                     max_sessions=max_sessions, note=note)

            return jsonify({
                'ok': True,
                'key': lic.key,
                'status': lic.status,
                'expires_at': lic.expires_at.strftime('%Y-%m-%d') if lic.expires_at else None,
                'max_sessions': lic.max_sessions,
                'note': lic.note or '',
                'created_at': lic.created_at.strftime('%Y-%m-%d') if lic.created_at else None,
            })
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    return render_template('create_license.html')


@app.route('/licenses/<license_key>/revoke', methods=['POST'])
@login_required
def revoke_license(license_key):
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                return jsonify({'ok': False, 'error': 'License not found'}), 404
            License.update_status(cursor, license_key, 'revoked')
            sessions_terminated = DBSession.delete_by_license_key(cursor, license_key)
        return jsonify({'ok': True, 'sessions_terminated': sessions_terminated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/licenses/<license_key>/delete', methods=['POST'])
@login_required
def delete_license(license_key):
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                return jsonify({'ok': False, 'error': 'License not found'}), 404
            License.delete(cursor, license_key)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/licenses/<license_key>/extend', methods=['POST'])
@login_required
def extend_license(license_key):
    try:
        data         = request.get_json() or {}
        extend_days  = int(data.get('extend_days', request.form.get('extend_days', 30)))
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                return jsonify({'ok': False, 'error': 'License not found'}), 404
            new_expires = lic.expires_at + timedelta(days=extend_days)
            License.update_expires_at(cursor, license_key, new_expires)
        return jsonify({'ok': True, 'expires_at': new_expires.strftime('%Y-%m-%d'), 'extend_days': extend_days})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500




@app.route('/sessions')
@login_required
def sessions():
    """
    Session viewer with real-time updates.
    
    Requirements: 10.5
    """
    try:
        # Get filter parameter
        license_key_filter = request.args.get('license_key', None)
        
        with db_pool.get_cursor() as cursor:
            if license_key_filter:
                # Get sessions for specific license
                session_list = DBSession.get_by_license_key(cursor, license_key_filter)
            else:
                # Get all active sessions
                cursor.execute("""
                    SELECT * FROM sessions
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY last_seen DESC
                """)
                session_list = [DBSession(row) for row in cursor.fetchall()]
        
        return render_template('sessions.html', 
                             sessions=session_list,
                             license_key_filter=license_key_filter)
        
    except Exception as e:
        flash(f'Error loading sessions: {str(e)}', 'danger')
        return render_template('sessions.html', sessions=[], license_key_filter=None)


@app.route('/api/sessions/live')
@login_required
def sessions_live():
    """API endpoint for real-time session updates."""
    try:
        with db_pool.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM sessions
                WHERE expires_at > CURRENT_TIMESTAMP
                ORDER BY last_seen DESC
            """)
            session_list = [DBSession(row) for row in cursor.fetchall()]
        sessions_data = [s.to_dict() for s in session_list]
        return jsonify({
            'sessions': sessions_data,
            'count': len(sessions_data),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/licenses/<license_key>/reset-hwid', methods=['POST'])
@login_required
def reset_hwid(license_key):
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                flash('License not found.', 'danger')
                return redirect(url_for('licenses'))
            if not lic.hwid:
                flash('No HWID bound to this license.', 'warning')
                return redirect(url_for('licenses'))
            License.reset_hwid(cursor, license_key)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/licenses/<license_key>/reactivate', methods=['POST'])
@login_required
def reactivate_license(license_key):
    try:
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                flash('License not found.', 'danger')
                return redirect(url_for('licenses'))
            if lic.status == 'active':
                flash('License is already active.', 'warning')
                return redirect(url_for('licenses'))
            License.update_status(cursor, license_key, 'active')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/licenses/<license_key>/note', methods=['POST'])
@login_required
def update_note(license_key):
    try:
        note = request.form.get('note', '').strip()
        with db_pool.get_cursor(commit=True) as cursor:
            lic = License.find_by_key(cursor, license_key)
            if not lic:
                return jsonify({'error': 'License not found'}), 404
            License.update_note(cursor, license_key, note)
        return jsonify({'ok': True, 'note': note})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/licenses/bulk-create', methods=['GET', 'POST'])
@login_required
def bulk_create():
    if request.method == 'POST':
        try:
            data         = request.get_json() or {}
            count        = max(1, min(100, int(data.get('count', request.form.get('count', 1)))))
            expires_days = int(data.get('expires_days', request.form.get('expires_days', 30)))
            max_sessions = max(1, int(data.get('max_sessions', request.form.get('max_sessions', 1))))
            note         = (data.get('note') or request.form.get('note', '')).strip()
            expires_at   = datetime.utcnow() + timedelta(days=expires_days)
            keys = []
            with db_pool.get_cursor(commit=True) as cursor:
                for _ in range(count):
                    key = generate_license_key()
                    License.create(cursor=cursor, key=key,
                                   expires_at=expires_at,
                                   max_sessions=max_sessions, note=note)
                    keys.append(key)
            return jsonify({'ok': True, 'keys': keys, 'count': len(keys),
                            'expires_days': expires_days, 'max_sessions': max_sessions, 'note': note})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': False, 'error': 'Method not allowed'}), 405


@app.route('/licenses/export')
@login_required
def export_licenses():
    import csv, io
    from flask import Response
    try:
        status_filter = request.args.get('status', None)
        with db_pool.get_cursor() as cursor:
            if status_filter:
                cursor.execute(
                    "SELECT * FROM licenses WHERE status = %s ORDER BY created_at DESC",
                    (status_filter,))
            else:
                cursor.execute("SELECT * FROM licenses ORDER BY created_at DESC")
            rows = cursor.fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['key', 'status', 'expires_at', 'max_sessions',
                         'hwid_bound', 'created_at', 'note'])
        for row in rows:
            writer.writerow([
                row['key'], row['status'],
                row['expires_at'].strftime('%Y-%m-%d %H:%M') if row['expires_at'] else '',
                row['max_sessions'],
                'Yes' if row.get('hwid') else 'No',
                row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
                row.get('note', '') or ''
            ])
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition':
                     f'attachment; filename=cipher_licenses_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'}
        )
    except Exception as e:
        flash(f'Export error: {str(e)}', 'danger')
        return redirect(url_for('licenses'))




def init_app():
    """Initialize the application."""
    # Initialize database connection pool
    try:
        db_pool.initialize()
        print("✓ Database connection initialized")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if not ADMIN_PASSWORD:
        print("✗ ADMIN_PASSWORD no está definido; el panel no arranca sin credenciales.")
        sys.exit(1)
    init_app()
    # Default to localhost only — never expose admin panel to network
    host  = os.environ.get('ADMIN_HOST', '127.0.0.1')
    port  = int(os.environ.get('ADMIN_PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'

    print(f"\n{'='*50}")
    print(f"  Cipher Admin Panel")
    print(f"  URL: http://127.0.0.1:{port}")
    print(f"  Localhost-only: YES")
    print(f"  Brute-force protection: {MAX_ATTEMPTS} attempts / {LOCKOUT_SECS}s lockout")
    print(f"{'='*50}\n")

    app.run(host=host, port=port, debug=debug)
