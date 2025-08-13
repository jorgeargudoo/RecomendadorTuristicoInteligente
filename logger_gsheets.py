import streamlit as st
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_NAME = "Logs_TurismoCarboneras"

def _load_sa_credentials():
    """
    Lee el service account desde st.secrets (dict TOML o JSON string),
    y normaliza la private_key para evitar errores PEM.
    """
    raw = st.secrets.get("gcp_service_account")
    if raw is None:
        raise RuntimeError("No se encontró 'gcp_service_account' en secrets.")

    # Puede venir como dict (secrets.toml con [gcp_service_account]) o como string JSON
    if isinstance(raw, dict):
        creds_dict = dict(raw)
    else:
        # string -> JSON
        creds_dict = json.loads(raw)

    # Normaliza saltos de línea (si vienen como literales '\n')
    pk = creds_dict.get("private_key", "")
    if "\\n" in pk:
        pk = pk.replace("\\n", "\n")
    creds_dict["private_key"] = pk

    return Credentials.from_service_account_info(creds_dict, scopes=SCOPE)

@st.cache_resource(show_spinner=False)
def _get_gs_client_and_sheet():
    """
    Cachea cliente y sheet para no re‑autenticar en cada log.
    """
    credentials = _load_sa_credentials()
    client = gspread.authorize(credentials)
    sheet = client.open(SPREADSHEET_NAME).sheet1
    return client, sheet

def get_sheet():
    """
    Mantengo esta función por compatibilidad con tu código.
    """
    _, sheet = _get_gs_client_and_sheet()
    return sheet

def log_event(evento, datos):
    """
    Guarda eventos en Google Sheets: [timestamp_utc, evento, json_datos]
    Nunca rompe la app si falla; muestra el error 1 sola vez por sesión.
    """
    try:
        sheet = get_sheet()
        fila = [datetime.utcnow().isoformat(), evento, json.dumps(datos, ensure_ascii=False)]
        sheet.append_row(fila)
    except Exception as e:
        # Evitar spam de error en cada llamada
        key = "_gsheets_error_shown"
        if not st.session_state.get(key):
            st.session_state[key] = True
            st.error(f"Error al guardar en Google Sheets: {e}")
