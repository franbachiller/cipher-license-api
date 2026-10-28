"""
Cipher Admin Panel — Interactive License Manager
Run: python panel.py
"""

import os, json, time, urllib.request, urllib.error
from datetime import datetime

print("[LEGACY WARNING] tools/panel.py is deprecated.")
print("Use tools/web_admin.py (localhost web panel) for the current stack.")

# ── Load config ──────────────────────────────────────────────
_conf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cipher_admin.conf")
_conf = {}
if os.path.exists(_conf_path):
    with open(_conf_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                _conf[k.strip()] = v.strip()
else:
    print(f"  ✘ cipher_admin.conf not found at {_conf_path}")
    exit(1)

SERVER_URL  = _conf.get("SERVER_URL",  "http://<IP_DEL_VPS>:5000")
ADMIN_TOKEN = _conf.get("ADMIN_TOKEN", "")

# ── ANSI colors ──────────────────────────────────────────────
R  = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
B  = "\033[94m"; M  = "\033[95m"; C  = "\033[96m"
W  = "\033[97m"; DIM= "\033[90m"; RST= "\033[0m"; BLD="\033[1m"

def clr(): os.system("cls")

def api(method, endpoint, data=None):
    url = f"{SERVER_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except Exception as ex:
        return {"error": str(ex)}, 0

def inp(prompt):
    return input(f"  {C}›{RST} {prompt}").strip()

def ok(msg):  print(f"  {G}✔{RST}  {msg}")
def err(msg): print(f"  {R}✘{RST}  {msg}")
def info(msg):print(f"  {B}·{RST}  {msg}")

def pause(): input(f"\n  {DIM}Press Enter to continue...{RST}")

# ── Banner ────────────────────────────────────────────────────
def banner():
    clr()
    print(f"""
{B}{BLD}  ╔══════════════════════════════════════════╗
  ║        CIPHER  LICENSE  MANAGER          ║
  ╚══════════════════════════════════════════╝{RST}
  {DIM}Server: {SERVER_URL}{RST}
""")

# ── Status bar ────────────────────────────────────────────────
def server_status():
    r, code = api("GET", "/api/admin/list")
    if code == 200:
        total = r.get("total", 0)
        active = sum(1 for l in r.get("licenses", []) if l["status"] == "active")
        print(f"  {DIM}Licenses: {W}{total}{DIM} total  ·  {G}{active}{DIM} active{RST}")
    else:
        print(f"  {R}⚠  Cannot reach server{RST}")
    print()

# ── All licenses table ─────────────────────────────────────────
def show_list(licenses):
    if not licenses:
        info("No licenses yet.")
        return
    status_color = {"active": G, "suspended": Y, "banned": R, "revoked": R, "expired": DIM}
    print(f"  {DIM}{'HWID':<18} {'STATUS':<11} {'PLAN':<10} {'EXPIRES':<12} {'LAST SEEN':<12} NOTE{RST}")
    print(f"  {DIM}{'─'*80}{RST}")
    for l in licenses:
        sc   = status_color.get(l["status"], W)
        exp  = l["expires_at"][:10] if l["expires_at"] else "lifetime"
        seen = l["last_seen"][:10] if l["last_seen"] else "never"
        # Check if expired
        if l["expires_at"]:
            try:
                if datetime.fromisoformat(l["expires_at"]) < datetime.utcnow():
                    sc = DIM
            except: pass
        note = l.get("note","")[:20]
        print(f"  {W}{l['hwid']:<18}{RST} {sc}{l['status']:<11}{RST} {C}{l['plan']:<10}{RST} {exp:<12} {seen:<12} {DIM}{note}{RST}")
    print(f"\n  {DIM}Total: {len(licenses)}{RST}")

# ── Actions ───────────────────────────────────────────────────
def action_create():
    banner()
    print(f"  {BLD}{W}── Create New License ──{RST}\n")
    hwid = inp("Client HWID: ").upper()
    if not hwid:
        err("HWID required."); pause(); return
    print(f"  {DIM}Plans: 1d · 7d · 30d · 90d · lifetime{RST}")
    plan = inp("Plan [30d]: ") or "30d"
    note = inp("Note (client name/Discord): ")

    r, code = api("POST", "/api/admin/create", {"hwid": hwid, "plan": plan, "note": note})
    print()
    if code == 200:
        ok(f"License created!")
        print(f"\n  {BLD}HWID:  {W}{r['hwid']}{RST}")
        print(f"  {BLD}Key:   {G}{r['key']}{RST}")
        print(f"  {BLD}Plan:  {C}{r['plan']}{RST}  ·  Expires: {r.get('expires_at','never')}")
        print(f"\n  {Y}→ Send this key to the client.{RST}")
    else:
        err(r.get("error", str(r)))
    pause()

def action_list():
    banner()
    print(f"  {BLD}{W}── All Licenses ──{RST}\n")
    r, code = api("GET", "/api/admin/list")
    if code == 200:
        show_list(r.get("licenses", []))
    else:
        err(f"Failed: {r}")
    pause()

def action_lookup():
    banner()
    print(f"  {BLD}{W}── Lookup HWID ──{RST}\n")
    hwid = inp("HWID: ").upper()
    r, code = api("GET", "/api/admin/list")
    if code != 200:
        err("Server error"); pause(); return
    found = [l for l in r.get("licenses",[]) if l["hwid"] == hwid]
    if not found:
        err(f"HWID {hwid} not found.")
    else:
        l = found[0]
        print(f"\n  HWID:      {W}{l['hwid']}{RST}")
        print(f"  Key:       {G}{l['license_key']}{RST}")
        print(f"  Status:    {l['status']}")
        print(f"  Plan:      {l['plan']}")
        print(f"  Expires:   {l.get('expires_at') or 'lifetime'}")
        print(f"  Created:   {l['created_at'][:10]}")
        print(f"  Last Seen: {l.get('last_seen') or 'never'}")
        print(f"  Note:      {l.get('note','')}")
    pause()

def action_status_change(new_status, label):
    banner()
    print(f"  {BLD}{W}── {label} License ──{RST}\n")
    hwid = inp("HWID: ").upper()
    r, code = api("POST", "/api/admin/revoke", {"hwid": hwid, "action": new_status})
    print()
    if r.get("status") == "ok":
        ok(f"{hwid} → {new_status}")
    else:
        err(r.get("error", str(r)))
    pause()

def action_extend():
    banner()
    print(f"  {BLD}{W}── Extend License ──{RST}\n")
    hwid = inp("HWID: ").upper()
    days = inp("Days to add [30]: ") or "30"
    r, code = api("POST", "/api/admin/extend", {"hwid": hwid, "days": int(days)})
    print()
    if r.get("status") == "ok":
        ok(f"Extended until {r['new_expires_at'][:10]}")
    else:
        err(r.get("error", str(r)))
    pause()

def action_delete():
    banner()
    print(f"  {BLD}{W}── Delete License ──{RST}\n")
    hwid = inp("HWID: ").upper()
    confirm = inp(f"Type '{hwid[:4]}' to confirm: ")
    if confirm.upper() != hwid[:4]:
        err("Cancelled."); pause(); return
    r, code = api("POST", "/api/admin/delete", {"hwid": hwid})
    print()
    if r.get("status") == "deleted":
        ok(f"Deleted {hwid}")
    else:
        err(r.get("error", str(r)))
    pause()

# ── Main menu ─────────────────────────────────────────────────
MENU = [
    ("Create license",          action_create),
    ("List all licenses",       action_list),
    ("Lookup HWID",             action_lookup),
    ("Suspend license",         lambda: action_status_change("suspended", "Suspend")),
    ("Reactivate license",      lambda: action_status_change("active",    "Reactivate")),
    ("Ban license",             lambda: action_status_change("banned",    "Ban")),
    ("Extend license",          action_extend),
    ("Delete license",          action_delete),
    ("Exit",                    None),
]

def main():
    # Enable ANSI on Windows
    os.system("")
    while True:
        banner()
        server_status()
        print(f"  {BLD}{W}Actions:{RST}")
        for i, (label, _) in enumerate(MENU, 1):
            color = R if label == "Exit" else (Y if "Ban" in label or "Delete" in label or "Suspend" in label else W)
            print(f"  {DIM}[{RST}{B}{i}{RST}{DIM}]{RST} {color}{label}{RST}")
        print()
        choice = inp("Select: ")
        if not choice.isdigit():
            continue
        idx = int(choice) - 1
        if idx < 0 or idx >= len(MENU):
            continue
        label, fn = MENU[idx]
        if fn is None:
            print(f"\n  {DIM}Bye.{RST}\n")
            break
        fn()

if __name__ == "__main__":
    main()
