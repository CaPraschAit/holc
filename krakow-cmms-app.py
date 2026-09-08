#!/usr/bin/env python3
# krakow-cmms-app.py
# Streamlit CMMS — UI + UX improvements (search, CSV export, email placeholder, Holcim colors)
# - top navigation
# - search & pagination for assets
# - CSV download for assets/parts/RM
# - email-send UI (simulated)
# - operator mode default for roles containing "Technik"
# - cached loaders & safe DB writes

import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os
import textwrap
from typing import Optional, Tuple

# -------------------------
# Configuration & DB Init
# -------------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "cmms.db")

INIT_SQL = textwrap.dedent("""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  code TEXT,
  name TEXT,
  section TEXT,
  criticality TEXT,
  status TEXT
);
CREATE TABLE IF NOT EXISTS parts (
  id TEXT PRIMARY KEY,
  name TEXT,
  location TEXT,
  stock INTEGER,
  min_stock INTEGER
);
CREATE TABLE IF NOT EXISTS users (
  email TEXT PRIMARY KEY,
  role TEXT,
  sep_d TEXT,
  sep_e TEXT
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id TEXT,
  user_email TEXT,
  role TEXT,
  all_ok INTEGER,
  comments TEXT,
  sep_signature TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reactive_maintenance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id TEXT,
  description TEXT,
  status TEXT,
  priority TEXT,
  assigned_role TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS part_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  part_id TEXT,
  quantity INTEGER,
  asset_id TEXT,
  user_email TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO assets (id, code, name, section, criticality, status) VALUES
('NH-SM-09','C-1009','Mieszalnik NH-SM-09','Mieszalniki','Wysoka','Sprawny'),
('NH-SM-47','C-1047','Odpylacz Pakowaczki NH-SM-47','Pakowaczki','Średnia','Sprawny'),
('NH-MX-09','C-2009','Waga Popiołu W NH-MX-09','Wagi','Wysoka','Sprawny');
INSERT OR IGNORE INTO parts (id, name, location, stock, min_stock) VALUES
('PART-USZCZELKA-MIX','Uszczelka boczna Mix','Regał A1',5,2),
('PART-WORKI-SM','Worki filtracyjne SM','Regał B3',10,5),
('PART-ROLEK-TAŚMA','Rolek do taśmy suszarni','Regał C2',2,2);
INSERT OR IGNORE INTO users (email, role, sep_d, sep_e) VALUES
('wojciech.nowak@holcim.com','Technik Elektryk','D1/2671/129/25','E1/2672/129/25'),
('mechanik@holcim.com','Technik AKP / Mechanik',NULL,NULL),
('planista@holcim.com','Planista',NULL,NULL);
""")

def init_db_if_missing() -> None:
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(INIT_SQL)
        conn.commit()
        conn.close()

init_db_if_missing()

# -------------------------
# DB helpers
# -------------------------
class DBConnection:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if self.conn:
            if exc_type is None:
                try:
                    self.conn.commit()
                except Exception:
                    pass
            else:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            try:
                self.conn.close()
            except Exception:
                pass

@st.cache_data(ttl=120)
def load_assets() -> pd.DataFrame:
    with DBConnection() as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM assets ORDER BY id", conn)
        except Exception:
            df = pd.DataFrame(columns=['id','code','name','section','criticality','status'])
    return df

@st.cache_data(ttl=120)
def load_parts() -> pd.DataFrame:
    with DBConnection() as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM parts ORDER BY id", conn)
        except Exception:
            df = pd.DataFrame(columns=['id','name','location','stock','min_stock'])
    return df

@st.cache_data(ttl=120)
def load_users() -> pd.DataFrame:
    with DBConnection() as conn:
        try:
            df = pd.read_sql_query("SELECT email, role FROM users ORDER BY email", conn)
        except Exception:
            df = pd.DataFrame(columns=['email','role'])
    return df

def safe_query_df(query: str, params: Tuple = ()) -> pd.DataFrame:
    with DBConnection() as conn:
        try:
            df = pd.read_sql_query(query, conn, params=params)
        except Exception:
            df = pd.DataFrame()
    return df

def execute_write(query: str, params: Tuple = ()) -> None:
    with DBConnection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
    try:
        st.cache_data.clear()
    except Exception:
        pass

# -------------------------
# UI Setup & Holcim Theme
# -------------------------
st.set_page_config(page_title="Holcim Kraków — CMMS", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")

# Holcim brand: primary orange and accent teal
PRIMARY = "#E84E2A"   # Holcim orange
ACCENT = "#0f766e"
TEXT = "#0f172a"

st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {{ --brand: {PRIMARY}; --accent: {ACCENT}; --text: {TEXT}; --muted:#6b7280; --card:#ffffff; --bg:#f9fafb; }}
section.main {{ padding-top:12px; }}
.app-container {{ max-width:1180px; margin:0 auto; padding:0 12px; }}
.stSidebar .css-1lcbmhc {{ width:280px; }}

.header {{
  font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial;
  font-size:30px !important; font-weight:700; color:var(--text); margin-bottom:8px;
  padding-bottom:8px; border-bottom: 3px solid rgba(232,78,42,0.08);
}}
.card {{ background:var(--card); border-radius:12px; padding:16px; box-shadow:0 8px 18px rgba(2,6,23,0.04); margin-bottom:14px; }}
.kpi {{ background: linear-gradient(180deg,#ffffff,#fbfff9); border-radius:10px; padding:10px; text-align:center; }}
.stButton>button {{ border-radius:10px; height:44px; font-weight:600; }}
.small-muted {{ color:var(--muted); font-size:13px; }}
.searchbox input[type="text"] {{ padding:10px 12px; border-radius:8px; }}
.download-btn > button {{ background: var(--brand); color: white; border-radius:8px; height:40px; }}
.nav-btns > label {{ margin-right:8px; }}
@media (max-width:900px) {{
  .stSidebar .css-1lcbmhc {{ width:100% !important; }}
  .app-container {{ padding:0 8px; }}
}}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar: user & context
# -------------------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/e5/Holcim_logo.svg", width=140)
st.sidebar.markdown("### 🔒 Logowanie CMMS: PF01_KRAKÓW")

users_df = load_users()
user_list = users_df['email'].tolist() if not users_df.empty else ["mechanik@holcim.com"]
selected_user = st.sidebar.selectbox("Wybierz użytkownika:", user_list)

u_row = safe_query_df("SELECT email, role, sep_d, sep_e FROM users WHERE email = ?", (selected_user,))
if not u_row.empty:
    user_email = u_row.iloc[0]['email']
    user_role = u_row.iloc[0]['role']
    sep_d = u_row.iloc[0].get('sep_d', None)
    sep_e = u_row.iloc[0].get('sep_e', None)
else:
    user_email = selected_user
    user_role = "Technik"
    sep_d = sep_e = None

st.sidebar.markdown(f"**Rola:** `{user_role}`")
if sep_d or sep_e:
    st.sidebar.markdown(f"🛡️ SEP: Dozór `{sep_d}` • Eksploatacja `{sep_e}`")
else:
    st.sidebar.markdown("ℹ️ Użytkownik bez uprawnień SEP")
st.sidebar.markdown("---")
st.sidebar.markdown("🌱 **Zakład:** `PF01_KRAKÓW (ul. Cementowa 2)`")
st.sidebar.markdown("⏱️ **Czas systemowy:** " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
st.sidebar.markdown("---")

# Operator mode default enabled for roles containing "Technik"
default_op = True if "Technik" in (user_role or "") else False
op_mode = st.sidebar.checkbox("Włącz Tryb Operatora (upraszczony)", value=default_op)
st.sidebar.markdown("<div class='small-muted'>Wersja demo — funkcje testowe</div>", unsafe_allow_html=True)

# -------------------------
# Main container + navigation
# -------------------------
st.markdown("<div class='app-container'>", unsafe_allow_html=True)
st.markdown(f"<div class='header'>PORTAL OPERACYJNO‑WDROŻENIOWY CMMS: PF01_KRAKÓW</div>", unsafe_allow_html=True)

nav = st.radio("", ["Hala", "Kalibracje AKP", "Magazyn WMS", "Pulpit", "Raporty", "Analizy AI"], horizontal=True)

# -------------------------
# Common helpers: CSV download
# -------------------------
def make_csv_bytes(df: pd.DataFrame) -> bytes:
    if df is None or df.empty:
        return "".encode("utf-8")
    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
    return csv.encode("utf-8")

def download_button_for_df(df: pd.DataFrame, label: str, filename: str):
    b = make_csv_bytes(df)
    st.download_button(label=label, data=b, file_name=filename, mime="text/csv")

# -------------------------
# Operator mode quick area (visible if enabled)
# -------------------------
if op_mode:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Tryb Operatora — szybkie akcje")
    c1, c2, c3 = st.columns(3)
    if 'op_action' not in st.session_state:
        st.session_state.op_action = None

    with c1:
        if st.button("🔎 Skanuj"):
            st.session_state.op_action = "scan"
    with c2:
        if st.button("🛠️ Zgłoś usterkę"):
            st.session_state.op_action = "report"
    with c3:
        if st.button("📦 Pobierz część"):
            st.session_state.op_action = "parts"

    action = st.session_state.get("op_action", None)
    if action == "scan":
        assets = load_assets()
        if assets.empty:
            st.info("Brak zasobów.")
        else:
            sel = st.selectbox("Wybierz maszynę:", assets.apply(lambda r: f'{r["id"]} — {r["name"]}', axis=1).tolist())
            aid = sel.split(" — ")[0]
            a = safe_query_df("SELECT * FROM assets WHERE id = ?", (aid,))
            if not a.empty:
                a = a.iloc[0]
                st.markdown(f"**{a['id']} — {a['name']}**  \nStatus: **{a['status']}**  \nKrytyczność: **{a['criticality']}**")
                if st.button("🟩 Zatwierdź: SPRAWNE"):
                    with st.spinner("Zapisuję..."):
                        execute_write("INSERT INTO logs (asset_id,user_email,role,all_ok,comments) VALUES (?,?,?,?,?)", (aid, user_email, user_role, 1, "Szybki obchód"))
                    st.success("Zapisano ✅")
    elif action == "report":
        assets = load_assets()
        if assets.empty:
            st.info("Brak zasobów.")
        else:
            sel = st.selectbox("Zgłoś usterkę dla:", assets.apply(lambda r: f'{r["id"]} — {r["name"]}', axis=1).tolist())
            aid = sel.split(" — ")[0]
            desc = st.text_area("Opis (krótko):", max_chars=200)
            prio = st.selectbox("Priorytet:", ["Średnia", "Krytyczny"])
            if st.button("Wyślij zgłoszenie"):
                with st.spinner("Tworzę zgłoszenie..."):
                    execute_write("INSERT INTO reactive_maintenance (asset_id,description,status,priority,assigned_role) VALUES (?,?,?,?,?)", (aid, desc or "Brak opisu", "Nowe", prio, "Technik"))
                st.success("Zgłoszenie wysłane ✅")
    elif action == "parts":
        parts = load_parts()
        if parts.empty:
            st.info("Brak części.")
        else:
            sel = st.selectbox("Wybierz część:", parts.apply(lambda r: f'{r["id"]} — {r["name"]} ({r["stock"]})', axis=1).tolist())
            pid = sel.split(" — ")[0]
            qty = st.number_input("Ilość:", min_value=1, value=1)
            if st.button("Pobierz"):
                cur = safe_query_df("SELECT stock,name FROM parts WHERE id = ?", (pid,))
                if not cur.empty and cur.iloc[0]['stock'] >= qty:
                    with st.spinner("Aktualizuję magazyn..."):
                        execute_write("UPDATE parts SET stock = stock - ? WHERE id = ?", (qty, pid))
                        execute_write("INSERT INTO part_transactions (part_id,quantity,asset_id,user_email) VALUES (?,?,?,?)", (pid, qty, None, user_email))
                    st.success("Pobrano ✅")
                else:
                    st.error("Brak wystarczającej ilości.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# -------------------------
# NAV: Hala (assets) with search & pagination & CSV export
# -------------------------
if nav == "Hala":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🛠️ Zasoby — przegląd i wyszukiwanie")
    assets = load_assets()
    left, right = st.columns([3,1])
    with left:
        q = st.text_input("Szukaj po ID / nazwie / kodzie:", value="", placeholder="np. NH-SM-09 lub Mieszalnik")
    with right:
        if not assets.empty:
            download_button_for_df(assets, "📥 Eksportuj Assets (CSV)", "assets_export.csv")
    if assets.empty:
        st.info("Brak zasobów w bazie.")
    else:
        if q.strip():
            mask = assets.apply(lambda r: q.strip().lower() in str(r['id']).lower() or q.strip().lower() in str(r['name']).lower() or q.strip().lower() in str(r.get('code','')).lower(), axis=1)
            filtered = assets[mask]
        else:
            filtered = assets
        # Pagination (simple)
        if 'assets_page' not in st.session_state:
            st.session_state.assets_page = 0
        page_size = 6
        start = st.session_state.assets_page * page_size
        end = start + page_size
        for _, row in filtered.iloc[start:end].iterrows():
            low = row['status'] == 'Krytyczny' or row.get('criticality','') == 'Wysoka'
            st.markdown(f"**{row['id']} — {row['name']}**  \nKod: `{row.get('code','')}`  •  Status: **{row['status']}**")
            if low:
                st.warning("Wysoka krytyczność / Krytyczny status")
        if end < len(filtered):
            if st.button("Pokaż więcej"):
                st.session_state.assets_page += 1
        else:
            # reset page if search changed
            st.session_state.assets_page = 0
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# NAV: Kalibracje AKP
# -------------------------
if nav == "Kalibracje AKP":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## ⚖️ Kalibracje wag (AKP)")
    with st.form("akp_form_v2"):
        scale = st.selectbox("Wybierz wagę:", ["NH-MX-09 - Waga popiołu W", "NH-SM-03 - Waga popiołu", "NH-SM-05 - Waga cementu"])
        target = st.number_input("Zadana ilość (kg):", value=1000.0, step=100.0)
        actual = st.number_input("Rzeczywista ilość (kg):", value=1000.0, step=1.0)
        if st.form_submit_button("💾 Zapisz protokół"):
            err = ((actual - target) / target) * 100
            sid = scale.split(" - ")[0]
            with st.spinner("Zapisuję..."):
                execute_write("INSERT INTO logs (asset_id,user_email,role,all_ok,comments) VALUES (?,?,?,?,?)", (sid, user_email, user_role, 0 if abs(err)>2 else 1, f"Kalibracja: błąd {err:.2f}%"))
                if abs(err) > 2:
                    execute_write("INSERT INTO reactive_maintenance (asset_id,description,status,priority,assigned_role) VALUES (?,?,?,?,?)", (sid, f"Krytyczny dryf {err:.2f}%", "Nowe", "Krytyczny", "Technik AKP"))
                    execute_write("UPDATE assets SET status = 'Krytyczny' WHERE id = ?", (sid,))
                    st.error("KRYTYCZNY DRYF — zgłoszono RM")
                else:
                    execute_write("UPDATE assets SET status = 'Sprawny' WHERE id = ?", (sid,))
                    st.success("Protokół zapisany ✅")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# NAV: Magazyn WMS (parts) + CSV export + simple inline report button
# -------------------------
if nav == "Magazyn WMS":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📦 Magazyn części (WMS)")
    parts = load_parts()
    left, right = st.columns([3,1])
    with right:
        if not parts.empty:
            download_button_for_df(parts, "📥 Eksportuj Parts (CSV)", "parts_export.csv")
    if parts.empty:
        st.info("Brak części w magazynie.")
    else:
        for _, r in parts.iterrows():
            low = r['stock'] <= r['min_stock']
            st.markdown(f"**{r['name']}** — `{r['id']}`  \n📍 {r['location']}  •  Stan: **{r['stock']}**")
            if low:
                st.warning("Niski stan — rozważ zamówienie")
    st.markdown("---")
    with st.form("withdraw_v2"):
        pid = st.selectbox("Wybierz część:", parts['id'].tolist() if not parts.empty else ["PART-USZCZELKA-MIX"])
        qty = st.number_input("Ilość:", min_value=1, value=1)
        asset_choices = safe_query_df("SELECT id FROM assets")
        aid = st.selectbox("Dla maszyny:", asset_choices['id'].tolist() if not asset_choices.empty else ["NH-SM-09"])
        if st.form_submit_button("📦 Potwierdź pobranie"):
            cur = safe_query_df("SELECT stock,name FROM parts WHERE id = ?", (pid,))
            if not cur.empty and int(cur.iloc[0]['stock']) >= qty:
                with st.spinner("Aktualizuję stan..."):
                    execute_write("UPDATE parts SET stock = stock - ? WHERE id = ?", (qty, pid))
                    execute_write("INSERT INTO part_transactions (part_id,quantity,asset_id,user_email) VALUES (?,?,?,?)", (pid, qty, aid, user_email))
                st.success("Pobrano ✅")
            else:
                st.error("Brak wystarczającej ilości")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# NAV: Pulpit (single aggregated query + CSV export for RM)
# -------------------------
if nav == "Pulpit":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📊 Pulpit & KPI")
    # One-liners: aggregated counts
    agg = safe_query_df("""
        SELECT
          (SELECT COUNT(*) FROM assets) AS total_assets,
          (SELECT COUNT(*) FROM assets WHERE status='Krytyczny') AS critical_assets,
          (SELECT COUNT(*) FROM logs) AS total_logs,
          (SELECT COUNT(*) FROM reactive_maintenance) AS total_rm
    """)
    if not agg.empty:
        total = int(agg.iloc[0]['total_assets'])
        critical = int(agg.iloc[0]['critical_assets'])
        logs = int(agg.iloc[0]['total_logs'])
        rms = int(agg.iloc[0]['total_rm'])
    else:
        total = critical = logs = rms = 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Park maszynowy", f"{total}")
    c2.metric("PPM (razem)", f"{logs}")
    c3.metric("Aktywne RM", f"{rms}")
    c4.metric("Krytyczne", f"{critical}")
    st.markdown("---")
    rm_df = safe_query_df("SELECT id, asset_id, description, priority, status, created_at FROM reactive_maintenance ORDER BY id DESC")
    if rm_df.empty:
        st.info("Brak aktywnych zgłoszeń RM.")
    else:
        download_button_for_df(rm_df, "📥 Eksportuj RM (CSV)", "rm_export.csv")
        st.markdown("### Bieżące zgłoszenia")
        for _, r in rm_df.head(10).iterrows():
            st.markdown(f"**RM-{r['id']}** | `{r['asset_id']}` | Priorytet: **{r['priority']}**  \n{r['description']}")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# NAV: Raporty (CSV export + email placeholder)
# -------------------------
if nav == "Raporty":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📄 Raporty — eksport i wysyłka (symulacja)")
    st.markdown("Możesz wygenerować CSV z danych i (symulacyjnie) wysłać raport e‑mailem.")
    report_type = st.selectbox("Typ raportu:", ["Assets snapshot", "Parts snapshot", "RM snapshot"])
    if st.button("Generuj CSV raportu"):
        if report_type == "Assets snapshot":
            df = load_assets()
            b = make_csv_bytes(df)
            st.download_button("📥 Pobierz CSV", b, file_name="assets_report.csv", mime="text/csv")
        elif report_type == "Parts snapshot":
            df = load_parts()
            b = make_csv_bytes(df)
            st.download_button("📥 Pobierz CSV", b, file_name="parts_report.csv", mime="text/csv")
        else:
            df = safe_query_df("SELECT * FROM reactive_maintenance")
            b = make_csv_bytes(df)
            st.download_button("📥 Pobierz CSV", b, file_name="rm_report.csv", mime="text/csv")
    st.markdown("---")
    st.markdown("### Wyślij raport e‑mailem (symulacja)")
    with st.form("email_report"):
        to_addr = st.text_input("Do (adres e‑mail):", value="manager@holcim.com")
        subj = st.text_input("Temat:", value=f"Raport CMMS — {datetime.date.today().isoformat()}")
        msg = st.text_area("Wiadomość (opcjonalnie):", value="Proszę znaleźć załączony raport (symulacja).", max_chars=1000)
        if st.form_submit_button("Wyślij e‑mail (symulacja)"):
            # record the simulated send in logs table as an audit trail
            with st.spinner("Rejestruję wysyłkę..."):
                execute_write("INSERT INTO logs (asset_id,user_email,role,all_ok,comments) VALUES (?,?,?,?,?)", (None, user_email, user_role, 1, f"E‑mail: '{subj}' -> {to_addr}"))
            st.success(f"Symulacja wysyłki e‑mail: {to_addr} (zarejestrowano) ✅")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# NAV: Analizy AI (Pareto) — improved grouping, CSV export
# -------------------------
if nav == "Analizy AI":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🤖 Analizy & Pareto")
    rm_df = safe_query_df("SELECT description FROM reactive_maintenance")
    if not rm_df.empty:
        def categorize(desc: str) -> str:
            d = (desc or "").lower()
            if any(k in d for k in ["ev", "elektrozaw", "pneum", "pneumaty"]): return "Pneumatyka (Elektrozawory)"
            if any(k in d for k in ["uszcze", "łożysk", "łożysko", "łożyska", "mechan"]): return "Mechanika (Łożyska/Uszczelki)"
            if any(k in d for k in ["waga", "tensometr", "dryf"]): return "AKP (Dryf wag)"
            return "Elektryka / Inne"
        rm_df['category'] = rm_df['description'].apply(categorize)
        pareto = rm_df['category'].value_counts().rename_axis('Przyczyna').reset_index(name='Ilość')
        download_button_for_df(pareto, "📥 Eksportuj Analizę (CSV)", "pareto_export.csv")
        st.bar_chart(pareto.set_index('Przyczyna')['Ilość'])
    else:
        demo = pd.DataFrame({'Przyczyna': ['Pneumatyka','Mechanika','AKP','Elektryka'], 'Ilość':[45,25,15,8]})
        download_button_for_df(demo, "📥 Eksportuj Demo (CSV)", "pareto_demo.csv")
        st.bar_chart(demo.set_index('Przyczyna')['Ilość'])
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Footer
# -------------------------
st.markdown("</div>", unsafe_allow_html=True)
st.markdown(f"<div class='small-muted' style='margin-top:12px'>Kolory firmowe: Holcim orange {PRIMARY} • accent {ACCENT}. Jeśli chcesz, dodam AG‑Grid lub prawdziwą wysyłkę e‑mail (SMTP) — daj znać.</div>", unsafe_allow_html=True)
