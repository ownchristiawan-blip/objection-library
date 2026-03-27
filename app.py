# ======================
# IMPORT LIBRARIES
# ======================
import streamlit as st
import gspread
import streamlit.components.v1 as components
import time
from oauth2client.service_account import ServiceAccountCredentials
from rapidfuzz import process
from datetime import datetime


# ======================
# VERSION
# ======================
VERSION = "1.0.0"

# ======================
# CACHE SETTING
# ======================
@st.cache_resource
def get_client():
    return connect_client()


# ======================
# CONFIGURATION
# ======================
SPREADSHEET_NAME = "Objection Library"     # Nama file Google Sheets

DATA_SHEET_NAME = "Lib"      # Sheet utama (data objection)
LOG_SHEET_NAME = "Log"      # Sheet log (tracking usage)


# ======================
# CONNECT TO GOOGLE SHEETS
# ======================
def connect_client():
    """
    Membuat koneksi ke Google Sheets API menggunakan service account.

    Return:
        client (gspread.Client)
    """
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json",
        scope
    )

    return gspread.authorize(creds)


def get_data_sheet(client):
    """
    Mengambil worksheet utama (Lib)

    Args:
        client: gspread client

    Return:
        worksheet
    """
    return client.open(SPREADSHEET_NAME).worksheet(DATA_SHEET_NAME)


def get_log_sheet(client):
    """
    Mengambil worksheet log (Log)

    Args:
        client: gspread client

    Return:
        worksheet
    """
    return client.open(SPREADSHEET_NAME).worksheet(LOG_SHEET_NAME)


# ======================
# WRAP RETRY
# ======================
def safe_request(func, *args, retries=3):
    for i in range(retries):
        try:
            return func(*args)
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(1)  # Tunggu sebelum retry


# ======================
# LOGGING SYSTEM
# ======================
def add_log(match_key):
    """
    Simpang Log ke buffer

    Args:
        match_key: string (key objection yang dicari)
    """
    if "log_buffer" not in st.session_state:
        st.session_state["log_buffer"] = []

    st.session_state["log_buffer"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "objection": match_key
    })

def flush_logs(client):
    """ 
    Kirim log dari buffer ke Google Sheets
    Args:
        client: gspread client
    """
    if "log_buffer" not in st.session_state:
        return
    
    if not st.session_state["log_buffer"]:
        return
    
    log_sheet = get_log_sheet(client)

    rows = [
        [item["timestamp"], item["objection"]]
        for item in st.session_state["log_buffer"]
    ]

    safe_request(log_sheet.append_rows, rows)

    # Clear buffer setelah flush
    st.session_state["log_buffer"] = []


# ======================
# ANALYTICS UTILITIES
# ======================
from datetime import timedelta
from collections import Counter

def filter_logs_by_date(logs, start_date, end_date):
    result = []

    for row in logs:
        try:
            ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
        except:
            continue  # Skip jika format timestamp tidak valid

        if start_date <= ts.date() <= end_date:
            result.append(row)

    return result

def count_objections(logs):
    """
    Menghitung frekuensi setiap objection dari data log.

    Args:
        logs: List of dict (filtered log entries)

    Return:
        Counter object dengan frekuensi setiap objection
    """
    counter = Counter()

    for row in logs:
        counter[row["objection"]] += 1

    return counter


# ======================
# TRANSFORM SHEET DATA → DICTIONARY
# ======================
def sheet_to_dict(records):
    """
    Convert list of records dari Google Sheets
    menjadi dictionary untuk akses cepat.

    Struktur hasil:
    {
        "mahal": {
            "keywords": ["harga", "biaya"],
            "tujuan": "...",
            "responses": {
                "soft": "...",
                "medium": "...",
                "hard": "..."
            }
        }
    }
    """
    result = {}

    for row in records:
        key = row["objection"].lower()

        # Split keywords (pisahkan dengan koma di Google Sheets)
        keywords = [
            k.strip().lower()
            for k in row.get("keywords", "").split(",")
            if k
        ]

        result[key] = {
            "keywords": keywords,
            "tujuan": row["tujuan"],
            "responses": {
                "soft": row["soft"],
                "medium": row["medium"],
                "hard": row["hard"]
            }
        }

    return result

# ======================
# LOAD DATA WITH CACHE
# ======================
@st.cache_data(ttl=60) # Cache data selama 60 detik untuk mengurangi overhead load data berulang
def load_data():
    client = get_client() 
    sheet = get_data_sheet(client)
    return sheet.get_all_records()


# ======================
# LOAD DATA
# ======================
client = get_client() # Cache client selama 60 detik untuk mengurangi overhead koneksi berulang
data_sheet = get_data_sheet(client)
records = load_data()  # Menggunakan fungsi dengan cache untuk load data sheet
data = sheet_to_dict(records)  # Konversi data sheet ke dictionary untuk akses cepat


# ======================
# SMART MATCH SYSTEM
# ======================
def smart_match(query, data):
    """
    Mencari objection terbaik berdasarkan:
    1. Exact match
    2. Keyword match
    3. Fuzzy match (fallback)

    Return:
    - key (string) jika ditemukan
    - None jika tidak
    """
    query = query.lower()

    # 1. Exact match
    if query in data:
        return query

    # 2. Keyword match
    for key, item in data.items():
        if query in item["keywords"]:
            return key

    # 3. Fuzzy match (fallback)
    keys = list(data.keys())
    result = process.extractOne(query, keys)

    if result and result[1] > 60:  # threshold similarity
        return result[0]

    return None


# ======================
# COPY TO CLIPBOARD BUTTON
# ======================
def copy_button(text, key):
    components.html(f"""
        <textarea id="text-{key}" style="display:none;">{text}</textarea>

        <button style="
            background-color:#262730;
            color:white;
            border:none;
            padding:6px 10px;
            border-radius:6px;
            cursor:pointer;
            font-size:12px;
        " onclick="
            const text = document.getElementById('text-{key}').value;
            navigator.clipboard.writeText(text);
            this.innerText = '✅';
            setTimeout(() => this.innerText = '📋', 1200);
        ">
            📋
        </button>
    """, height=40)


# ======================
# MATCH COUNTER
# ======================
def increment_count(data_sheet, match_key):
    try:
        cell = data_sheet.find(match_key)
    except:
        return  # Jika tidak ditemukan, keluar dari fungsi
    
    if cell:
        row = cell.row
        current = data_sheet.cell(row, 7).value or 0  # Kolom G untuk count

        try:
            current = int(current)
        except:
            current = 0

        safe_request(data_sheet.update_cell, row, 7, current + 1)  # Update count di kolom G


# ======================
# CLEAR FORM HANDLER
# ======================
if "clear_form" in st.session_state and st.session_state["clear_form"]:
    st.session_state["objection_input"] = ""
    st.session_state["keywords_input"] = ""
    st.session_state["tujuan_input"] = ""
    st.session_state["soft_input"] = ""
    st.session_state["medium_input"] = ""
    st.session_state["hard_input"] = ""

    st.session_state["clear_form"] = False


# ======================
# PAGE SETUP
# ======================
st.set_page_config(
    page_title="ISM Objection Library",
    page_icon="💰",
    layout="centered"
)

st.title("💰 ISM Objection Library")
st.caption("Internal Tool — Algonova Sales Team")


# ======================
# SEARCH SECTION
# ======================
st.subheader("🔍 Cari Objection")

with st.form("search_form", clear_on_submit=True):
    query = st.text_input("Contoh: mahal, harga, kemahalan", key="search_input", placeholder="Ketik objection atau keyword...")
    submitted = st.form_submit_button("Cari")

# LOGIC
if submitted and query:
    match = smart_match(query, data)

    if match:
        item = data[match]

        # 🔥 update count
        increment_count(data_sheet, match)

        # 🔥 log ke sheet Log
        add_log(match)

        st.subheader(f"📌 Objection: {match}")
        st.write(f"🎯 Tujuan: {item['tujuan']}")

        st.divider()

        for level, text in item["responses"].items():
            cleaned_text = text

            # Label
            st.markdown(f"""
                <div style="
                    font-size: 15px;
                    letter-spacing: 0.5px;
                    opacity: 0.8;
                    font-weight: 600;
                    margin: 0;
                ">
                    {level.capitalize()}
                </div>
            """, unsafe_allow_html=True)

            # Copy button + response text
            safe_text = cleaned_text.replace("`", "\\`")  # Escape backticks untuk mencegah masalah rendering
            
            components.html(f"""
                <div style="margin-bottom:16px;">
                    <div onclick="
                        navigator.clipboard.writeText(`{safe_text}`);

                        const msg = document.createElement('div');
                        msg.innerText = 'Copied!';
                        msg.style.fontSize = '12px';
                        msg.style.color = '#4caf50';
                        msg.style.marginTop = '6px';

                        this.appendChild(msg);

                        setTimeout(() => msg.remove(), 1000);
                    "
                    style="
                        position: relative;
                        background-color: #1e1e1e;
                        padding: 16px;
                        border-radius: 10px;
                        font-family: monospace;
                        color: #e6e6e6;
                        font-size: 15.5px;
                        line-height: 1.6;
                        cursor: pointer;
                        transition: 0.2s;
                    "
                    onmouseover="this.style.backgroundColor='#2a2a2a'"
                    onmouseout="this.style.backgroundColor='#1e1e1e'"
                    >
                        {cleaned_text}
                    </div>
                </div>
            """, height=160)
    else:
        st.warning(f"❌ Objection \"{query}\" tidak ditemukan!")


# ======================
# LOAD LOGS WITH CACHE
# ======================
@st.cache_data(ttl=60) # Cache analytics selama 60 detik untuk mengurangi beban load data berulang
def load_logs():
    client = get_client()
    log_sheet = get_log_sheet(client)
    return log_sheet.get_all_records()


# ======================
# ANALYTICS (PERIOD)
# ======================
st.divider()

col1, col2 = st.columns([4, 1])

with col1:
    st.subheader("📊 Top Objections (By Period)")

with col2:
    if st.button("🔄", help="Sync & Refresh"):
        try:
            flush_logs(client)  # Flush log buffer sebelum reload data log
            load_logs.clear()  # Clear cache untuk load_logs agar data terbaru bisa dimuat ulang
            load_data.clear()  # Clear cache untuk load_data agar data terbaru bisa dimuat ulang
            st.toast("Synced and refreshed!", icon="✅")
        except Exception:
            st.toast("Failed to sync.", icon="❌")

from datetime import date

today = date.today()

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Start Date", value=today - timedelta(days=30))

with col2:
    end_date = st.date_input("End Date", value=today)

if start_date > end_date:
    st.error("Start Date tidak boleh lebih besar dari End Date")

logs = load_logs()  # Menggunakan fungsi dengan cache untuk load data log sheet

filtered_logs = filter_logs_by_date(logs, start_date, end_date)
counts = count_objections(filtered_logs)

top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]

if not top and start_date <= end_date:
    st.info("Belum ada data untuk periode ini. Coba pilih tanggal lain.")
else:
    for obj, cnt in top:
        st.write(f"{obj} — {cnt} kali")


# ======================
# ADD NEW OBJECTION
# ======================
st.divider()

with st.expander("➕ Tambah Objection Baru"):
    with st.form("add_form"):
        new_key = st.text_input("Objection", key="objection_input")
        keywords = st.text_input("Keywords", key="keywords_input")
        tujuan = st.text_input("Tujuan respon", key="tujuan_input")

        soft = st.text_area("Soft response", key="soft_input")
        medium = st.text_area("Medium response", key="medium_input")
        hard = st.text_area("Hard response", key="hard_input")

        submit = st.form_submit_button("Simpan")

        if submit:
            safe_request(
                data_sheet.append_row, [
                    new_key.lower(),
                    keywords.lower(),
                    tujuan,
                    soft,
                    medium,
                    hard
                ]
            )

            load_data.clear()  # Clear cache untuk load_data agar data terbaru bisa dimuat ulang
            load_logs.clear()  # Clear cache untuk load_logs agar data log terbaru bisa dimuat ulang

            st.toast("Data berhasil disimpan!", icon="✅")

            # Clear form inputs
            st.session_state["clear_form"] = True

            st.rerun()  # Refresh halaman untuk update data


# =======================
# AUTO FLUSH LOG BUFFER
# =======================
if "log_buffer" in st.session_state and len(st.session_state["log_buffer"]) >= 5:   # Flush log jika buffer sudah mencapai 5 item untuk mencegah kehilangan data
    flush_logs(client)


# ======================
# DEBUG (OPTIONAL)
# ======================
with st.expander("🔍 Debug Data"):
    st.write(records)


# ======================
# FOOTER
# ======================
st.divider()

st.markdown(f"""
    <div style="
        text-align: center;
        font-size: 12.5px;
        opacity: 0.5;
        margin-top: 8px;
    ">
        Version {VERSION} • Built by <span style="font-weight:700;">ownch</span> 
    </div>
""", unsafe_allow_html=True)