import streamlit as st
import json
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_NAME = "Logs_TurismoCarboneras"

def _load_sa_credentials():
    raw = st.secrets.get("gcp_service_account")
    if raw is None:
        raise RuntimeError("No se encontró 'gcp_service_account' en secrets.")

    if isinstance(raw, dict):
        creds_dict = dict(raw)
    else:
        creds_dict = json.loads(raw)

    pk = creds_dict.get("private_key", "")
    if "\\n" in pk:
        pk = pk.replace("\\n", "\n")
    creds_dict["private_key"] = pk

    return Credentials.from_service_account_info(creds_dict, scopes=SCOPE)

@st.cache_resource(show_spinner=False)
def _get_gs_client_and_sheet():
    credentials = _load_sa_credentials()
    client = gspread.authorize(credentials)
    sheet = client.open(SPREADSHEET_NAME).sheet1
    return client, sheet

def get_sheet():
    _, sheet = _get_gs_client_and_sheet()
    return sheet

def log_event(evento, datos):
    try:
        sheet = get_sheet()
        fila = [
                (datetime.utcnow() + timedelta(hours=2)).replace(microsecond=0).isoformat(),
                evento,
                json.dumps(datos, ensure_ascii=False)
            ]
        sheet.append_row(fila)
    except Exception as e:
        key = "_gsheets_error_shown"
        if not st.session_state.get(key):
            st.session_state[key] = True
            st.error(f"Error al guardar en Google Sheets: {e}")



