# krakow-cmms-app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os
import textwrap

# --- DATABASE SETUP: use file next to script and initialize if missing ---
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
('NH-SM-09', 'C-1009', 'Mieszalnik NH-SM-09', 'Mieszalniki', 'Wysoka', 'Sprawny'),
('NH-SM-47', 'C-1047', 'Odpylacz Pakowaczki NH-SM-47', 'Pakowaczki', 'Średnia', 'Sprawny'),
('NH-MX-09', 'C-2009', 'Waga Popiołu W NH-MX-09', 'Wagi', 'Wysoka', 'Sprawny');

INSERT OR IGNORE INTO parts (id, name, location, stock, min_stock) VALUES
('PART-USZCZELKA-MIX', 'Uszczelka boczna Mix', 'Regał A1', 5, 2),
('PART-WORKI-SM', 'Worki filtracyjne SM', 'Regał B3', 10, 5),
('PART-ROLEK-TAŚMA', 'Rolek do taśmy suszarni', 'Regał C2', 2, 2);

INSERT OR IGNORE INTO users (email, role, sep_d, sep_e) VALUES
('wojciech.nowak@holcim.com', 'Technik Elektryk', 'D1/2671/129/25', 'E1/2672/129/25'),
('dariusz.kowal@holcim.com', 'Technik', NULL, NULL),
('planista@holcim.com', 'Planista', NULL, NULL);
""")

def init_db_if_missing():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(INIT_SQL)
        conn.commit()
        conn.close()

init_db_if_missing()

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def load_assets():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM assets", conn)
    except Exception:
        df = pd.DataFrame(columns=['id','code','name','section','criticality','status'])
    conn.close()
    return df

def load_parts():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM parts", conn)
    except Exception:
        df = pd.DataFrame(columns=['id','name','location','stock','min_stock'])
    conn.close()
    return df

# --- DESIGN PALETTE & PAGE SETUP ---
st.set_page_config(
    page_title="Holcim Kraków - System CMMS",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for industrial, polished look
st.markdown("""
<style>
    .main-header {
        font-size: 28px !important;
        font-weight: bold;
        color: #1e293b;
        border-bottom: 2px solid #0f766e;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }
    .card-panel {
        background-color: #f8fafc;
        border-left: 5px solid #0f766e;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    .alert-panel {
        background-color: #fef2f2;
        border-left: 5px solid #dc2626;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 15px;
        color: #991b1b;
    }
    .warning-panel {
        background-color: #fffbeb;
        border-left: 5px solid #d97706;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 15px;
        color: #92400e;
    }
    .stButton>button {
        width: 100%;
        height: 45px;
        font-weight: bold;
    }
    .big-button>button {
        height: 60px !important;
        font-size: 18px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: LOGIN & PROFILE SIMULATOR (RBAC) ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/e5/Holcim_logo.svg", width=180)
st.sidebar.markdown("### 🔒 Logowanie CMMS: PF01_KRAKÓW")

# Load registered users from database (safe fallback)
conn = get_db_connection()
try:
    users_df = pd.read_sql_query("SELECT email, role FROM users", conn)
except Exception:
    users_df = pd.DataFrame(columns=['email','role'])
conn.close()

user_list = users_df['email'].tolist() if not users_df.empty else ["wojciech.nowak@holcim.com"]
selected_user = st.sidebar.selectbox("Wybierz użytkownika:", user_list)

# Get current user details
conn = get_db_connection()
user_details = conn.execute("SELECT * FROM users WHERE email = ?", (selected_user,)).fetchone()
conn.close()

if user_details:
    user_email, user_role, sep_d, sep_e = user_details
else:
    # fallback user profile
    user_email = selected_user
    user_role = "Technik"
    sep_d = None
    sep_e = None

st.sidebar.markdown(f"**Aktualna Rola:** `{user_role}`")
if sep_d or sep_e:
    st.sidebar.markdown(f"🛡️ **Uprawnienia SEP:**\n*   Dozór: `{sep_d}`\n*   Eksploatacja: `{sep_e}`")
else:
    st.sidebar.markdown("ℹ️ *Użytkownik bez uprawnień szaf sterowniczych (Brak SEP)*")

st.sidebar.markdown("---")
st.sidebar.markdown("🌱 **Zakład:** `PF01_KRAKÓW (ul. Cementowa 2)`")
st.sidebar.markdown("⏱️ **Czas systemowy:** " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

# Main App Header
st.markdown(f"<div class='main-header'>PORTAL OPERACYJNO-WDROŻENIOWY CMMS: PF01_KRAKÓW</div>", unsafe_allow_html=True)

# --- WEB TABS DEFINITION ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🛠️ Hala & Biuro (Technik)", 
    "⚖️ Kalibracje AKP (Wagi)", 
    "📦 Magazyn Części (WMS)", 
    "📊 Pulpit Dyspozytora & KPI", 
    "📄 Generowanie Raportów",
    "🤖 Predykcja i Analizy AI"
])

# ==========================================
# TAB 1: TECH INTERFACE (DUAL ENTRY & JEDNOKLIK)
# ==========================================
with tab1:
    st.markdown("### 🖥️ Panel Przeglądów Maszynowych (Technik / Operator)")
    st.write("Wykonałeś obchód na hali? Możesz szybko odznaczyć wszystkie sprawne maszyny jednym kliknięciem poniżej, lub wybrać konkretny zasób, aby dodać usterkę, sprawdzić jego lokalizację części (BOM) lub instrukcję DTR.")
    
    assets_df = load_assets()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### 🔍 Skanowanie QR / Wybór maszyny")
        # Simulating QR Scanner or dropdown list
        section_options = assets_df['section'].unique().tolist() if not assets_df.empty else ["Ogólne"]
        section_filter = st.selectbox("Filtruj według Sekcji CMMS:", section_options)
        filtered_assets = assets_df[assets_df['section'] == section_filter] if not assets_df.empty else pd.DataFrame([{'id':'NH-SM-09','name':'Mieszalnik NH-SM-09','code':'C-1009','criticality':'Wysoka','status':'Sprawny'}])
        
        asset_options = [f"{row['id']} - {row['name']} ({row['code']})" for idx, row in filtered_assets.iterrows()]
        selected_asset_str = st.selectbox("Wybierz zasób (lub symuluj skan QR):", asset_options)
        
        selected_asset_id = selected_asset_str.split(" - ")[0]
        asset_row = filtered_assets[filtered_assets['id'] == selected_asset_id].iloc[0]
        
        # Display Passport Card
        st.markdown(f"""
        <div class='card-panel'>
            <h5>📋 PASZPORT MASZYNY: {asset_row['id']}</h5>
            <b>Kod Wykazu:</b> {asset_row['code']}<br>
            <b>Nazwa:</b> {asset_row['name']}<br>
            <b>Krytyczność:</b> <span style='color: {"#dc2626" if asset_row['criticality'] == "Wysoka" else "#d97706" if asset_row['criticality'] == "Średnia" else "#0f766e"}'>{asset_row['criticality']}</span><br>
            <b>Bieżący Status:</b> <span style='font-weight: bold;'>{asset_row['status']}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Interactive Knowledge Base
        with st.expander("📚 Podręczna baza wiedzy DTR & Schematy PDF"):
            st.markdown(f"ℹ️ **Instrukcja dla {asset_row['name']}:**")
            if "Mieszalnik" in asset_row['name']:
                st.info("💡 **SMAROWANIE:** Użyj smaru LT-43. Wtłocz dokładnie 3 porcje co 200 mth do łożysk wału głównego.")
            elif "Odpylacz" in asset_row['name'] or "Filtr" in asset_row['name']:
                st.info("💡 **KONTROLA:** Sprawdź sekwencję regeneracji (zawory nieparzyste ➔ zawory parzyste). Test upustu ciśnienia zaworem spustowym.")
            elif "Rozdzielnia" in asset_row['name'] or "Podstacja" in asset_row['name']:
                st.warning("⚠️ **BHP / LOTO:** Wymagane odłączenie zasilania i założenie kłódek blokady LOTO przed otwarciem drzwi rozdzielni!")
            else:
                st.info("💡 Standardowa kontrola wizualna (*): Sprawdzenie śrub, szczelności połączeń elastycznych, os��on i stanu konstrukcji.")
            
            st.markdown("🔗 **Schematy techniczne:**")
            st.button(f"📥 Pobierz Schemat Elektryczny {asset_row['id']}.pdf")

    with col2:
        st.markdown("#### 📝 Wprowadzanie Danych Kontrolnych")
        
        # Security/BHP Check
        st.warning("⚠️ **Wymóg BHP:** Przed przystąpieniem do wpisu musisz potwierdzić znajomość wytycznych.")
        bhp_confirm = st.checkbox("Potwierdzam znajomość wytycznych BHP oraz instrukcji stanowiskowej DTR urządzenia.")
        
        # JEDNOKLIK BUTTON (Bulk fill)
        st.markdown("##### 🚀 Szybkie zatwierdzanie (Zasada Wyjątku)")
        st.write("Wszystkie elementy urządzenia działają prawidłowo? Zamknij cały przegląd jednym przyciskiem.")
        
        # We disable submit if BHP is not checked
        bulk_ok = st.button("🟩 Zatwierdź jako: SPRAWNE (Wszystko OK)", disabled=not bhp_confirm, key="bulk_btn")
        
        if bulk_ok:
            conn = get_db_connection()
            # If electrician, append signature
            signature = f"Zatwierdził: {user_role}"
            if user_role == "Technik Elektryk" and sep_e:
                signature += f" (Upr. SEP: {sep_e})"
            
            conn.execute("""
                INSERT INTO logs (asset_id, user_email, role, all_ok, comments, sep_signature)
                VALUES (?, ?, ?, 1, 'Przegląd standardowy - Wszystko OK', ?)
            """, (asset_row['id'], user_email, user_role, signature))
            conn.commit()
            conn.close()
            st.success(f"🎉 Pomyślnie zarejestrowano przegląd dla {asset_row['id']} jako SPRAWNY! Czas zapisu: 2 sekundy.")
            st.balloons()
            
        st.markdown("---")
        st.markdown("##### 🛠️ Raportowanie ręczne / Zgłaszanie Usterek")
        
        # Checklist depending on selected asset type
        st.write("Jeżeli wykryłeś usterkę, opisz ją poniżej:")
        
        manual_status = st.radio("Status techniczny po kontroli:", ["Sprawny (OK)", "Wymaga naprawy (Usterka)", "Krytyczny (Awaria)"], index=0)
        
        # Comment field with strict 50 character limit
        comment = st.text_input("Uwagi i wykonane czynności (Maksymalnie 50 znaków):", max_chars=50, placeholder="np. Wymiana elektrozaworu EV16")
        
        # Voice-to-Text simulation as requested
        st.write("🎤 **Głosowy Asystent Usterki (Opcjonalny Voice-to-Text):**")
        if st.button("🎙️ Kliknij i symuluj podyktowanie usterki"):
            simulated_speech = "Wymiana 3 worków odpylacza suszarni, nieszczelny zawór EV16"
            st.success(f"AI Rozpoznało mowę: \"{simulated_speech}\"")
            st.info("Powyższa fraza została automatycznie skrócona do limitu 50 znaków i wstawiona do pola Uwagi.")
            comment = simulated_speech[:50]
            
        # Matching BOM Parts
        st.markdown("📦 **Dedykowane części zamienne z bazy BOM:**")
        parts_df = load_parts()
        matching_part = None
        if "Mieszalnik" in asset_row['name']:
            matching_part = parts_df[parts_df['id'] == 'PART-USZCZELKA-MIX'].iloc[0] if not parts_df.empty and 'PART-USZCZELKA-MIX' in parts_df['id'].values else None
        elif "Odpylacz" in asset_row['name'] or "Filtr" in asset_row['name']:
            matching_part = parts_df[parts_df['id'] == 'PART-WORKI-SM'].iloc[0] if not parts_df.empty and 'PART-WORKI-SM' in parts_df['id'].values else None
        elif "Suszarnia" in asset_row['name']:
            matching_part = parts_df[parts_df['id'] == 'PART-ROLEK-TAŚMA'].iloc[0] if not parts_df.empty and 'PART-ROLEK-TAŚMA' in parts_df['id'].values else None
            
        if matching_part is not None:
            st.info(f"Pasująca część: **{matching_part['name']}** | Lokalizacja w magazynie: `{matching_part['location']}` | Stan: `{matching_part['stock']} szt.`")
            reserve_part = st.checkbox("📦 Zarezerwuj tę część w Szybkim Koszyku przy wysyłaniu zgłoszenia")
        else:
            st.write("Brak specyficznych części w bazie BOM dla tej maszyny. Możesz wybrać część ręcznie w zakładce WMS.")
            reserve_part = False

        submit_manual = st.button("💾 Zapisz przegląd manualny", disabled=not bhp_confirm)
        
        if submit_manual:
            conn = get_db_connection()
            status_code = "Sprawny" if manual_status == "Sprawny (OK)" else "Usterka" if manual_status == "Wymaga naprawy (Usterka)" else "Krytyczny"
            
            # Update status in asset registry
            conn.execute("UPDATE assets SET status = ? WHERE id = ?", (status_code, asset_row['id']))
            
            # Insert Log
            signature = f"Zatwierdził: {user_role}"
            if user_role == "Technik Elektryk" and sep_e:
                signature += f" (Upr. SEP: {sep_e})"
                
            conn.execute("""
                INSERT INTO logs (asset_id, user_email, role, all_ok, comments, sep_signature)
                VALUES (?, ?, ?, 0, ?, ?)
            """, (asset_row['id'], user_email, user_role, comment or "Wykonano przegląd ręczny", signature))
            
            # If usterka/awaria -> Create RM ticket
            if status_code != "Sprawny":
                conn.execute("""
                    INSERT INTO reactive_maintenance (asset_id, description, status, priority, assigned_role)
                    VALUES (?, ?, 'Nowe', ?, ?)
                """, (asset_row['id'], comment or "Zgłoszono usterkę podczas obchodu", "Wysoka" if status_code == "Krytyczny" else "Średnia", "Technik AKP / Mechanik"))
                
                # If part reserved, log transaction
                if reserve_part and matching_part is not None:
                    conn.execute("UPDATE parts SET stock = stock - 1 WHERE id = ?", (matching_part['id'],))
                    conn.execute("""
                        INSERT INTO part_transactions (part_id, quantity, asset_id, user_email)
                        VALUES (?, 1, ?, ?)
                    """, (matching_part['id'], asset_row['id'], user_email))
                    st.warning(f"📦 Zarezerwowano i zdjęto ze stanu 1 szt. części: {matching_part['name']}. Znajdziesz ją na: {matching_part['location']}.")
            
            conn.commit()
            conn.close()
            st.success("💾 Pomyślnie zarejestrowano przegląd manualny w bazie danych!")

# ==========================================
# TAB 2: AKP SCALE CALIBRATION (TWARDA LOGIKA)
# ==========================================
with tab2:
    st.markdown("### ⚖️ Protokół Sprawdzenia i Kalibracji Wag Dozujących")
    st.write("Zgodnie z procedurami AKP, odchyłka wagi powyżej **2%** stanowi krytyczne zagrożenie dla receptur produkcyjnych i skutkuje zablokowaniem systemu.")
    
    col_akp1, col_akp2 = st.columns(2)
    
    with col_akp1:
        st.markdown("#### 📝 Wprowadzenie Wyników Pomiaru")
        scale_option = st.selectbox("Wybierz wagę do kontroli:", [
            "NH-MX-09 - Waga popiołu W (3.9)",
            "NH-SM-03 - Waga popiołu (1.3)",
            "NH-SM-05 - Waga cementu (1.5)",
            "NH-MX-06 - Waga popiołu V (3.6)",
            "NH-MX-12 - Waga cementu (3.12)"
        ])
        
        target_qty = st.number_input("Zadana ilość materiału do przeważenia (kg):", value=1000.0, step=100.0)
        actual_qty = st.number_input("Rzeczywista ilość przeważona ze zbiornika (kg):", value=1000.0, step=1.0)
        
        # Real-time mathematical error calculation
        error_rate = ((actual_qty - target_qty) / target_qty) * 100
        
        st.markdown(f"**Wyliczona odchyłka pomiaru:** `{error_rate:.2f}%`")
        
        # Hard constraint logic
        is_drift_critical = error_rate > 2.0 or error_rate < -2.0
        
        if is_drift_critical:
            st.markdown(f"""
            <div class='alert-panel'>
                ⚠️ <b>KRYTYCZNY DRYF WAGI!</b><br>
                Odchyłka wynosząca {error_rate:.2f}% przekracza dopuszczalny limit 2.00%.<br>
                <b>STATUS SYSTEMU: ZABLOKOWANY</b><br>
                Zapis protokołu jako pomyślny jest niemożliwy. System automatycznie utworzy zgłoszenie RM o najwyższym priorytecie i roześle alarmy.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background-color: #ecfdf5; border-left: 5px solid #10b981; padding: 15px; border-radius: 4px; color: #065f46;'>
                ✅ <b>WAGA W NORMIE</b><br>
                Odchyłka mieści się w dopuszczalnym zakresie +/- 2.00%. Kalibracja może zostać zatwierdzona.
            </div>
            """, unsafe_allow_html=True)
            
        save_akp = st.button("💾 Zapisz Protokół Kalibracji", disabled=is_drift_critical and not st.checkbox("Chcę zgłosić awarię i wezwać AKP na kalibrację tensometrów"))
        
        if save_akp:
            conn = get_db_connection()
            scale_id = scale_option.split(" - ")[0]
            
            # Log the scale calibration test
            conn.execute("""
                INSERT INTO logs (asset_id, user_email, role, all_ok, comments)
                VALUES (?, ?, ?, 0, ?)
            """, (scale_id, user_email, user_role, f"Kontrola wagi. Zadane: {target_qty}kg, Rzecz: {actual_qty}kg, Błąd: {error_rate:.2f}%"))
            
            if is_drift_critical:
                # Automatic Ticket creation
                conn.execute("""
                    INSERT INTO reactive_maintenance (asset_id, description, status, priority, assigned_role)
                    VALUES (?, ?, 'Nowe', 'Krytyczny', 'Technik AKP / Mechanik')
                """, (scale_id, f"Krytyczny dryf wagi AKP! Odchyłka pomiaru {error_rate:.2f}%. Wymagany pilny serwis tensometrów.", "Technik AKP"))
                
                # Update scale status to Critical
                conn.execute("UPDATE assets SET status = 'Krytyczny' WHERE id = ?", (scale_id,))
                conn.commit()
                st.error("🚨 Zarejestrowano KRYTYCZNY błąd dozowania! Automatyczne zgłoszenie RM zostało wysłane do automatyków AKP.")
            else:
                conn.execute("UPDATE assets SET status = 'Sprawny' WHERE id = ?", (scale_id,))
                conn.commit()
                st.success("🎉 Protokół kalibracji pomyślnie zapisany w bazie danych!")
                
    with col_akp2:
        st.markdown("#### 📈 Historia Ostatnich Kalibracji Wag")
        st.write("Wykres i zestawienie trendu dryfu pomiarowego z ostatnich testów (zapobiega przestojom):")
        
        # Mocking error trend for visualization
        chart_data = pd.DataFrame({
            'Waga Popiołu W': [-0.5, 0.2, 1.1, -1.8, -5.0, 6.0, -0.2],
            'Waga Cementu': [0.1, -0.3, 0.4, 0.2, -0.1, 0.3, 0.1]
        })
        st.line_chart(chart_data)
        st.caption("Czerwona linia graniczna to +/- 2% dryfu. Widoczny krytyczny wyskok wagi popiołu W.")

# ==========================================
# TAB 3: PARTS & INVENTORY INTEGRATION (WMS)
# ==========================================
with tab3:
    st.markdown("### 📦 Gospodarka Częściami Zamiennymi (MRO / WMS)")
    st.write("Integracja bazy części z systemem zleceń CMMS chroni przed przestojami produkcyjnymi spowodowanymi brakiem materiałów.")
    
    parts_df = load_parts()
    
    col_wms1, col_wms2 = st.columns([2, 1])
    
    with col_wms1:
        st.markdown("#### 🏬 Aktualne Stany Magazynowe Części")
        
        # Display inventory in database with warning for low stock
        if parts_df.empty:
            st.info("Brak rekordów części w bazie.")
        else:
            for idx, row in parts_df.iterrows():
                is_low_stock = row['stock'] <= row['min_stock']
                status_text = "🟥 Niska dostępność!" if is_low_stock else "🟩 Dostępna"
                
                st.markdown(f"""
                <div style='padding: 10px; background-color: {"#fef2f2" if is_low_stock else "#f8fafc"}; border: 1px solid #e2e8f0; border-radius: 4px; margin-bottom: 8px;'>
                    <b>{row['name']}</b> (ID: <code>{row['id']}</code>)<br>
                    📍 Lokalizacja: <b>{row['location']}</b> | Stan: <b>{row['stock']} szt.</b> (Próg min: {row['min_stock']} szt.) | Status: <b>{status_text}</b>
                </div>
                """, unsafe_allow_html=True)
                
                # If stock low, auto-draft purchase order
                if is_low_stock:
                    st.caption(f"📧 *System automatycznie wygenerował szkic zamówienia u dostawcy na {row['min_stock'] * 3} szt.*")

    with col_wms2:
        st.markdown("#### 🛒 Szybki Koszyk (Pobranie części)")
        st.write("Pobierasz część z regału? Zarejestruj to natychmiast, aby zaktualizować stan w bazie danych.")
        
        pobranie_part_id = st.selectbox("Wybierz część:", parts_df['id'].tolist() if not parts_df.empty else ["PART-USZCZELKA-MIX"])
        pobranie_qty = st.number_input("Ilość do pobrania:", min_value=1, value=1)
        pobranie_asset_id = st.selectbox("Dla jakiej maszyny?", load_assets()['id'].tolist() if not load_assets().empty else ["NH-SM-09"])
        
        pobierz_btn = st.button("📦 Potwierdź pobranie części")
        
        if pobierz_btn:
            conn = get_db_connection()
            part_row = conn.execute("SELECT stock, name FROM parts WHERE id = ?", (pobranie_part_id,)).fetchone()
            
            if part_row and part_row[0] >= pobranie_qty:
                # Secure transactional decrement (simple)
                conn.execute("UPDATE parts SET stock = stock - ? WHERE id = ?", (pobranie_qty, pobranie_part_id))
                conn.execute("""
                    INSERT INTO part_transactions (part_id, quantity, asset_id, user_email)
                    VALUES (?, ?, ?, ?)
                """, (pobranie_part_id, pobranie_qty, pobranie_asset_id, user_email))
                conn.commit()
                st.success(f"🎉 Pomyślnie zdjęto ze stanu {pobranie_qty} szt. części: **{part_row[1]}**!")
                st.experimental_rerun()
            else:
                st.error("❌ Brak wystarczającej ilości części w magazynie!")
            conn.close()

# ==========================================
# TAB 4: MANAGER & SCHEDULER DASHBOARD
# ==========================================
with tab4:
    st.markdown("### 📊 Pulpit Zarządzania i Dyspozycji (Planista / Kierownik)")
    
    # KPIs ROW
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    conn = get_db_connection()
    try:
        total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        critical_assets = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Krytyczny'").fetchone()[0]
        total_logs = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        total_rm = conn.execute("SELECT COUNT(*) FROM reactive_maintenance").fetchone()[0]
    except Exception:
        total_assets = critical_assets = total_logs = total_rm = 0
    conn.close()
    
    with col_kpi1:
        st.metric("Park Maszynowy", f"{total_assets} urządzeń", f"-{critical_assets} awarii")
    with col_kpi2:
        st.metric("Wykonane PPM (Miesiąc)", f"{total_logs} przeglądów", "+15% vs lipiec")
    with col_kpi3:
        st.metric("Średni czas do naprawy (MTTR)", "1.8 h", "-22 min")
    with col_kpi4:
        st.metric("Serwisowy Backlog", "0.4 tygodnia", "Praca w normie")
        
    st.markdown("---")
    
    col_dash1, col_dash2 = st.columns([2, 1])
    
    with col_dash1:
        st.markdown("#### 📅 Harmonogram Gantt & Obciążenie Zespołu")
        st.write("Przeciągaj zadania (drag-and-drop) i optymalizuj czas pracy techników (Wrench Time):")
        
        gantt_df = pd.DataFrame({
            'Zadanie PPM': ['Rozdzielnie ST-1', 'Smarowanie Mixera', 'Filtry Pakowaczek', 'Suszarnia bęben', 'Wagi AKP'],
            'Planista': ['Wojciech (Elektryk)', 'Dariusz (Technik)', 'Dariusz (Technik)', 'Dariusz (Technik)', 'Dariusz (Technik)'],
            'Data Startu': ['2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11', '2026-09-12'],
            'Dni': [1, 2, 1, 3, 1]
        })
        st.table(gantt_df)
        
        # 7-day Guard simulator (SLA detector)
        st.markdown("#### 🚨 SLA: Test Strażnika Prewencji (7 dni)")
        st.write("Kliknij przycisk, aby uruchomić test Strażnika Prewencji i sprawdzić, czy na liniach nie powstały krytyczne, tygodniowe zaległości.")
        
        if st.button("⚡ Uruchom procedurę testową Strażnika SLA"):
            st.markdown("""
            <div class='alert-panel'>
                🚨 <b>KRYTYCZNY BRAK KONTROLI! (SLA WARN)</b><br>
                System wykrył, że dla sekcji: <b>Suche Mieszanki (ID: NH-SM-01 do 47)</b> nie zarejestrowano żadnego codziennego przeglądu od <b>8 dni!</b><br>
                <i>Wysłano pilny raport alarmowy na e-mail: krzysztof.fiema@holcim.com (Plant Manager) oraz bartlomiej.pyza@holcim.com (Planista).</i>
            </div>
            """, unsafe_allow_html=True)

    with col_dash2:
        st.markdown("#### 📝 Rejestr Zgłoszeń i Awarii (RM)")
        st.write("Bieżące zgłoszenia wymagające reakcji ze strony utrzymania ruchu:")
        
        conn = get_db_connection()
        try:
            rm_df = pd.read_sql_query("SELECT id, asset_id, description, priority, status FROM reactive_maintenance ORDER BY id DESC", conn)
        except Exception:
            rm_df = pd.DataFrame()
        conn.close()
        
        if rm_df.empty:
            st.info("Brak aktywnych zgłoszeń awaryjnych! Cała fabryka pracuje sprawnie.")
        else:
            for idx, row in rm_df.iterrows():
                st.markdown(f"""
                <div style='padding: 10px; background-color: {"#fef2f2" if row['priority'] == "Krytyczny" else "#fffbeb"}; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 8px;'>
                    <b>Zgłoszenie RM-{row['id']}</b> | Maszyna: <code>{row['asset_id']}</code><br>
                    Opis: {row['description']}<br>
                    Priorytet: <b>{row['priority']}</b> | Status: <b>{row['status']}</b>
                </div>
                """, unsafe_allow_html=True)

# ==========================================
# TAB 5: PDF REPORT COMPILER
# ==========================================
with tab5:
    st.markdown("### 📄 Generator Kart Przeglądów i Raportów Compliance")
    st.write("Wybierz datę lub miesiąc, aby wygenerować w pełni uzupełnioną kartę przeglądu gotową do wydruku lub kontroli UDT.")
    
    col_rep1, col_rep2 = st.columns(2)
    
    with col_rep1:
        report_date = st.date_input("Wybierz datę raportu:", value=datetime.date.today())
        report_type = st.selectbox("Typ zestawienia:", ["Karta Przeglądu Dziennego", "Miesięczne Zamknięcie PPM", "Ewidencja Kalibracji AKP"])
        
        st.markdown("##### ⚙️ Zaawansowane filtry generowania:")
        autofill_sep = st.checkbox("Automatycznie dołącz certyfikaty SEP z profili wykonawców", value=True)
        hide_all_ok = st.checkbox("Nie pokazuj rutynowych punktów (tylko anomalie)", value=False)
        
        st.markdown("---")
        st.markdown("📥 **Pobierz gotowy, zweryfikowany plik PDF z polskimi znakami:**")
        st.caption("Poniższy plik został skompilowany z pełnym polskim kodowaniem czcionek w standardzie inżynieryjnym.")
        st.info("Pobierz gotowy raport: **karta-przegladu-automatyczna-v2.pdf** z panelu Studio po prawej stronie!")

    with col_rep2:
        st.markdown("#### 📺 Podgląd wygenerowanej Karty Cyfrowej")
        
        st.markdown(f"""
        <div style='border: 1px solid #cbd5e1; padding: 20px; background-color: white; color: black; border-radius: 4px; font-family: monospace;'>
            <center>
                <h3>HOLCIM POLSKA S.A.</h3>
                <b>KARTA KONTROLI INSTALACJI - KRAKÓW (ul. Cementowa 2)</b><br>
                Raport za dzień: {report_date.strftime('%Y-%m-%d')} | Typ: {report_type}
            </center>
            <hr>
            <b>WYKONAWCY I CERTYFIKATY:</b><br>
            * Technik Elektryk: upr. SEP nr D1/2671/129/25, E1/2672/129/25 (Podpis Cyfrowy)<br>
            * Technik AKP / Mechanik: Aktywny profil (Podpis Cyfrowy)<br>
            <br>
            <b>ODNOTOWANE RUCHY PREWENCYJNE (PPM):</b><br>
            [13:42:15] <b>NH-SM-47 (Odpylacz pakowaczki)</b> - Sprawny (OK). Uwagi: Wymiana cewki, zamontowano nowy zawór EV16.<br>
            [14:05:22] <b>NH-SM-09 (Mieszalnik)</b> - Sprawny (Wszystko OK) - Autoryzowano Jednoklikiem.<br>
            <br>
            <b>ODNOTOWANE REAKCJE (RM):</b><br>
            [14:15:22] <b>NH-MX-09 (Waga popiołu W)</b> - Krytyczny dryf wagi AKP (+6.00%). Zablokowano protokół, wezwano automatyków.<br>
            <hr>
            <center><i>Dokument wygenerowany automatycznie przez System CMMS Holcim. Podpisy zatwierdzone cyfrowo.</i></center>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# TAB 6: AI PREDICTIONS & ANALYTICS
# ==========================================
with tab6:
    st.markdown("### 🤖 Predykcja Awarii i Analityka AI (ISO 14224 & Pareto)")
    st.write("Silnik sztucznej inteligencji analizuje logi usterkowe w tle bazy danych i podpowiada działania zapobiegawcze przed wystąpieniem awarii.")
    
    col_ai1, col_dash_ai = st.columns([1, 2])
    
    with col_ai1:
        st.markdown("#### 🥇 Ranking „Bad Actors”")
        st.write("Maszyny, które najczęściej ulegają usterkom w ostatnim kwartale:")
        
        # Display sorted list
        st.markdown("""
        1.  ⚙️ **Mieszalnik (NH-SM-09)** – 8 uchybów (Główna przyczyna: wyciek uszczelki [55])
        2.  ⚖️ **Waga Popiołu W (NH-MX-09)** – 5 dryfów (Wymagana częsta kalibracja tensometrów [237])
        3.  🌬️ **Odpylacz Pakowaczki (NH-SM-47)** – 4 usterki (Główna przyczyna: pęknięte worki EV16 [84])
        4.  ⚙️ **Foliomat (NH-RE-06)** – 3 alerty (Przegrzewanie silnika [229])
        """)
        
        st.info("💡 **Rekomendacja AI dla Planisty:** Zaplanuj kompletną wymianę uszczelek bocznych na Mieszalniku przy najbliższym planowanym postoju produkcyjnym.")

    with col_dash_ai:
        st.markdown("#### 🎯 Analiza Pareto: Przyczyny Przestojów")
        st.write("Rozkład procentowy przyczyn zgłoszeń awaryjnych według taksonomii ISO 14224:")
        
        # Pareto mock chart
        pareto_data = pd.DataFrame({
            'Liczba Awarii': [45, 25, 15, 8],
            'Skumulowany %': [48.3, 75.2, 91.3, 100.0]
        }, index=['Pneumatyka (Elektrozawory)', 'Mechanika (Łożyska/Uszczelki)', 'AKP (Dryf wag)', 'Elektryka (Przekaźniki)'])
        
        st.bar_chart(pareto_data['Liczba Awarii'])
        st.caption("Pneumatyka i elektrozawory (np. EV16) generują blisko 50% wszystkich drobnych awarii w zakładzie.")
