"""
Cipher License API — Server v2
Flask + SQLite + Rate limiting

Endpoints:
    POST /api/validate           — Loader validation (HWID + key)
    POST /api/admin/create       — Create license
    POST /api/admin/revoke       — Change license status
    POST /api/admin/extend       — Extend expiry
    POST /api/admin/delete       — Delete license
    GET  /api/admin/list         — List all licenses
"""

import os, sqlite3, hashlib, hmac, time
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cipher.db")
ADMIN_TOKEN = os.environ.get("CIPHER_ADMIN_TOKEN", "")

HMAC_SECRET = bytes([
    0x7A, 0x3F, 0xB8, 0x52, 0xE1, 0x6D, 0x94, 0x0C,
    0xA5, 0x28, 0xF3, 0x71, 0xDE, 0x89, 0x46, 0xBB,
    0x1C, 0xE7, 0x5A, 0x03, 0x9F, 0x64, 0xD2, 0x48,
    0x8E, 0x37, 0xC6, 0x15, 0xAB, 0x70, 0xF9, 0x53
])

# ── Rate limiting (in-memory) ────────────────────────────────
_rate_data = defaultdict(list)  # ip -> [timestamps]
RATE_LIMIT  = 10   # max requests
RATE_WINDOW = 60   # per seconds

def rate_limit_check(ip):
    now = time.time()
    window = _rate_data[ip]
    # Drop old entries
    _rate_data[ip] = [t for t in window if now - t < RATE_WINDOW]
    if len(_rate_data[ip]) >= RATE_LIMIT:
        return False
    _rate_data[ip].append(now)
    return True

# ── Database ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hwid        TEXT UNIQUE NOT NULL,
            license_key TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            plan        TEXT NOT NULL DEFAULT 'lifetime',
            expires_at  TEXT,
            created_at  TEXT NOT NULL,
            last_seen   TEXT,
            note        TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Auth ─────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not ADMIN_TOKEN or token != ADMIN_TOKEN:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Key gen ──────────────────────────────────────────────────
def generate_key(hwid: str) -> str:
    hwid = hwid.strip().upper()
    sig = hmac.new(HMAC_SECRET, hwid.encode(), hashlib.sha256).hexdigest().upper()
    s = sig[:25]
    return f"{s[0:5]}-{s[5:10]}-{s[10:15]}-{s[15:20]}-{s[20:25]}"

# ── Validate ─────────────────────────────────────────────────
@app.route("/api/validate", methods=["POST"])
def validate():
    ip = request.remote_addr
    if not rate_limit_check(ip):
        return jsonify({"status": "error", "message": "Rate limited"}), 429

    data = request.get_json(silent=True) or {}
    hwid = (data.get("hwid") or "").strip().upper()
    key  = (data.get("key")  or "").strip().upper()

    if not hwid or not key:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE hwid = ?", (hwid,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "invalid", "message": "No license for this HWID"})

    if row["license_key"].upper() != key:
        conn.close()
        return jsonify({"status": "invalid", "message": "Invalid key"})

    if row["status"] in ("suspended", "banned", "revoked"):
        conn.close()
        return jsonify({"status": row["status"], "message": f"License {row['status']}"})

    if row["expires_at"]:
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
            conn.close()
            return jsonify({"status": "expired", "message": "License expired"})

    conn.execute("UPDATE licenses SET last_seen = ? WHERE hwid = ?",
                 (datetime.utcnow().isoformat(), hwid))
    conn.commit()
    conn.close()
    return jsonify({"status": "valid", "plan": row["plan"]})

# ── Admin: Create ─────────────────────────────────────────────
@app.route("/api/admin/create", methods=["POST"])
@admin_required
def admin_create():
    data = request.get_json(silent=True) or {}
    hwid = (data.get("hwid") or "").strip().upper()
    plan = data.get("plan", "lifetime")
    note = data.get("note", "")
    if not hwid:
        return jsonify({"error": "Missing hwid"}), 400

    key = generate_key(hwid)
    now = datetime.utcnow().isoformat()
    plan_days = {"1d":1,"7d":7,"30d":30,"90d":90}
    expires_at = (datetime.utcnow() + timedelta(days=plan_days[plan])).isoformat() if plan in plan_days else None

    conn = get_db()
    try:
        conn.execute("INSERT INTO licenses (hwid,license_key,status,plan,expires_at,created_at,note) VALUES(?,?,'active',?,?,?,?)",
                     (hwid, key, plan, expires_at, now, note))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "HWID already exists"}), 409
    conn.close()
    return jsonify({"status": "created", "hwid": hwid, "key": key, "plan": plan, "expires_at": expires_at})

# ── Admin: Revoke/Status ──────────────────────────────────────
@app.route("/api/admin/revoke", methods=["POST"])
@admin_required
def admin_revoke():
    data   = request.get_json(silent=True) or {}
    hwid   = (data.get("hwid") or "").strip().upper()
    action = data.get("action", "revoked")
    if action not in ("revoked","suspended","banned","active"):
        return jsonify({"error": "Invalid action"}), 400
    conn = get_db()
    cur = conn.execute("UPDATE licenses SET status=? WHERE hwid=?", (action, hwid))
    conn.commit(); conn.close()
    return (jsonify({"status":"ok","hwid":hwid,"new_status":action}) if cur.rowcount
            else (jsonify({"error":"Not found"}), 404))

# ── Admin: Extend ─────────────────────────────────────────────
@app.route("/api/admin/extend", methods=["POST"])
@admin_required
def admin_extend():
    data = request.get_json(silent=True) or {}
    hwid = (data.get("hwid") or "").strip().upper()
    days = data.get("days", 30)
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE hwid=?", (hwid,)).fetchone()
    if not row: conn.close(); return jsonify({"error":"Not found"}), 404
    base = datetime.utcnow()
    if row["expires_at"]:
        exp = datetime.fromisoformat(row["expires_at"])
        if exp > base: base = exp
    new_exp = (base + timedelta(days=days)).isoformat()
    conn.execute("UPDATE licenses SET expires_at=?,status='active' WHERE hwid=?", (new_exp, hwid))
    conn.commit(); conn.close()
    return jsonify({"status":"ok","hwid":hwid,"new_expires_at":new_exp})

# ── Admin: Delete ─────────────────────────────────────────────
@app.route("/api/admin/delete", methods=["POST"])
@admin_required
def admin_delete():
    data = request.get_json(silent=True) or {}
    hwid = (data.get("hwid") or "").strip().upper()
    conn = get_db()
    cur = conn.execute("DELETE FROM licenses WHERE hwid=?", (hwid,))
    conn.commit(); conn.close()
    return (jsonify({"status":"deleted","hwid":hwid}) if cur.rowcount
            else (jsonify({"error":"Not found"}), 404))

# ── Admin: List ───────────────────────────────────────────────
@app.route("/api/admin/list", methods=["GET"])
@admin_required
def admin_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    # rename license_key -> key for consistency
    for r in result:
        r["key"] = r.pop("license_key", "")
    return jsonify({"licenses": result, "total": len(result)})

if __name__ == "__main__":
    print("[LEGACY WARNING] tools/server.py is deprecated.")
    print("Use api_server/app.py for the production license API.")
    if not ADMIN_TOKEN:
        print("Set CIPHER_ADMIN_TOKEN to use legacy admin endpoints.")
    app.run(host="0.0.0.0", port=5000, debug=False)
