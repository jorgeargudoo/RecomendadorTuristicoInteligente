import streamlit as st
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Alcance de permisos para Google Sheets
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Nombre de tu hoja de Google Sheets (cámbialo si es distinto)
SPREADSHEET_NAME = "Logs_TurismoCarboneras"

def get_sheet():
    """
    Conecta con Google Sheets usando las credenciales guardadas en Streamlit Secrets.
    """
    # Cargar credenciales desde secrets
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    client = gspread.authorize(credentials)
    return client.open(SPREADSHEET_NAME).sheet1

def log_event(evento, datos):
    """
    Guarda eventos en Google Sheets en el formato:
    [timestamp, evento, json_datos]
    """
    try:
        sheet = get_sheet()
        fila = [datetime.now().isoformat(), evento, json.dumps(datos, ensure_ascii=False)]
        sheet.append_row(fila)
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
