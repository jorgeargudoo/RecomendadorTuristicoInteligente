import json
from datetime import datetime
import os

LOG_FILE = "logs_usuarios.csv"

def log_event(evento, datos):
    """Guarda eventos en un archivo CSV para análisis posterior."""
    linea = f"{datetime.now().isoformat()},{evento},{json.dumps(datos, ensure_ascii=False)}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea)
