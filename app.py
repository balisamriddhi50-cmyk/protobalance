import streamlit as st
from datetime import date, datetime
import pandas as pd
import io
import sqlite3
import json
import hashlib
import base64
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go

# ── DATABASE ──────────────────────────────────────────
def get_db():
    return sqlite3.connect("protobalance.db")

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT,
        role TEXT DEFAULT 'manager',
        theme TEXT DEFAULT 'purple',
        org_name TEXT DEFAULT 'My Organisation',
        logo BLOB)""")

    c.execute("""CREATE TABLE IF NOT EXISTS writers (
        name TEXT PRIMARY KEY,
        specialties TEXT,
        available INTEGER DEFAULT 1)""")

    c.execute("""CREATE TABLE IF NOT EXISTS protocols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, specialty TEXT, priority TEXT,
        deadline TEXT, assigned_to TEXT,
        status TEXT DEFAULT 'Not Started',
        added_on TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, action TEXT, username TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS feedback (
        protocol_name TEXT PRIMARY KEY,
        writer TEXT, rating INTEGER,
        comment TEXT, feedback_date TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS specialties (
        name TEXT PRIMARY KEY)""")

    c.execute("""CREATE TABLE IF NOT EXISTS gcp_certifications (
        writer_name TEXT PRIMARY KEY,
        certification_date TEXT,
        expiry_date TEXT,
        certification_body TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS sops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sop_number TEXT, sop_title TEXT,
        version TEXT, effective_date TEXT,
        department TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS sop_acknowledgements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        writer_name TEXT, sop_id INTEGER,
        acknowledged_date TEXT,
        UNIQUE(writer_name, sop_id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS protocol_timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        protocol_id INTEGER, protocol_name TEXT,
        writer_name TEXT, assigned_date TEXT,
        completed_date TEXT, turnaround_days INTEGER)""")

    default_specialties = [
        "Oncology", "Cardiology", "Neurology",
        "Diabetes", "Nephrology", "Pulmonology",
        "Gastroenterology", "Infectious Diseases",
        "Rheumatology", "Dermatology", "Psychiatry",
        "Ophthalmology", "Orthopedics", "Hematology",
        "Pharmacovigilance", "Regulatory Affairs",
        "Bioequivalence", "Pediatrics", "Geriatrics"
    ]
    for s in default_specialties:
        c.execute(
            "INSERT OR IGNORE INTO specialties VALUES (?)", (s,)
        )

    default_sops = [
        ("SOP-001", "Protocol Writing Guidelines",
         "v2.0", "2024-01-01", "Clinical Operations"),
        ("SOP-002", "ICH-GCP Compliance Requirements",
         "v3.1", "2024-01-01", "Quality Assurance"),
        ("SOP-003", "Adverse Event Reporting",
         "v1.5", "2024-03-01", "Pharmacovigilance"),
        ("SOP-004", "Source Data Verification",
         "v2.2", "2024-02-01", "Clinical Operations"),
        ("SOP-005", "Informed Consent Process",
         "v1.8", "2024-01-15", "Regulatory Affairs"),
        ("SOP-006", "Protocol Deviation Reporting",
         "v1.3", "2024-02-15", "Quality Assurance"),
    ]
    for sop in default_sops:
        c.execute(
            "INSERT OR IGNORE INTO sops "
            "(sop_number, sop_title, version, "
            "effective_date, department) VALUES (?,?,?,?,?)",
            sop
        )

    default_pw = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute(
        "INSERT OR IGNORE INTO users "
        "(username, password, role) VALUES (?,?,?)",
        ("admin", default_pw, "admin")
    )
    conn.commit()
    conn.close()

init_db()

# ── HELPERS ───────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_login(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT password, role FROM users WHERE username=?",
        (username,)
    )
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_pw(password):
        return row[1]
    return None

def get_user_settings(username):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT theme, org_name, logo FROM users "
        "WHERE username=?", (username,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "theme": row[0],
            "org_name": row[1],
            "logo": row[2]
        }
    return {"theme": "purple",
            "org_name": "My Organisation", "logo": None}

def save_user_settings(username, theme, org_name, logo=None):
    conn = get_db()
    c = conn.cursor()
    if logo:
        c.execute(
            "UPDATE users SET theme=?, org_name=?, logo=? "
            "WHERE username=?",
            (theme, org_name, logo, username)
        )
    else:
        c.execute(
            "UPDATE users SET theme=?, org_name=? "
            "WHERE username=?",
            (theme, org_name, username)
        )
    conn.commit()
    conn.close()

def create_user(username, password, role):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password, role) "
            "VALUES (?,?,?)",
            (username, hash_pw(password), role)
        )
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT username, role FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_specialties():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM specialties ORDER BY name")
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result

def add_specialty(name):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO specialties VALUES (?)", (name,)
    )
    conn.commit()
    conn.close()

def get_writers():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT name, specialties, available FROM writers"
    )
    rows = c.fetchall()
    conn.close()
    return {r[0]: {
        "specialties": json.loads(r[1]),
        "available": bool(r[2])
    } for r in rows}

def add_writer(name, specialties, available):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO writers VALUES (?,?,?)",
        (name, json.dumps(specialties), int(available))
    )
    conn.commit()
    conn.close()

def update_writer_availability(name, available):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE writers SET available=? WHERE name=?",
        (int(available), name)
    )
    conn.commit()
    conn.close()

def get_protocols():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, specialty, priority, deadline, "
        "assigned_to, status, added_on FROM protocols"
    )
    rows = c.fetchall()
    conn.close()
    return [{
        "id": r[0], "name": r[1], "specialty": r[2],
        "priority": r[3], "deadline": r[4],
        "assigned_to": r[5], "status": r[6], "added_on": r[7]
    } for r in rows]

def add_protocol(name, specialty, priority,
                 deadline, assigned_to):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO protocols (name, specialty, priority, "
        "deadline, assigned_to, status, added_on) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, specialty, priority, deadline,
         assigned_to, "Not Started", str(date.today()))
    )
    conn.commit()
    conn.close()

def update_protocol_status(protocol_id, new_status):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE protocols SET status=? WHERE id=?",
        (new_status, protocol_id)
    )
    conn.commit()
    conn.close()

def reassign_protocol(protocol_id, new_writer):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE protocols SET assigned_to=? WHERE id=?",
        (new_writer, protocol_id)
    )
    conn.commit()
    conn.close()

def log_audit(action, username="system"):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO audit_log "
        "(timestamp, action, username) VALUES (?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         action, username)
    )
    conn.commit()
    conn.close()

def get_audit_log():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, username, action "
        "FROM audit_log ORDER BY id DESC"
    )
    rows = c.fetchall()
    conn.close()
    return [{"Time": r[0], "User": r[1], "Action": r[2]}
            for r in rows]

def save_feedback(protocol_name, writer, rating, comment):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO feedback VALUES (?,?,?,?,?)",
        (protocol_name, writer, rating,
         comment, str(date.today()))
    )
    conn.commit()
    conn.close()

def get_feedback():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT protocol_name, writer, rating, "
        "comment, feedback_date FROM feedback"
    )
    rows = c.fetchall()
    conn.close()
    return {r[0]: {
        "writer": r[1], "rating": r[2],
        "comment": r[3], "date": r[4]
    } for r in rows}

def get_gcp_certifications():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT writer_name, certification_date, "
        "expiry_date, certification_body "
        "FROM gcp_certifications"
    )
    rows = c.fetchall()
    conn.close()
    return {r[0]: {
        "certification_date": r[1],
        "expiry_date": r[2],
        "certification_body": r[3]
    } for r in rows}

def save_gcp_certification(writer, cert_date,
                           expiry_date, cert_body):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO gcp_certifications "
        "VALUES (?,?,?,?)",
        (writer, cert_date, expiry_date, cert_body)
    )
    conn.commit()
    conn.close()

def get_sops():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, sop_number, sop_title, version, "
        "effective_date, department FROM sops"
    )
    rows = c.fetchall()
    conn.close()
    return [{
        "id": r[0], "sop_number": r[1],
        "sop_title": r[2], "version": r[3],
        "effective_date": r[4], "department": r[5]
    } for r in rows]

def add_sop(sop_number, sop_title, version,
            effective_date, department):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sops (sop_number, sop_title, "
        "version, effective_date, department) "
        "VALUES (?,?,?,?,?)",
        (sop_number, sop_title, version,
         effective_date, department)
    )
    conn.commit()
    conn.close()

def get_acknowledgements():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT writer_name, sop_id "
        "FROM sop_acknowledgements"
    )
    rows = c.fetchall()
    conn.close()
    result = {}
    for r in rows:
        if r[0] not in result:
            result[r[0]] = []
        result[r[0]].append(r[1])
    return result

def acknowledge_sop(writer, sop_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sop_acknowledgements "
        "(writer_name, sop_id, acknowledged_date) "
        "VALUES (?,?,?)",
        (writer, sop_id, str(date.today()))
    )
    conn.commit()
    conn.close()

def save_turnaround(protocol_id, protocol_name,
                    writer_name, assigned_date):
    conn = get_db()
    c = conn.cursor()
    completed_date = str(date.today())
    try:
        assigned = datetime.strptime(
            assigned_date, "%Y-%m-%d"
        ).date()
        days = (date.today() - assigned).days
    except:
        days = 0
    c.execute(
        "INSERT OR IGNORE INTO protocol_timeline "
        "(protocol_id, protocol_name, writer_name, "
        "assigned_date, completed_date, turnaround_days) "
        "VALUES (?,?,?,?,?,?)",
        (protocol_id, protocol_name, writer_name,
         assigned_date, completed_date, days)
    )
    conn.commit()
    conn.close()

def get_turnaround_analytics():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT writer_name, AVG(turnaround_days), "
        "MIN(turnaround_days), MAX(turnaround_days), "
        "COUNT(*) FROM protocol_timeline "
        "GROUP BY writer_name"
    )
    rows = c.fetchall()
    conn.close()
    return [{
        "Writer": r[0],
        "Avg Days": round(r[1], 1),
        "Fastest (days)": r[2],
        "Slowest (days)": r[3],
        "Total Completed": r[4]
    } for r in rows]

# ── THEME SYSTEM ──────────────────────────────────────
THEMES = {
    "purple": {
        "primary": "#7c3aed",
        "secondary": "#a78bfa",
        "bg": "#0e1117",
        "card": "#1e1e2e",
        "sidebar_bg": "#1a1a2e",
        "text": "#ffffff",
        "tab_active": "#7c3aed",
        "tab_hover": "#6d28d9",
        "name": "Purple Dark"
    },
    "blue": {
        "primary": "#0ea5e9",
        "secondary": "#38bdf8",
        "bg": "#0a192f",
        "card": "#112240",
        "sidebar_bg": "#0a192f",
        "text": "#ccd6f6",
        "tab_active": "#0ea5e9",
        "tab_hover": "#0284c7",
        "name": "Blue Professional"
    },
    "green": {
        "primary": "#10b981",
        "secondary": "#34d399",
        "bg": "#0d1f0d",
        "card": "#1a3a1a",
        "sidebar_bg": "#0d1f0d",
        "text": "#a8d5a2",
        "tab_active": "#10b981",
        "tab_hover": "#059669",
        "name": "Green Medical"
    },
    "light": {
        "primary": "#6366f1",
        "secondary": "#818cf8",
        "bg": "#f8fafc",
        "card": "#ffffff",
        "sidebar_bg": "#f1f5f9",
        "text": "#1e293b",
        "tab_active": "#6366f1",
        "tab_hover": "#4f46e5",
        "name": "Light Clean"
    },
    "dark": {
        "primary": "#f59e0b",
        "secondary": "#fbbf24",
        "bg": "#111827",
        "card": "#1f2937",
        "sidebar_bg": "#111827",
        "text": "#f9fafb",
        "tab_active": "#f59e0b",
        "tab_hover": "#d97706",
        "name": "Dark Gold"
    }
}

def get_theme_css(theme_key):
    t = THEMES.get(theme_key, THEMES["purple"])
    return f"""
    <style>
    /* ── Global ── */
    .stApp {{
        background-color: {t['bg']};
        color: {t['text']};
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background-color: {t['sidebar_bg']} !important;
        border-right: 1px solid {t['primary']}33;
    }}

    /* ── Hide default radio circles ── */
    [data-testid="stSidebar"] .stRadio > div {{
        display: none !important;
    }}

    /* ── Nav tabs ── */
    .nav-tab {{
        display: block;
        width: 100%;
        padding: 12px 16px;
        margin: 4px 0;
        border-radius: 10px;
        border: none;
        background: transparent;
        color: {t['text']};
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        text-align: left;
        transition: all 0.2s;
        border-left: 3px solid transparent;
    }}

    .nav-tab:hover {{
        background: {t['primary']}22;
        border-left: 3px solid {t['secondary']};
        color: {t['secondary']};
    }}

    .nav-tab.active {{
        background: {t['primary']}33;
        border-left: 3px solid {t['primary']};
        color: {t['primary']};
        font-weight: 700;
    }}

    /* ── Cards ── */
    .pb-card {{
        background: {t['card']};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        border: 1px solid {t['primary']}22;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}

    /* ── Header ── */
    .pb-header {{
        background: linear-gradient(
            135deg, {t['card']}, {t['sidebar_bg']}
        );
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        border-left: 5px solid {t['primary']};
        box-shadow: 0 4px 15px {t['primary']}22;
    }}

    .pb-header h1 {{
        color: {t['primary']};
        margin: 0;
        font-size: 28px;
        font-weight: 700;
    }}

    .pb-header p {{
        color: {t['secondary']};
        margin: 4px 0 0 0;
        font-size: 14px;
    }}

    /* ── Metric cards ── */
    [data-testid="stMetric"] {{
        background: {t['card']};
        border-radius: 12px;
        padding: 16px;
        border: 1px solid {t['primary']}22;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}

    [data-testid="stMetricValue"] {{
        color: {t['primary']} !important;
        font-size: 32px !important;
        font-weight: 700 !important;
    }}

    [data-testid="stMetricLabel"] {{
        color: {t['text']} !important;
        font-size: 13px !important;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: {t['primary']};
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
        box-shadow: 0 2px 8px {t['primary']}44;
    }}

    .stButton > button:hover {{
        background: {t['tab_hover']};
        box-shadow: 0 4px 12px {t['primary']}66;
        transform: translateY(-1px);
    }}

    /* ── Expander ── */
    [data-testid="stExpander"] {{
        background: {t['card']};
        border-radius: 10px;
        border: 1px solid {t['primary']}22;
        margin-bottom: 8px;
    }}

    /* ── Input fields ── */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {{
        background: {t['card']};
        border-radius: 8px;
        border: 1px solid {t['primary']}44;
        color: {t['text']};
    }}

    /* ── Tables ── */
    [data-testid="stTable"] {{
        background: {t['card']};
        border-radius: 10px;
    }}

    /* ── Status badges ── */
    .badge-success {{
        background: #10b98122;
        color: #10b981;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #10b98144;
    }}

    .badge-danger {{
        background: #ef444422;
        color: #ef4444;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #ef444444;
    }}

    .badge-warning {{
        background: #f59e0b22;
        color: #f59e0b;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #f59e0b44;
    }}

    .badge-info {{
        background: {t['primary']}22;
        color: {t['primary']};
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid {t['primary']}44;
    }}

    /* ── Divider ── */
    hr {{
        border-color: {t['primary']}22;
    }}

    /* ── Sidebar logo area ── */
    .sidebar-logo {{
        text-align: center;
        padding: 16px 0;
        border-bottom: 1px solid {t['primary']}33;
        margin-bottom: 16px;
    }}

    .sidebar-org-name {{
        color: {t['primary']};
        font-size: 18px;
        font-weight: 700;
        margin: 8px 0 2px 0;
    }}

    .sidebar-caption {{
        color: {t['secondary']};
        font-size: 11px;
    }}

    .sidebar-user {{
        background: {t['primary']}22;
        border-radius: 8px;
        padding: 8px 12px;
        margin: 12px 0;
        font-size: 12px;
        color: {t['secondary']};
        border-left: 3px solid {t['primary']};
    }}

    /* ── Nav section headers ── */
    .nav-section {{
        color: {t['secondary']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 12px 16px 4px 16px;
        margin-top: 8px;
    }}
    </style>
    """

# ── NAV ICONS ─────────────────────────────────────────
NAV_ICONS = {
    "Dashboard": "📊",
    "Writers": "✍️",
    "Protocols": "📋",
    "Progress": "🔄",
    "Feedback": "⭐",
    "Audit Log": "🔍",
    "Export": "📥",
    "Settings": "⚙️",
    "GCP Compliance": "🏅",
    "SOP Management": "📑",
    "Analytics": "📈",
    "Admin Panel": "🔐"
}

NAV_SECTIONS = {
    "MAIN": ["Dashboard"],
    "MANAGEMENT": ["Writers", "Protocols", "Progress"],
    "QUALITY": ["GCP Compliance", "SOP Management", "Feedback"],
    "REPORTS": ["Analytics", "Audit Log", "Export"],
    "SYSTEM": ["Settings", "Admin Panel"]
}

# ── SESSION STATE ─────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

# ══════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.set_page_config(
        page_title="ProtoBalance",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
    <style>
    .stApp { background: linear-gradient(
        135deg, #0e1117, #1a1a2e); }
    .login-card {
        background: #1e1e2e;
        border-radius: 20px;
        padding: 40px;
        border: 1px solid #7c3aed33;
        box-shadow: 0 20px 60px rgba(124,58,237,0.2);
    }
    .login-title {
        text-align: center;
        color: #7c3aed;
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .login-sub {
        text-align: center;
        color: #a78bfa;
        font-size: 15px;
        margin-bottom: 32px;
    }
    .stButton > button {
        background: #7c3aed;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        font-size: 16px;
        padding: 12px;
        width: 100%;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #6d28d9;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(124,58,237,0.4);
    }
    .stTextInput > div > div > input {
        background: #111827;
        border: 1px solid #7c3aed44;
        border-radius: 10px;
        color: white;
        padding: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-card">
            <div class="login-title">ProtoBalance</div>
            <div class="login-sub">
                Clinical Protocol Management System
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        username = st.text_input(
            "Username", placeholder="Enter username"
        )
        password = st.text_input(
            "Password", type="password",
            placeholder="Enter password"
        )
        st.write("")
        if st.button("Login", use_container_width=True):
            role = verify_login(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.session_state.current_page = "Dashboard"
                log_audit("Login", username)
                st.rerun()
            else:
                st.error("Invalid username or password")

        st.write("")
        st.caption(
            "Default: username = **admin** "
            "| password = **admin123**"
        )

# ══════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════
else:
    settings = get_user_settings(st.session_state.username)
    theme_key = settings.get("theme", "purple")
    t = THEMES.get(theme_key, THEMES["purple"])
    org_name = settings.get("org_name", "My Organisation")
    logo_data = settings.get("logo")

    st.set_page_config(
        page_title="ProtoBalance — " + org_name,
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown(
        get_theme_css(theme_key), unsafe_allow_html=True
    )

    # ── SIDEBAR ───────────────────────────────────────
    with st.sidebar:
        # Logo and org name
        if logo_data:
            try:
                logo_bytes = base64.b64decode(logo_data)
                logo_b64 = base64.b64encode(
                    logo_bytes
                ).decode()
                st.markdown(
                    f'<div class="sidebar-logo">'
                    f'<img src="data:image/png;base64,'
                    f'{logo_b64}" style="width:80px;'
                    f'height:80px;border-radius:12px;'
                    f'object-fit:cover;">'
                    f'<div class="sidebar-org-name">'
                    f'{org_name}</div>'
                    f'<div class="sidebar-caption">'
                    f'Protocol Management System</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            except:
                st.markdown(
                    f'<div class="sidebar-logo">'
                    f'<div style="font-size:40px;">🧪</div>'
                    f'<div class="sidebar-org-name">'
                    f'{org_name}</div>'
                    f'<div class="sidebar-caption">'
                    f'Protocol Management System</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                f'<div class="sidebar-logo">'
                f'<div style="font-size:48px;">🧪</div>'
                f'<div class="sidebar-org-name">'
                f'{org_name}</div>'
                f'<div class="sidebar-caption">'
                f'Protocol Management System</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # User info badge
        st.markdown(
            f'<div class="sidebar-user">'
            f'👤 {st.session_state.username} '
            f'<span style="opacity:0.6;">('
            f'{st.session_state.role})</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Navigation
        pages_by_role = list(NAV_SECTIONS["MAIN"]) + \
            list(NAV_SECTIONS["MANAGEMENT"]) + \
            list(NAV_SECTIONS["QUALITY"]) + \
            list(NAV_SECTIONS["REPORTS"]) + \
            ["Settings"]

        if st.session_state.role == "admin":
            pages_by_role.append("Admin Panel")

        for section, section_pages in NAV_SECTIONS.items():
            visible = [
                p for p in section_pages
                if p in pages_by_role
            ]
            if not visible:
                continue

            st.markdown(
                f'<div class="nav-section">{section}</div>',
                unsafe_allow_html=True
            )

            for page in visible:
                icon = NAV_ICONS.get(page, "•")
                is_active = (
                    st.session_state.current_page == page
                )
                active_class = "active" if is_active else ""

                if st.button(
                    f"{icon}  {page}",
                    key=f"nav_{page}",
                    use_container_width=True
                ):
                    st.session_state.current_page = page
                    st.rerun()

        st.write("")
        st.markdown("---")
        if st.button(
            "🚪  Logout", use_container_width=True
        ):
            log_audit("Logout", st.session_state.username)
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()

    menu = st.session_state.current_page

    def page_header(title, subtitle=""):
        st.markdown(
            f'<div class="pb-header">'
            f'<h1>{title}</h1>'
            f'<p>{subtitle}</p>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ════════════════════════════════════════════════
    # DASHBOARD
    # ════════════════════════════════════════════════
    if menu == "Dashboard":
        page_header(
            "📊 Manager Dashboard",
            org_name + " — Clinical Operations Overview"
        )

        protocols = get_protocols()
        writers = get_writers()

        if not protocols:
            st.info(
                "No protocols added yet. "
                "Go to Protocols to get started."
            )
        else:
            today = date.today()
            total = len(protocols)
            completed = len([
                p for p in protocols
                if p["status"] == "Completed"
            ])
            in_progress = len([
                p for p in protocols
                if p["status"] == "In Progress"
            ])
            under_review = len([
                p for p in protocols
                if p["status"] == "Under Review"
            ])
            pending = len([
                p for p in protocols
                if p["status"] == "Not Started"
            ])
            overdue = len([
                p for p in protocols
                if p["status"] != "Completed"
                and datetime.strptime(
                    p["deadline"], "%Y-%m-%d"
                ).date() < today
            ])

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total", total)
            c2.metric("Completed", completed)
            c3.metric("In Progress", in_progress)
            c4.metric("Under Review", under_review)
            c5.metric("Not Started", pending)
            c6.metric("Overdue", overdue)

            if overdue > 0:
                st.error(
                    "⚠️ OVERDUE — Immediate attention required"
                )
                for p in protocols:
                    deadline = datetime.strptime(
                        p["deadline"], "%Y-%m-%d"
                    ).date()
                    days_late = (today - deadline).days
                    if (p["status"] != "Completed"
                            and deadline < today):
                        st.markdown(
                            f'<span class="badge-danger">'
                            f'OVERDUE {days_late}d</span> '
                            f'**{p["name"]}** → '
                            f'{p["assigned_to"]}',
                            unsafe_allow_html=True
                        )

            st.write("---")

            # ── GRAPHS ────────────────────────────────
            col1, col2, col3 = st.columns(3)

            # PIE CHART — Protocol Status
            with col1:
                st.subheader("Protocol Status")
                status_counts = {
                    "Not Started": pending,
                    "In Progress": in_progress,
                    "Under Review": under_review,
                    "Completed": completed
                }
                fig_pie = px.pie(
                    values=list(status_counts.values()),
                    names=list(status_counts.keys()),
                    color_discrete_sequence=[
                        "#6b7280", t["primary"],
                        t["secondary"], "#10b981"
                    ],
                    hole=0.4
                )
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=t["text"],
                    margin=dict(t=20, b=20, l=20, r=20),
                    legend=dict(
                        font=dict(color=t["text"])
                    ),
                    showlegend=True
                )
                fig_pie.update_traces(
                    textfont_color=t["text"]
                )
                st.plotly_chart(
                    fig_pie,
                    use_container_width=True
                )

            # BAR CHART — Team Workload
            with col2:
                st.subheader("Team Workload")
                if writers:
                    writer_names = []
                    active_counts = []
                    completed_counts = []
                    for writer in writers:
                        assigned = [
                            p for p in protocols
                            if p["assigned_to"] == writer
                        ]
                        writer_names.append(writer)
                        active_counts.append(len([
                            p for p in assigned
                            if p["status"] != "Completed"
                        ]))
                        completed_counts.append(len([
                            p for p in assigned
                            if p["status"] == "Completed"
                        ]))

                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        name="Active",
                        x=writer_names,
                        y=active_counts,
                        marker_color=t["primary"]
                    ))
                    fig_bar.add_trace(go.Bar(
                        name="Completed",
                        x=writer_names,
                        y=completed_counts,
                        marker_color="#10b981"
                    ))
                    fig_bar.update_layout(
                        barmode="group",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color=t["text"],
                        margin=dict(t=20, b=20, l=20, r=20),
                        legend=dict(
                            font=dict(color=t["text"])
                        ),
                        xaxis=dict(
                            gridcolor="#333333"
                        ),
                        yaxis=dict(
                            gridcolor="#333333"
                        )
                    )
                    st.plotly_chart(
                        fig_bar,
                        use_container_width=True
                    )

            # LINE GRAPH — Turnaround Trend
            with col3:
                st.subheader("Turnaround Trend")
                conn = get_db()
                c_db = conn.cursor()
                c_db.execute(
                    "SELECT completed_date, "
                    "AVG(turnaround_days) "
                    "FROM protocol_timeline "
                    "GROUP BY completed_date "
                    "ORDER BY completed_date"
                )
                trend_rows = c_db.fetchall()
                conn.close()

                if trend_rows:
                    fig_line = px.line(
                        x=[r[0] for r in trend_rows],
                        y=[r[1] for r in trend_rows],
                        labels={
                            "x": "Date",
                            "y": "Avg Days"
                        },
                        color_discrete_sequence=[
                            t["primary"]
                        ]
                    )
                    fig_line.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color=t["text"],
                        margin=dict(t=20, b=20, l=20, r=20),
                        xaxis=dict(
                            gridcolor="#333333"
                        ),
                        yaxis=dict(
                            gridcolor="#333333"
                        )
                    )
                    st.plotly_chart(
                        fig_line,
                        use_container_width=True
                    )
                else:
                    st.info(
                        "Complete protocols to see trend"
                    )

            st.write("---")
            st.subheader("Team Workload Summary")
            if writers:
                wdata = []
                for writer in writers:
                    assigned = [
                        p for p in protocols
                        if p["assigned_to"] == writer
                    ]
                    done = len([
                        p for p in assigned
                        if p["status"] == "Completed"
                    ])
                    active = len([
                        p for p in assigned
                        if p["status"] != "Completed"
                    ])
                    wdata.append({
                        "Writer": writer,
                        "Total": len(assigned),
                        "Completed": done,
                        "Active": active,
                        "Available": (
                            "✅ Yes"
                            if writers[writer].get(
                                "available", True
                            )
                            else "🔴 On Leave"
                        )
                    })
                st.table(wdata)

            st.write("---")
            col1, col2, col3 = st.columns(3)
            high = len([
                p for p in protocols
                if p["priority"] == "High"
                and p["status"] != "Completed"
            ])
            medium = len([
                p for p in protocols
                if p["priority"] == "Medium"
                and p["status"] != "Completed"
            ])
            low = len([
                p for p in protocols
                if p["priority"] == "Low"
                and p["status"] != "Completed"
            ])
            col1.metric("🔴 High Priority Active", high)
            col2.metric("🟡 Medium Priority Active", medium)
            col3.metric("🟢 Low Priority Active", low)

    # ════════════════════════════════════════════════
    # WRITERS
    # ════════════════════════════════════════════════
    elif menu == "Writers":
        page_header(
            "✍️ Writer Management",
            "Add and manage protocol writers and their specialties"
        )
        specialties = get_specialties()
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown(
                '<div class="pb-card">',
                unsafe_allow_html=True
            )
            st.subheader("Add New Writer")
            new_writer = st.text_input("Full Name")
            selected_specs = st.multiselect(
                "Select Specialties", options=specialties
            )
            st.write("**Add custom specialty:**")
            custom_spec = st.text_input("New Specialty")
            if st.button("➕ Add to List"):
                if custom_spec.strip():
                    add_specialty(custom_spec.strip())
                    log_audit(
                        "Added specialty: " + custom_spec,
                        st.session_state.username
                    )
                    st.success(custom_spec + " added!")
                    st.rerun()

            available = st.checkbox(
                "Currently Available", value=True
            )
            if st.button(
                "✅ Add Writer", use_container_width=True
            ):
                if new_writer.strip() and selected_specs:
                    add_writer(
                        new_writer.strip(),
                        selected_specs, available
                    )
                    log_audit(
                        "Added writer: " + new_writer,
                        st.session_state.username
                    )
                    st.success(new_writer + " added!")
                    st.rerun()
                else:
                    st.error(
                        "Please enter name and "
                        "select specialties"
                    )
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.subheader("Current Writers")
            writers = get_writers()
            if writers:
                for writer, info in writers.items():
                    avail = info.get("available", True)
                    badge = (
                        '<span class="badge-success">'
                        '✅ Available</span>'
                        if avail else
                        '<span class="badge-danger">'
                        '🔴 On Leave</span>'
                    )
                    with st.expander(writer):
                        st.markdown(
                            badge, unsafe_allow_html=True
                        )
                        st.write(
                            "**Specialties:** " +
                            ", ".join(info["specialties"])
                        )
                        new_avail = st.checkbox(
                            "Mark as Available",
                            value=avail,
                            key="avail_" + writer
                        )
                        if st.button(
                            "Update Status",
                            key="upd_" + writer
                        ):
                            update_writer_availability(
                                writer, new_avail
                            )
                            if not new_avail:
                                protocols = get_protocols()
                                writers_db = get_writers()
                                for p in protocols:
                                    if (
                                        p["assigned_to"] == writer
                                        and p["status"]
                                        != "Completed"
                                    ):
                                        eligible = [
                                            w for w, inf
                                            in writers_db.items()
                                            if inf.get(
                                                "available", True
                                            )
                                            and p["specialty"]
                                            in inf["specialties"]
                                            and w != writer
                                        ]
                                        if eligible:
                                            wl = {
                                                w: len([
                                                    x for x
                                                    in protocols
                                                    if x[
                                                        "assigned_to"
                                                    ] == w
                                                    and x["status"]
                                                    != "Completed"
                                                ])
                                                for w in eligible
                                            }
                                            new_w = min(
                                                wl, key=wl.get
                                            )
                                            reassign_protocol(
                                                p["id"], new_w
                                            )
                                            log_audit(
                                                "Auto-reassigned "
                                                + p["name"] +
                                                " to " + new_w,
                                                st.session_state.username
                                            )
                            log_audit(
                                "Updated: " + writer,
                                st.session_state.username
                            )
                            st.success("Updated!")
                            st.rerun()
            else:
                st.info("No writers added yet.")

    # ════════════════════════════════════════════════
    # PROTOCOLS
    # ════════════════════════════════════════════════
    elif menu == "Protocols":
        page_header(
            "📋 Protocol Management",
            "Add protocols and auto-assign to best available writer"
        )
        specialties = get_specialties()
        writers = get_writers()
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown(
                '<div class="pb-card">',
                unsafe_allow_html=True
            )
            st.subheader("Add New Protocol")
            new_protocol = st.text_input("Protocol Name")
            new_specialty = st.selectbox(
                "Required Specialty", options=specialties
            )
            new_priority = st.selectbox(
                "Priority", ["High", "Medium", "Low"]
            )
            new_deadline = st.date_input(
                "Deadline", min_value=date.today()
            )

            if st.button(
                "🚀 Add and Auto-Assign",
                use_container_width=True
            ):
                if new_protocol.strip():
                    protocols = get_protocols()
                    avail = {
                        w: info for w, info in writers.items()
                        if info.get("available", True)
                        and new_specialty in info["specialties"]
                    }
                    if avail:
                        wl = {
                            w: len([
                                p for p in protocols
                                if p["assigned_to"] == w
                                and p["status"] != "Completed"
                            ])
                            for w in avail
                        }
                        assigned = min(wl, key=wl.get)
                    else:
                        assigned = (
                            "UNASSIGNED - No specialist"
                        )
                    add_protocol(
                        new_protocol.strip(),
                        new_specialty, new_priority,
                        str(new_deadline), assigned
                    )
                    log_audit(
                        "Added: " + new_protocol +
                        " → " + assigned,
                        st.session_state.username
                    )
                    st.success(
                        "Assigned to " + assigned + "!"
                    )
                    st.rerun()
                else:
                    st.error("Please enter protocol name")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.subheader("All Protocols")
            protocols = get_protocols()
            writers_db = get_writers()
            if protocols:
                today = date.today()
                for p in protocols:
                    deadline = datetime.strptime(
                        p["deadline"], "%Y-%m-%d"
                    ).date()
                    days_left = (deadline - today).days

                    if p["status"] == "Completed":
                        badge = (
                            '<span class="badge-success">'
                            'Completed</span>'
                        )
                    elif days_left < 0:
                        badge = (
                            '<span class="badge-danger">'
                            'OVERDUE</span>'
                        )
                    elif days_left <= 3:
                        badge = (
                            '<span class="badge-warning">'
                            'URGENT</span>'
                        )
                    else:
                        badge = (
                            '<span class="badge-info">'
                            'On Track</span>'
                        )

                    with st.expander(
                        p["name"] + " | " + p["priority"]
                    ):
                        st.markdown(
                            badge, unsafe_allow_html=True
                        )
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(
                                "**Specialty:** " +
                                p["specialty"]
                            )
                            st.write(
                                "**Assigned To:** " +
                                p["assigned_to"]
                            )
                        with col_b:
                            st.write(
                                "**Deadline:** " +
                                p["deadline"]
                            )
                            st.write(
                                "**Status:** " + p["status"]
                            )

                        if (p["status"] != "Completed"
                                and days_left >= 0):
                            st.info(
                                str(days_left) + " days left"
                            )
                        elif (p["status"] != "Completed"
                              and days_left < 0):
                            st.error(
                                "Overdue by " +
                                str(abs(days_left)) + " days"
                            )

                        writer_list = list(writers_db.keys())
                        if writer_list:
                            st.write("**Reassign:**")
                            new_assignee = st.selectbox(
                                "Select Writer",
                                writer_list,
                                key="rs_" + str(p["id"])
                            )
                            if st.button(
                                "🔄 Reassign",
                                key="do_rs_" + str(p["id"])
                            ):
                                reassign_protocol(
                                    p["id"], new_assignee
                                )
                                log_audit(
                                    "Reassigned " +
                                    p["name"] + " to " +
                                    new_assignee,
                                    st.session_state.username
                                )
                                st.success(
                                    "Reassigned to " +
                                    new_assignee
                                )
                                st.rerun()
            else:
                st.info("No protocols added yet.")

    # ════════════════════════════════════════════════
    # PROGRESS
    # ════════════════════════════════════════════════
    elif menu == "Progress":
        page_header(
            "🔄 Progress Tracking",
            "Update protocol status and track completion"
        )
        protocols = get_protocols()

        if not protocols:
            st.info("No protocols added yet.")
        else:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All", "Not Started", "In Progress",
                 "Under Review", "Completed"]
            )
            for p in protocols:
                if (status_filter != "All"
                        and p["status"] != status_filter):
                    continue

                with st.expander(
                    p["name"] + " — " + p["assigned_to"]
                ):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        if p["status"] == "Completed":
                            st.markdown(
                                '<span class="badge-success">'
                                'Completed</span>',
                                unsafe_allow_html=True
                            )
                        elif p["status"] == "In Progress":
                            st.markdown(
                                '<span class="badge-info">'
                                'In Progress</span>',
                                unsafe_allow_html=True
                            )
                        elif p["status"] == "Under Review":
                            st.markdown(
                                '<span class="badge-warning">'
                                'Under Review</span>',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                '<span class="badge-danger">'
                                'Not Started</span>',
                                unsafe_allow_html=True
                            )
                        st.write(
                            "**Writer:** " + p["assigned_to"]
                        )
                        st.write(
                            "**Deadline:** " + p["deadline"]
                        )
                        st.write(
                            "**Priority:** " + p["priority"]
                        )

                    with col2:
                        opts = [
                            "Not Started", "In Progress",
                            "Under Review", "Completed"
                        ]
                        new_status = st.selectbox(
                            "Update Status", opts,
                            key="st_" + str(p["id"]),
                            index=opts.index(p["status"])
                        )
                        if st.button(
                            "✅ Update",
                            key="upd_st_" + str(p["id"])
                        ):
                            old = p["status"]
                            update_protocol_status(
                                p["id"], new_status
                            )
                            if new_status == "Completed":
                                save_turnaround(
                                    p["id"], p["name"],
                                    p["assigned_to"],
                                    p["added_on"]
                                )
                            log_audit(
                                p["name"] + ": " +
                                old + " → " + new_status,
                                st.session_state.username
                            )
                            st.success(
                                "Updated to " + new_status
                            )
                            st.rerun()

    # ════════════════════════════════════════════════
    # FEEDBACK
    # ════════════════════════════════════════════════
    elif menu == "Feedback":
        page_header(
            "⭐ Feedback and Ratings",
            "Rate completed protocols and track writer performance"
        )
        protocols = get_protocols()
        feedback = get_feedback()
        completed = [
            p for p in protocols
            if p["status"] == "Completed"
        ]

        if not completed:
            st.info(
                "No completed protocols yet. "
                "Mark protocols as Completed first."
            )
        else:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Rate Protocols")
                for p in completed:
                    with st.expander(
                        p["name"] + " — " + p["assigned_to"]
                    ):
                        existing = feedback.get(p["name"], {})
                        rating = st.slider(
                            "Rating (1-5 stars)",
                            1, 5,
                            value=existing.get("rating", 3),
                            key="rat_" + str(p["id"])
                        )
                        stars = "⭐" * rating
                        st.write(stars)
                        comment = st.text_area(
                            "Comments",
                            value=existing.get("comment", ""),
                            key="com_" + str(p["id"])
                        )
                        if st.button(
                            "💾 Save Feedback",
                            key="fb_" + str(p["id"])
                        ):
                            save_feedback(
                                p["name"],
                                p["assigned_to"],
                                rating, comment
                            )
                            log_audit(
                                "Feedback: " + p["name"] +
                                " — " + str(rating) + "★",
                                st.session_state.username
                            )
                            st.success("Saved!")
                            st.rerun()

            with col2:
                st.subheader("Performance Summary")
                feedback = get_feedback()
                if feedback:
                    writer_scores = {}
                    for pname, fb in feedback.items():
                        w = fb["writer"]
                        if w not in writer_scores:
                            writer_scores[w] = []
                        writer_scores[w].append(fb["rating"])

                    perf_writers = []
                    perf_avgs = []
                    perf_table = []

                    for w, scores in writer_scores.items():
                        avg = sum(scores) / len(scores)
                        perf_writers.append(w)
                        perf_avgs.append(round(avg, 1))
                        perf_table.append({
                            "Writer": w,
                            "Rated": len(scores),
                            "Avg": str(round(avg, 1)) + "/5",
                            "Stars": "⭐" * round(avg)
                        })

                    fig_perf = px.bar(
                        x=perf_writers,
                        y=perf_avgs,
                        labels={"x": "Writer", "y": "Avg Rating"},
                        color=perf_avgs,
                        color_continuous_scale=[
                            "#ef4444", "#f59e0b", "#10b981"
                        ],
                        range_y=[0, 5]
                    )
                    fig_perf.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color=t["text"],
                        margin=dict(t=20, b=20, l=20, r=20),
                        showlegend=False,
                        xaxis=dict(
                            gridcolor="#333333"
                        ),
                        yaxis=dict(
                            gridcolor="#333333"
                        )
                    )
                    st.plotly_chart(
                        fig_perf, use_container_width=True
                    )
                    st.table(perf_table)
                else:
                    st.info("No feedback submitted yet.")

    # ════════════════════════════════════════════════
    # AUDIT LOG
    # ════════════════════════════════════════════════
    elif menu == "Audit Log":
        page_header(
            "🔍 Audit Trail",
            "Complete log of all actions for regulatory compliance"
        )
        audit = get_audit_log()
        if audit:
            st.table(pd.DataFrame(audit))
        else:
            st.info("No actions logged yet.")

    # ════════════════════════════════════════════════
    # EXPORT
    # ════════════════════════════════════════════════
    elif menu == "Export":
        page_header(
            "📥 Export Reports",
            "Download complete reports as Excel"
        )
        protocols = get_protocols()
        feedback = get_feedback()
        audit = get_audit_log()

        if protocols:
            today = date.today()
            export_data = []
            for p in protocols:
                deadline = datetime.strptime(
                    p["deadline"], "%Y-%m-%d"
                ).date()
                days_left = (deadline - today).days
                if p["status"] == "Completed":
                    ts = "Completed"
                elif days_left < 0:
                    ts = (
                        "OVERDUE " +
                        str(abs(days_left)) + " days"
                    )
                elif days_left == 0:
                    ts = "DUE TODAY"
                elif days_left <= 3:
                    ts = str(days_left) + " days URGENT"
                else:
                    ts = str(days_left) + " days left"

                fb = feedback.get(p["name"], {})
                export_data.append({
                    "Protocol": p["name"],
                    "Specialty": p["specialty"],
                    "Priority": p["priority"],
                    "Assigned To": p["assigned_to"],
                    "Deadline": p["deadline"],
                    "Status": p["status"],
                    "Time Status": ts,
                    "Rating": fb.get("rating", "N/A"),
                    "Feedback": fb.get("comment", "N/A")
                })

            df = pd.DataFrame(export_data)
            st.subheader("Full Protocol Report")
            st.table(df)

            buffer = io.BytesIO()
            with pd.ExcelWriter(
                buffer, engine="openpyxl"
            ) as writer:
                df.to_excel(
                    writer, index=False,
                    sheet_name="Protocols"
                )
                if audit:
                    pd.DataFrame(audit).to_excel(
                        writer, index=False,
                        sheet_name="Audit Log"
                    )
                if feedback:
                    fb_list = [{
                        "Protocol": pn,
                        "Writer": fb["writer"],
                        "Rating": fb["rating"],
                        "Comment": fb["comment"],
                        "Date": fb["date"]
                    } for pn, fb in feedback.items()]
                    pd.DataFrame(fb_list).to_excel(
                        writer, index=False,
                        sheet_name="Feedback"
                    )

            st.download_button(
                label="📥 Download Full Report as Excel",
                data=buffer.getvalue(),
                file_name=(
                    "ProtoBalance_" + str(today) + ".xlsx"
                ),
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        else:
            st.info("No protocols to export yet.")

    # ════════════════════════════════════════════════
    # SETTINGS
    # ════════════════════════════════════════════════
    elif menu == "Settings":
        page_header(
            "⚙️ Settings",
            "Customise your ProtoBalance experience"
        )
        settings = get_user_settings(
            st.session_state.username
        )

        tab1, tab2, tab3 = st.tabs([
            "🎨 Theme & Branding",
            "🔐 Password",
            "👁️ Preview"
        ])

        with tab1:
            col1, col2 = st.columns([1, 1])

            with col1:
                st.subheader("Organisation Name")
                org_name_input = st.text_input(
                    "Name",
                    value=settings.get(
                        "org_name", "My Organisation"
                    )
                )

                st.write("---")
                st.subheader("Upload Logo")
                st.caption(
                    "Appears in sidebar after upload."
                )
                uploaded_logo = st.file_uploader(
                    "Choose logo image",
                    type=["png", "jpg", "jpeg"]
                )
                if uploaded_logo:
                    img = Image.open(uploaded_logo)
                    img = img.resize((300, 300))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    logo_b64 = base64.b64encode(
                        buf.getvalue()
                    ).decode()
                    st.image(
                        img, caption="Preview", width=120
                    )
                    st.session_state[
                        "pending_logo"
                    ] = logo_b64

            with col2:
                st.subheader("Choose Theme")
                theme_options = {
                    "purple": "💜 Purple Dark",
                    "blue": "💙 Blue Professional",
                    "green": "💚 Green Medical",
                    "light": "🤍 Light Clean",
                    "dark": "🖤 Dark Gold"
                }

                current_theme = settings.get(
                    "theme", "purple"
                )
                selected_theme = st.radio(
                    "Select your theme",
                    options=list(theme_options.keys()),
                    format_func=lambda x: theme_options[x],
                    index=list(
                        theme_options.keys()
                    ).index(current_theme)
                )

                # Theme preview
                prev_t = THEMES[selected_theme]
                st.markdown(
                    f'<div style="background:{prev_t["card"]};'
                    f'border-radius:12px;padding:16px;'
                    f'border-left:4px solid {prev_t["primary"]};'
                    f'margin-top:16px;">'
                    f'<span style="color:{prev_t["primary"]};'
                    f'font-weight:700;font-size:16px;">'
                    f'{prev_t["name"]}</span><br>'
                    f'<span style="color:{prev_t["secondary"]};'
                    f'font-size:13px;">Preview of selected theme'
                    f'</span></div>',
                    unsafe_allow_html=True
                )

            st.write("---")
            if st.button(
                "💾 Save Settings",
                use_container_width=True
            ):
                logo_to_save = st.session_state.get(
                    "pending_logo", None
                )
                save_user_settings(
                    st.session_state.username,
                    selected_theme,
                    org_name_input,
                    logo_to_save
                )
                log_audit(
                    "Settings updated",
                    st.session_state.username
                )
                st.success(
                    "Settings saved! "
                    "Refresh to see theme change."
                )
                st.rerun()

        with tab2:
            st.subheader("Change Password")
            new_password = st.text_input(
                "New Password", type="password"
            )
            confirm_password = st.text_input(
                "Confirm Password", type="password"
            )
            if st.button(
                "🔐 Update Password",
                use_container_width=True
            ):
                if new_password and confirm_password:
                    if new_password == confirm_password:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute(
                            "UPDATE users SET password=? "
                            "WHERE username=?",
                            (hash_pw(new_password),
                             st.session_state.username)
                        )
                        conn.commit()
                        conn.close()
                        log_audit(
                            "Password changed",
                            st.session_state.username
                        )
                        st.success("Password updated!")
                    else:
                        st.error("Passwords do not match")
                else:
                    st.error("Please fill both fields")

        with tab3:
            st.subheader("Theme Preview")
            for tk, tv in THEMES.items():
                st.markdown(
                    f'<div style="background:{tv["card"]};'
                    f'border-radius:12px;padding:16px;'
                    f'margin-bottom:8px;'
                    f'border-left:4px solid {tv["primary"]};">'
                    f'<span style="color:{tv["primary"]};'
                    f'font-weight:700;">{tv["name"]}</span>'
                    f'<span style="color:{tv["secondary"]};'
                    f'margin-left:12px;font-size:13px;">'
                    f'Primary: {tv["primary"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # ════════════════════════════════════════════════
    # GCP COMPLIANCE
    # ════════════════════════════════════════════════
    elif menu == "GCP Compliance":
        page_header(
            "🏅 ICH-GCP Compliance Tracker",
            "Track certification status — expired certs flagged automatically"
        )
        writers = get_writers()
        certs = get_gcp_certifications()
        today = date.today()
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown(
                '<div class="pb-card">',
                unsafe_allow_html=True
            )
            st.subheader("Add Certification")
            writer_list = list(writers.keys())
            if writer_list:
                selected_writer = st.selectbox(
                    "Select Writer", writer_list
                )
                cert_date = st.date_input(
                    "Certification Date",
                    value=date.today()
                )
                expiry_date = st.date_input(
                    "Expiry Date",
                    value=date(
                        today.year + 2,
                        today.month, today.day
                    )
                )
                cert_body = st.selectbox(
                    "Certification Body",
                    ["ICRP", "ACRP", "CCRPS",
                     "ICH", "MHRA", "Other"]
                )
                if st.button(
                    "💾 Save Certification",
                    use_container_width=True
                ):
                    save_gcp_certification(
                        selected_writer,
                        str(cert_date),
                        str(expiry_date),
                        cert_body
                    )
                    log_audit(
                        "GCP cert updated: " +
                        selected_writer,
                        st.session_state.username
                    )
                    st.success("Saved!")
                    st.rerun()
            else:
                st.info("Add writers first.")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.subheader("Certification Status")
            if writers:
                cert_data = []
                for writer in writers:
                    cert = certs.get(writer, {})
                    if cert:
                        expiry = datetime.strptime(
                            cert["expiry_date"], "%Y-%m-%d"
                        ).date()
                        dte = (expiry - today).days
                        if dte < 0:
                            status = "EXPIRED"
                            badge = "badge-danger"
                        elif dte <= 30:
                            status = (
                                "EXPIRING SOON — " +
                                str(dte) + " days"
                            )
                            badge = "badge-warning"
                        else:
                            status = (
                                "Valid — " +
                                str(dte) + " days"
                            )
                            badge = "badge-success"
                    else:
                        status = "NO CERT ON FILE"
                        badge = "badge-danger"
                        cert = {
                            "certification_body": "N/A",
                            "expiry_date": "N/A"
                        }

                    cert_data.append({
                        "Writer": writer,
                        "Body": cert.get(
                            "certification_body", "N/A"
                        ),
                        "Expiry": cert.get(
                            "expiry_date", "N/A"
                        ),
                        "Status": status
                    })

                exp = [
                    d for d in cert_data
                    if "EXPIRED" in d["Status"]
                    or "NO CERT" in d["Status"]
                ]
                expiring = [
                    d for d in cert_data
                    if "EXPIRING" in d["Status"]
                ]

                if exp:
                    st.error(
                        str(len(exp)) +
                        " writer(s) need immediate attention"
                    )
                if expiring:
                    st.warning(
                        str(len(expiring)) +
                        " certification(s) expiring soon"
                    )

                st.table(pd.DataFrame(cert_data))

                # GCP Chart
                valid_c = len([
                    d for d in cert_data
                    if "Valid" in d["Status"]
                ])
                exp_c = len([
                    d for d in cert_data
                    if "EXPIRED" in d["Status"]
                ])
                exp_soon_c = len([
                    d for d in cert_data
                    if "EXPIRING" in d["Status"]
                ])
                no_cert_c = len([
                    d for d in cert_data
                    if "NO CERT" in d["Status"]
                ])

                fig_gcp = px.pie(
                    values=[valid_c, exp_c,
                             exp_soon_c, no_cert_c],
                    names=["Valid", "Expired",
                           "Expiring Soon", "No Cert"],
                    color_discrete_sequence=[
                        "#10b981", "#ef4444",
                        "#f59e0b", "#6b7280"
                    ],
                    hole=0.4
                )
                fig_gcp.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=t["text"],
                    margin=dict(t=20, b=20, l=20, r=20)
                )
                st.plotly_chart(
                    fig_gcp, use_container_width=True
                )
            else:
                st.info("No writers added yet.")

    # ════════════════════════════════════════════════
    # SOP MANAGEMENT
    # ════════════════════════════════════════════════
    elif menu == "SOP Management":
        page_header(
            "📑 SOP Acknowledgement System",
            "Track SOP compliance — audit ready at all times"
        )
        sops = get_sops()
        writers = get_writers()
        acknowledgements = get_acknowledgements()

        tab1, tab2, tab3 = st.tabs([
            "📊 Acknowledgement Matrix",
            "➕ Add New SOP",
            "📈 Compliance Report"
        ])

        with tab1:
            if sops and writers:
                matrix_data = []
                for writer in writers:
                    writer_acks = acknowledgements.get(
                        writer, []
                    )
                    row = {"Writer": writer}
                    for sop in sops:
                        row[sop["sop_number"]] = (
                            "✅" if sop["id"] in writer_acks
                            else "❌"
                        )
                    matrix_data.append(row)
                st.table(pd.DataFrame(matrix_data))

                st.write("---")
                col1, col2 = st.columns(2)
                with col1:
                    ack_writer = st.selectbox(
                        "Writer",
                        list(writers.keys()),
                        key="ack_writer"
                    )
                with col2:
                    sop_options = {
                        s["sop_number"] + " — " +
                        s["sop_title"]: s["id"]
                        for s in sops
                    }
                    selected_sop = st.selectbox(
                        "SOP", list(sop_options.keys())
                    )
                if st.button(
                    "✅ Record Acknowledgement",
                    use_container_width=True
                ):
                    sop_id = sop_options[selected_sop]
                    acknowledge_sop(ack_writer, sop_id)
                    log_audit(
                        ack_writer + " ack: " + selected_sop,
                        st.session_state.username
                    )
                    st.success("Recorded!")
                    st.rerun()
            else:
                st.info("Add writers and SOPs first.")

        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                new_sop_number = st.text_input(
                    "SOP Number", placeholder="SOP-007"
                )
                new_sop_title = st.text_input("SOP Title")
                new_sop_version = st.text_input(
                    "Version", placeholder="v1.0"
                )
            with col2:
                new_sop_date = st.date_input(
                    "Effective Date"
                )
                new_sop_dept = st.selectbox(
                    "Department",
                    ["Clinical Operations",
                     "Quality Assurance",
                     "Regulatory Affairs",
                     "Pharmacovigilance",
                     "Data Management",
                     "Medical Affairs"]
                )
            if st.button(
                "➕ Add SOP", use_container_width=True
            ):
                if new_sop_number and new_sop_title:
                    add_sop(
                        new_sop_number, new_sop_title,
                        new_sop_version,
                        str(new_sop_date), new_sop_dept
                    )
                    log_audit(
                        "Added SOP: " + new_sop_number,
                        st.session_state.username
                    )
                    st.success("SOP added!")
                    st.rerun()
                else:
                    st.error("Please fill required fields")

        with tab3:
            if sops and writers:
                total_sops = len(sops)
                compliance_data = []
                comp_writers = []
                comp_pcts = []

                for writer in writers:
                    writer_acks = acknowledgements.get(
                        writer, []
                    )
                    done = len(writer_acks)
                    pct = round(
                        (done / total_sops) * 100
                    )
                    compliance_data.append({
                        "Writer": writer,
                        "Acknowledged": done,
                        "Total": total_sops,
                        "Compliance": str(pct) + "%",
                        "Status": (
                            "✅ Fully Compliant"
                            if pct == 100
                            else "⚠️ " +
                            str(total_sops - done) +
                            " pending"
                        )
                    })
                    comp_writers.append(writer)
                    comp_pcts.append(pct)

                fig_comp = px.bar(
                    x=comp_writers,
                    y=comp_pcts,
                    labels={
                        "x": "Writer",
                        "y": "Compliance %"
                    },
                    color=comp_pcts,
                    color_continuous_scale=[
                        "#ef4444", "#f59e0b", "#10b981"
                    ],
                    range_y=[0, 100]
                )
                fig_comp.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=t["text"],
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=False,
                    xaxis=dict(
                        gridcolor="#333333"
                    ),
                    yaxis=dict(
                        gridcolor="#333333"
                    )
                )
                st.plotly_chart(
                    fig_comp, use_container_width=True
                )
                st.table(pd.DataFrame(compliance_data))
            else:
                st.info("No data available yet.")

    # ════════════════════════════════════════════════
    # ANALYTICS
    # ════════════════════════════════════════════════
    elif menu == "Analytics":
        page_header(
            "📈 Turnaround Time Analytics",
            "Performance data calculated automatically"
        )
        analytics = get_turnaround_analytics()

        if not analytics:
            st.info(
                "No completed protocols yet. "
                "Mark protocols as Completed to see analytics."
            )
        else:
            fastest = min(
                analytics, key=lambda x: x["Avg Days"]
            )
            slowest = max(
                analytics, key=lambda x: x["Avg Days"]
            )
            most = max(
                analytics,
                key=lambda x: x["Total Completed"]
            )

            col1, col2, col3 = st.columns(3)
            col1.metric(
                "⚡ Fastest Writer",
                fastest["Writer"],
                str(fastest["Avg Days"]) + " avg days"
            )
            col2.metric(
                "🏆 Most Productive",
                most["Writer"],
                str(most["Total Completed"]) + " completed"
            )
            col3.metric(
                "⚠️ Needs Attention",
                slowest["Writer"],
                str(slowest["Avg Days"]) + " avg days"
            )

            st.write("---")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Avg Turnaround by Writer")
                fig_ta = px.bar(
                    x=[a["Writer"] for a in analytics],
                    y=[a["Avg Days"] for a in analytics],
                    labels={
                        "x": "Writer",
                        "y": "Avg Days"
                    },
                    color=[a["Avg Days"] for a in analytics],
                    color_continuous_scale=[
                        "#10b981", "#f59e0b", "#ef4444"
                    ]
                )
                fig_ta.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=t["text"],
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=False,
                    xaxis=dict(
                        gridcolor="#333333"
                    ),
                    yaxis=dict(
                        gridcolor="#333333"
                    )
                )
                st.plotly_chart(
                    fig_ta, use_container_width=True
                )

            with col2:
                st.subheader("Protocols Completed")
                fig_prod = px.bar(
                    x=[a["Writer"] for a in analytics],
                    y=[
                        a["Total Completed"]
                        for a in analytics
                    ],
                    labels={
                        "x": "Writer",
                        "y": "Total Completed"
                    },
                    color_discrete_sequence=[t["primary"]]
                )
                fig_prod.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=t["text"],
                    margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(
                        gridcolor="#333333"
                    ),
                    yaxis=dict(
                        gridcolor="#333333"
                    )
                )
                st.plotly_chart(
                    fig_prod, use_container_width=True
                )

            st.write("---")
            st.subheader("Performance Table")
            st.table(pd.DataFrame(analytics))

            st.write("---")
            st.subheader("Protocol Timeline")
            conn = get_db()
            c_db = conn.cursor()
            c_db.execute(
                "SELECT protocol_name, writer_name, "
                "assigned_date, completed_date, "
                "turnaround_days FROM protocol_timeline "
                "ORDER BY completed_date DESC"
            )
            rows = c_db.fetchall()
            conn.close()
            if rows:
                st.table(pd.DataFrame([{
                    "Protocol": r[0],
                    "Writer": r[1],
                    "Assigned": r[2],
                    "Completed": r[3],
                    "Days": r[4]
                } for r in rows]))

    # ════════════════════════════════════════════════
    # ADMIN PANEL
    # ════════════════════════════════════════════════
    elif menu == "Admin Panel":
        if st.session_state.role != "admin":
            st.error("Access denied.")
        else:
            page_header(
                "🔐 Admin Panel",
                "Manage users and system settings"
            )
            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown(
                    '<div class="pb-card">',
                    unsafe_allow_html=True
                )
                st.subheader("Create New User")
                new_username = st.text_input("Username")
                new_password = st.text_input(
                    "Password", type="password"
                )
                new_role = st.selectbox(
                    "Role", ["manager", "admin"]
                )
                if st.button(
                    "➕ Create User",
                    use_container_width=True
                ):
                    if new_username and new_password:
                        success = create_user(
                            new_username,
                            new_password, new_role
                        )
                        if success:
                            log_audit(
                                "Created user: " +
                                new_username,
                                st.session_state.username
                            )
                            st.success(
                                "User " + new_username +
                                " created!"
                            )
                            st.rerun()
                        else:
                            st.error(
                                "Username already exists"
                            )
                    else:
                        st.error("Fill all fields")
                st.markdown(
                    '</div>', unsafe_allow_html=True
                )

            with col2:
                st.subheader("All Users")
                users = get_all_users()
                if users:
                    st.table(pd.DataFrame([{
                        "Username": u[0],
                        "Role": u[1]
                    } for u in users]))