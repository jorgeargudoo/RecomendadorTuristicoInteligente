import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import joblib
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import requests
import numpy as np
import os
# Ruta relativa al modelo en tu repo
RUTA_MODELO = "modelo_turismo.pkl"

# Cargar el modelo una sola vez
@st.cache_resource
def cargar_modelo():
    return joblib.load(RUTA_MODELO)

class AEMET:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://opendata.aemet.es/opendata/api"

    def get_prediccion_url(self, id_municipio):
        """Obtiene la URL de los datos crudos para un municipio."""
        resp = requests.get(
            f"{self.base_url}/prediccion/especifica/municipio/diaria/{id_municipio}",
            headers={"api_key": self.api_key}
        )
        resp.raise_for_status()
        return resp.json().get("datos")

    def get_datos_prediccion(self, datos_url):
        """Descarga el JSON de predicción desde la URL proporcionada por AEMET."""
        resp = requests.get(datos_url)
        resp.raise_for_status()
        datos = resp.json()

        # Asegurarnos de que existe la estructura esperada
        if isinstance(datos, list) and "prediccion" in datos[0]:
            return datos[0]["prediccion"]["dia"][0]  # Día de hoy
        else:
            raise ValueError("Estructura de JSON inesperada en datos de AEMET")

    def extraer_datos_relevantes(self, prediccion_dia):
        """Extrae las variables relevantes para el sistema de recomendaciones."""
        try:
            fecha = prediccion_dia.get("fecha", None)

            tmax = prediccion_dia.get("temperatura", {}).get("maxima", None)
            tmin = prediccion_dia.get("temperatura", {}).get("minima", None)

            # Precipitación: tomamos el primer valor disponible (periodo 00-24)
            prob_lluvia = 0
            if "probPrecipitacion" in prediccion_dia and len(prediccion_dia["probPrecipitacion"]) > 0:
                prob_lluvia = prediccion_dia["probPrecipitacion"][0].get("value", 0) or 0

            uv = prediccion_dia.get("uvMax", None)

            return {
                "fecha": fecha,
                "tmax": int(tmax) if tmax is not None else None,
                "tmin": int(tmin) if tmin is not None else None,
                "lluvia": int(prob_lluvia),
                "UV": int(uv) if uv is not None else None
            }
        except Exception as e:
            raise ValueError(f"Error extrayendo datos: {e}")

class OpenUV:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.openuv.io/api/v1"

    def get_current_uv(self, lat, lon):
        """Obtiene el UV actual en tiempo real desde OpenUV."""
        headers = {"x-access-token": self.api_key}
        params = {"lat": lat, "lng": lon}
        resp = requests.get(f"{self.base_url}/uv", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        return round(data["result"]["uv"], 2)  # UV actual redondeado a 2 decimales

@st.cache_data(ttl=3600)  # cachea durante 1 hora
def obtener_clima_hoy():
    """Consulta AEMET y OpenUV, y devuelve el clima de hoy."""
    API_KEY_AEMET = st.secrets["API_KEY_AEMET"]
    API_KEY_OPENUV = st.secrets["API_KEY_OPENUV"]

    aemet = AEMET(api_key=API_KEY_AEMET)
    openuv = OpenUV(api_key=API_KEY_OPENUV)

    # 1️⃣ Obtener datos base desde AEMET
    datos_url = aemet.get_prediccion_url("16055")  # ID de Carboneras de Guadazaón
    prediccion_dia = aemet.get_datos_prediccion(datos_url)
    clima_hoy = aemet.extraer_datos_relevantes(prediccion_dia)

    # 2️⃣ Sustituir UV por valor actual desde OpenUV
    uv_actual = openuv.get_current_uv(lat=39.8997, lon=-1.8123)
    clima_hoy["UV"] = uv_actual

    return clima_hoy

modelo_recomendador = joblib.load("modelo_turismo.pkl")

# from logger_gsheets import log_event  # Logs desactivados por ahora

# -------------------------
# CONFIGURACIÓN INICIAL
# -------------------------
st.set_page_config(page_title="Carboneras de Guadazaón", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
        /* Color de fondo */
        .stApp {
            background-color: #eaf5ea; /* Verde pastel */
        }
        .main-title {
            text-align: center;
            font-size: 3em;
            font-weight: bold;
            color: #2f4f2f;
        }
        .title-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
        }
        .title-container img {
            height: 80px;
        }
        .subtitle {
            text-align: center;
            font-size: 1.2em;
            color: #4f704f;
            margin-top: -10px;
            font-style: italic;
        }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# FUNCIONES AUXILIARES
# -------------------------

def mostrar_mapa_recomendaciones(lugares_recomendados, LUGARES_INFO):
    """
    Muestra en un mapa solo los lugares recomendados, con popups detallados.
    
    Parámetros:
    - lugares_recomendados: lista con claves tipo "CastilloAliaga", "Ruta1", etc.
    - LUGARES_INFO: diccionario anidado con la información detallada de cada lugar
    """
    m = folium.Map(location=[39.883, -1.80], zoom_start=13)

    for clave in LUGARES_INFO: #HAY QUE PONER lugares_recomendados
        lugar = LUGARES_INFO.get(clave)
        if lugar:
            # Generar HTML para el popup
            nombre = lugar.get("nombre", "Lugar sin nombre")
            descripcion = lugar.get("descripcion", "")
            imagen = lugar.get("imagen_url", "")
            
            popup_html = f"<b>{nombre}</b><br>"
            if imagen:
                popup_html += f'<img src="{imagen}" width="200"><br>'
            popup_html += f'<p style="width:200px;">{descripcion}</p>'

            folium.Marker(
                location=[lugar["lat"], lugar["lon"]],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color="green", icon="info-sign")
            ).add_to(m)

    # Mostrar el mapa en Streamlit
    st_folium(m, width=700, height=500)

def formulario_usuario():
    st.write("Por favor, rellena este formulario para obtener recomendaciones personalizadas:")

    edad = st.slider("¿Cuál es tu edad?", 10, 80, 25)
    genero = st.selectbox("¿Cuál es tu género?", ["Hombre", "Mujer", "Otro"])
    genero_cod = 0 if genero == "Hombre" else 1 if genero == "Mujer" else 0.5

    residencia_opciones = ["Sí, todo el año", "Solo en verano o en vacaciones", "No, pero soy de aquí", "No"]
    residencia = st.selectbox("¿Vives en Carboneras?", residencia_opciones)
    residencia_dict = pd.get_dummies(pd.Series([residencia]), prefix="residencia")
    residencia_dict = residencia_dict.reindex(columns=[
    'residencia_Sí, todo el año',
    'residencia_Solo en verano o en vacaciones',
    'residencia_No, pero soy de aquí',
    'residencia_No'
    ], fill_value=0)

    residencia_dict = residencia_dict.iloc[0].to_dict()


    actividad_opciones = ["Solo en fiestas o vacaciones", "De vez en cuando", "Varias veces por semana", "A diario"]
    freq_actividad = st.selectbox("¿Con qué frecuencia realizas actividades turísticas?", actividad_opciones)
    actividad_map = {actividad_opciones[i]: i for i in range(len(actividad_opciones))}
    freq_actividad_cod = actividad_map[freq_actividad]

    freq_recom_opciones = ["Nunca", "Pocas veces", "A veces", "A menudo", "Siempre"]
    freq_recom = st.selectbox("¿Con qué frecuencia recomiendas actividades a otras personas?", freq_recom_opciones)
    freq_recom_map = {freq_recom_opciones[i]: i + 1 for i in range(len(freq_recom_opciones))}
    freq_recom_cod = freq_recom_map[freq_recom]

    actividades_disponibles = [
        "Naturaleza y paseos", "Rutas", "Monumentos o historia",
        "Sitios tranquilos para descansar", "Eventos o fiestas",
        "Bares y restaurantes"
    ]

    st.subheader("¿Qué actividades recomendarías a familias?")
    actividades_familias = st.multiselect("Selecciona actividades para familias", actividades_disponibles, key="familias")
    
    st.subheader("¿Qué actividades recomendarías a jóvenes?")
    actividades_jovenes = st.multiselect("Selecciona actividades para jóvenes", actividades_disponibles, key="jovenes")
    
    st.subheader("¿Qué actividades recomendarías a mayores?")
    actividades_mayores = st.multiselect("Selecciona actividades para mayores", actividades_disponibles, key="mayores")

    def codificar_actividades(actividades_seleccionadas, grupo):
        return {f"{grupo}_{actividad}": 1 if actividad in actividades_seleccionadas else 0
                for actividad in actividades_disponibles}

    recom_familias = codificar_actividades(actividades_familias, "recom_familias")
    recom_jovenes = codificar_actividades(actividades_jovenes, "recom_jovenes")
    recom_mayores = codificar_actividades(actividades_mayores, "recom_mayores")

    datos_usuario = {
    "edad": edad,
    "genero": genero_cod,
    "actividad_frecuencia": freq_actividad_cod,
    "freq_recom": freq_recom_cod,
    **residencia_dict,
    **recom_familias,
    **recom_jovenes,
    **recom_mayores
    }
    
    return datos_usuario

def mostrar_informacion_local():
    st.header("Descubre Carboneras de Guadazaón")
    st.subheader("Fiestas del municipio")
    st.write("Durante la última semana de agosto, se realizan actividades culturales, conciertos y mercados artesanales.")
    st.subheader("Domingo de Procesiones en Mayo")
    st.write("Se celebra con desfiles tradicionales y música en vivo.")
    st.subheader("Lugares de interés")
    st.write("Aquí aparecerá la lista de todos los lugares con su información.")

def mostrar_servicios():
    st.header("Servicios")
    st.write("Aquí aparecerán las tiendas, hostales, casas rurales, restaurantes, bares, etc.")

def mostrar_sobre_nosotros():
    st.header("Sobre nosotros")
    st.write("Información sobre el ayuntamiento, el alcalde y la finalidad de esta página.")

# -------------------------
# CUERPO PRINCIPAL
# -------------------------
# Título con escudo
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.markdown(f"""
        <div class="title-container">
            <div class="main-title">Carboneras de Guadazaón</div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="subtitle">DONDE REPOSA EL SUEÑO DEL NUEVO MUNDO</div>', unsafe_allow_html=True)

# Navegación principal
pagina = st.radio(
    " ", 
    ["Descubre Carboneras de Guadazaón", "Recomendador turístico", "Servicios", "Sobre nosotros"],
    index=0,
    horizontal=True
)

# Lógica difusa
tmax = ctrl.Antecedent(np.arange(-5, 46, 1), 'tmax')
tmin = ctrl.Antecedent(np.arange(-10, 36, 1), 'tmin')
prob = ctrl.Antecedent(np.arange(0, 101, 1), 'prob_lluvia')
uv = ctrl.Antecedent(np.arange(0, 13, 1), 'UV')
recom_exterior = ctrl.Consequent(np.arange(0, 1.1, 0.1), 'recom_exterior')
# tmax
tmax['frio'] = fuzz.trapmf(tmax.universe, [-5, -5, 5, 12])
tmax['moderado'] = fuzz.trimf(tmax.universe, [10, 20, 28])
tmax['calido'] = fuzz.trapmf(tmax.universe, [25, 30, 45, 45])

# tmin
tmin['muy_frio'] = fuzz.trapmf(tmin.universe, [-10, -10, 0, 5])
tmin['frio'] = fuzz.trimf(tmin.universe, [3, 8, 13])
tmin['suave'] = fuzz.trapmf(tmin.universe, [10, 15, 35, 35])

# prob_lluvia
prob['baja'] = fuzz.trapmf(prob.universe, [0, 0, 20, 30])
prob['media'] = fuzz.trimf(prob.universe, [20, 50, 80])
prob['alta'] = fuzz.trapmf(prob.universe, [70, 85, 100, 100])

# UV
uv['bajo'] = fuzz.trapmf(uv.universe, [0, 0, 3, 6])
uv['moderado'] = fuzz.trimf(uv.universe, [4, 7, 9])
uv['alto'] = fuzz.trapmf(uv.universe, [6, 10, 14, 14])

# recom_exterior
recom_exterior['no'] = fuzz.trapmf(recom_exterior.universe, [0, 0, 0.2, 0.4])
recom_exterior['posible'] = fuzz.trimf(recom_exterior.universe, [0.3, 0.5, 0.7])
recom_exterior['si'] = fuzz.trapmf(recom_exterior.universe, [0.6, 0.8, 1, 1])
rules = [
    # NO RECOMENDABLE
    ctrl.Rule(prob['alta'], recom_exterior['no']),
    ctrl.Rule(tmax['frio'] & tmin['muy_frio'], recom_exterior['no']),
    ctrl.Rule(tmax['calido'] & uv['alto'], recom_exterior['no']),

    # POSIBLE
    ctrl.Rule(prob['media'] & (tmax['moderado'] | tmax['calido']), recom_exterior['posible']),
    ctrl.Rule(prob['baja'] & tmax['frio'] & tmin['frio'], recom_exterior['posible']),
    ctrl.Rule(prob['baja'] & uv['moderado'], recom_exterior['posible']),

    # SI RECOMENDABLE
    ctrl.Rule(prob['baja'] & tmax['moderado'] & tmin['suave'], recom_exterior['si']),
    ctrl.Rule(prob['baja'] & uv['bajo'], recom_exterior['si']),
    ctrl.Rule(prob['baja'] & tmax['calido'] & uv['bajo'], recom_exterior['si']),
]
sistema_ctrl = ctrl.ControlSystem(rules)
def recomendar(clima):
    sim = ctrl.ControlSystemSimulation(sistema_ctrl)
    sim.input['tmax'] = clima.get('tmax', 20)
    sim.input['tmin'] = clima.get('tmin', 10)
    sim.input['prob_lluvia'] = clima.get('lluvia', 0)
    sim.input['UV'] = clima.get('UV', 5)
    sim.compute()
    return sim.output.get('recom_exterior')

LUGARES_EXTERIOR = {
            "CastilloAliaga",
            "LagunaCaolin",
            "RiberaRioGuadazaon",
            "CerritoArena",
            "MiradorCruz",
            "FuenteTresCanos",
            "PuenteCristinasRioCabriel",
            "TorcasPalancaresTierraMuerta",
            "LagunasCanadaHoyo",
            "ChorrerasRioCabriel",
            "FachadaHarinas",
            "Ruta1",
            "Ruta2",
            "SaltoBalsa",
            "MiradorPicarcho"
}

LUGARES_INFO = {
    "IglesiaSantoDomingoSilos": {
        "nombre": "Iglesia de Santo Domingo de Silos",
        "lat": 39.90095,
        "lon": -1.81300,
        "descripcion": "La Iglesia de Santo Domingo de Silos es uno de los lugares más emblemáticos de Carboneras de Guadazaón. Su origen se remonta al siglo XIII, aunque a lo largo del tiempo ha sido ampliada y transformada, combinando elementos románicos, mudéjares y toques más recientes, como su espadaña herreriana. En el interior sorprende su artesonado mudéjar policromado, una auténtica joya artesanal, y la pila bautismal románica que ha visto pasar generaciones de vecinos. Entre sus murales, pintados en el siglo XX por el párroco Carlos de la Rica, aparecen detalles curiosos y modernos que contrastan con la solemnidad del templo.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:IglesiaCarboneras.JPG"
    },  

    "PanteonMarquesesMoya": {
        "nombre": "Iglesia‑Panteón de los Marqueses de Moya",
        "lat": 39.90419,
        "lon": -1.81184,
        "descripcion": "La Iglesia-Panteón de los Marqueses de Moya es un monumento único en Carboneras de Guadazaón y un auténtico símbolo de su historia. Construida en el siglo XVI sobre el antiguo convento de Santo Domingo, destaca por su estilo gótico-isabelino, elegante y sobrio a la vez.En su interior descansan los Marqueses de Moya, Andrés de Cabrera y Beatriz de Bobadilla, figuras clave en la corte de los Reyes Católicos y protectores de Cristóbal Colón. Sus sepulcros, de piedra tallada con gran detalle, evocan el esplendor de la nobleza castellana de la época. El conjunto conserva elementos originales como la portada de arco apuntado y una cuidada decoración interior, que invitan a sumergirse en la historia local y en el papel que este rincón jugó en los grandes acontecimientos del siglo XV y XVI. Un lugar de visita obligada para los amantes de la historia y la arquitectura.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Carboneras-iglesiaPante%C3%B3n_(2019)9522.jpg"
    },  

    "CastilloAliaga": {
        "nombre": "Castillo de Aliaga",
        "lat": 39.951194001639635, 
        "lon": -1.84319081923086,
        "descripcion": "El Castillo de Aliaga se alza sobre un cerro cercano a Carboneras de Guadazaón, dominando el paisaje con sus restos de murallas y su privilegiada vista del valle del Guadazaón. Construido en época medieval como fortaleza defensiva, formó parte del sistema de control territorial de la Serranía y fue testigo de siglos de historia local. Aunque hoy solo se conservan las ruinas, su emplazamiento permite imaginar la importancia estratégica que tuvo. La subida al castillo, entre pinares y sendas, culmina con un mirador natural que regala panorámicas espectaculares, especialmente al atardecer. Visitarlo es una oportunidad para combinar naturaleza, senderismo y un viaje al pasado, en un entorno donde el silencio y las vistas invitan a detenerse y contemplar.",
        "imagen_url": "https://github.com/jorgeargudoo/RecomendadorTuristicoInteligente/blob/5c0f5f9d41e40faf86d76a69dc77b1bbbc4b24da/imagenes/CastilloAliaga.png"
    },  

    "LagunaCaolin": {
        "nombre": "Laguna de Caolín",
        "lat": 39.9035,
        "lon": -1.8200,
        "descripcion": "Antigua cantera de caolín hoy inundada; aguas turquesa en paisaje de pinar y yesos. Muy fotogénica.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Ayuntamiento_de_Carboneras_de_Guadaza%C3%B3n.jpg"
    },  # (coordenadas aproximadas; imagen municipal representativa) :contentReference[oaicite:3]{index=3}

    "RiberaRioGuadazaon": {
        "nombre": "Ribera del Río Guadazaón",
        "lat": 39.89614,
        "lon": -1.81006,
        "descripcion": "Paseo por vegas y huertas del Guadazaón con flora de ribera y tramos de sombra agradables.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Estaci%C3%B3n_de_Carboneras_de_Guadaza%C3%B3n_04.jpg"
    },  # (lat/long del núcleo como acceso; imagen del entorno local) :contentReference[oaicite:4]{index=4}

    "CerritoArena": {
        "nombre": "Cerrito de la Arena",
        "lat": 39.9000,
        "lon": -1.8050,
        "descripcion": "Pequeño alto testigo con yacimiento neolítico asociado a hallazgos de ‘mazos de piedra’ citados en la bibliografía local.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Ayuntamiento_de_Carboneras_de_Guadaza%C3%B3n.jpg"
    },  # (punto cercano al casco; referencia histórica en Wikipedia) :contentReference[oaicite:5]{index=5}

    "MiradorCruz": {
        "nombre": "Mirador de la Cruz",
        "lat": 39.9050,
        "lon": -1.8000,
        "descripcion": "Pequeña loma con cruz y vistas abiertas de los campos serranos; atardeceres muy vistosos.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Plaza_de_toros_de_Carboneras_de_Guadaza%C3%B3n.jpg"
    },  # (ubicación aproximada; imagen local libre) :contentReference[oaicite:6]{index=6}

    "FuenteTresCanos": {
        "nombre": "Fuente de los Tres Caños",
        "lat": 39.8995,
        "lon": -1.8120,
        "descripcion": "Fuente tradicional del pueblo, punto de agua y reunión en el casco histórico.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Ayuntamiento_de_Carboneras_de_Guadaza%C3%B3n.jpg"
    },  # (centro urbano; imagen representativa) :contentReference[oaicite:7]{index=7}

    "PuenteCristinasRioCabriel": {
        "nombre": "Puente de las Cristinas (río Cabriel)",
        "lat": 39.93069,
        "lon": -1.72325,
        "descripcion": "Puente de sillería (s. XVI) sobre el Cabriel, restaurado en 2018–2019; tramo de vía pecuaria histórica.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Pajaroncillo-puenteCristinas_(2019)9516.jpg"
    },  # :contentReference[oaicite:8]{index=8}

    "TorcasPalancaresTierraMuerta": {
        "nombre": "Torcas de Palancares / Tierra Muerta",
        "lat": 40.02854,
        "lon": -1.96132,
        "descripcion": "Conjunto de dolinas kársticas de gran tamaño en el monte de Los Palancares; senderos señalizados y pinar de pino negral.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Torcas_de_los_Palancares_-_Cuenca_-_Spain_-_panoramio.jpg"
    },  # (coords aproximadas del acceso; foto libre) :contentReference[oaicite:9]{index=9}

    "LagunasCanadaHoyo": {
        "nombre": "Lagunas de Cañada del Hoyo",
        "lat": 39.98611,
        "lon": -1.87222,
        "descripcion": "Monumento Natural (2007): lagunas kársticas de colores (Gitana, Tejo, Parra…); pasarelas y miradores.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Vistatotal3.jpg"
    },  # :contentReference[oaicite:10]{index=10}

    "ChorrerasRioCabriel": {
        "nombre": "Las Chorreras del río Cabriel",
        "lat": 39.672,
        "lon": -1.595,
        "descripcion": "Saltos, tobas y pozas turquesas entre Enguídanos y Víllora; paraje geológico y de baño regulado en verano.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Chorreras_de_Engu%C3%ADdanos_07.jpg"
    },  # (coords de entorno; imagen libre) :contentReference[oaicite:11]{index=11}

    "FachadaHarinas": {
        "nombre": "Fachada de la antigua fábrica de harinas",
        "lat": 39.8990,
        "lon": -1.8125,
        "descripcion": "Vestigio industrial (mediados del s. XX) junto al casco; fachada conservada como memoria del pasado fabril.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Ayuntamiento_de_Carboneras_de_Guadaza%C3%B3n.jpg"
    },  # (punto urbano; imagen local libre) :contentReference[oaicite:12]{index=12}

    "Ruta1": {
        "nombre": "Sendero Hoz del río Algarra",
        "lat": 39.8700,
        "lon": -1.8200,
        "descripcion": "Senda fluvial por la hoz del Algarra, con alternancia de ribera y farallones calcáreos; apta para público general.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Cabriel_River_-_Hoces_del_Cabriel_Natural_Park.jpg"
    },  # (aprox. entorno serrano; imagen del Cabriel/Hoces representativa) :contentReference[oaicite:13]{index=13}

    "Ruta2": {
        "nombre": "Ruta de los molinos de agua",
        "lat": 39.8880,
        "lon": -1.8020,
        "descripcion": "Itinerario local por antiguos aprovechamientos hidráulicos y vegas del Guadazaón.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Estaci%C3%B3n_de_Carboneras_de_Guadaza%C3%B3n_05.jpg"
    },  # (punto de salida en el pueblo; imagen local libre) :contentReference[oaicite:14]{index=14}

    "SaltoBalsa": {
        "nombre": "Salto de la Balsa",
        "lat": 39.9050,
        "lon": -1.7800,
        "descripcion": "Cascadilla y pozas del arroyo de la Balsa en entorno de pinar; tramo corto y umbrío.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Torcas_de_Palancares_(14_de_abril_de_2007,_Serran%C3%ADa_de_Cuenca)_06.JPG"
    },  # (aprox.; imagen natural libre de la Serranía) :contentReference[oaicite:15]{index=15}

    "MiradorPicarcho": {
        "nombre": "Mirador del Picarcho",
        "lat": 39.9670,
        "lon": -1.9000,
        "descripcion": "Alto cercano a Cañada del Hoyo con vistas a los pinares y lagunas; buen punto para amanecer/atardecer.",
        "imagen_url": "https://commons.wikimedia.org/wiki/File:Lagunas_de_Ca%C3%B1ada_del_Hoyo,_pan16_20101108_(5167346167).jpg"
    }  # (entorno de Cañada del Hoyo; imagen libre de las lagunas) :contentReference[oaicite:16]{index=16}
}


def filtrar_por_clima(recomendaciones, clima):
    """
    Filtra recomendaciones de lugares de exterior si el clima no es favorable.
    recomendaciones: dict {lugar: 1/0} (salida del primer modelo)
    clima: dict con tmax, tmin, lluvia, estado_cielo, UV
    """
    score_exterior = recomendar(clima)
    filtradas = recomendaciones.copy()

    if score_exterior < 0.50:  # umbral configurable
        for lugar in LUGARES_EXTERIOR:
            if lugar in filtradas:
                filtradas[lugar] = 0
    return filtradas

if pagina == "Descubre Carboneras de Guadazaón":
    mostrar_informacion_local()
elif pagina == "Recomendador turístico":
    st.header("Recomendador turístico")
    datos_usuario = formulario_usuario()  
    columnas_entrenamiento = [
            'edad', 'genero', 'actividad_frecuencia', 'freq_recom',
            'residencia_No', 'residencia_No, pero soy de aquí',
            'residencia_Solo en verano o en vacaciones', 'residencia_Sí, todo el año',
            'recom_familias_Naturaleza y paseos', 'recom_familias_Rutas',
            'recom_familias_Monumentos o historia', 'recom_familias_Sitios tranquilos para descansar',
            'recom_familias_Eventos o fiestas', 'recom_familias_Bares y restaurantes',
            'recom_jovenes_Naturaleza y paseos', 'recom_jovenes_Rutas',
            'recom_jovenes_Monumentos o historia', 'recom_jovenes_Sitios tranquilos para descansar',
            'recom_jovenes_Eventos o fiestas', 'recom_jovenes_Bares y restaurantes',
            'recom_mayores_Naturaleza y paseos', 'recom_mayores_Rutas',
            'recom_mayores_Monumentos o historia', 'recom_mayores_Sitios tranquilos para descansar',
            'recom_mayores_Eventos o fiestas', 'recom_mayores_Bares y restaurantes'
        ]
        
    df_usuario = pd.DataFrame([datos_usuario])
        
    # Rellenar columnas faltantes con 0
    for col in columnas_entrenamiento:
        if col not in df_usuario.columns:
            df_usuario[col] = 0
        
    # Asegurar el mismo orden de columnas
    df_usuario = df_usuario[columnas_entrenamiento]

        
    # Extraer los nombres de lugares a partir de las columnas del modelo
    lugares = [
        "IglesiaSantoDomingoSilos",
        "PanteonMarquesesMoya",
        "CastilloAliaga",
        "LagunaCaolin",
        "RiberaRioGuadazaon",
        "CerritoArena",
        "MiradorCruz",
        "FuenteTresCanos",
        "PuenteCristinasRioCabriel",
        "TorcasPalancaresTierraMuerta",
        "LagunasCanadaHoyo",
        "ChorrerasRioCabriel",
        "FachadaHarinas",
        "Ruta1",
        "Ruta2",
        "SaltoBalsa",
        "MiradorPicarcho"
    ]
    if st.button("Obtener recomendaciones", key="obtener_recomendaciones"):
        # Predecir
        modelo_recomendador = cargar_modelo()
        predicciones_binarias = modelo_recomendador.predict(df_usuario)[0]
        recomendaciones_dict = {lugar: int(pred) for lugar, pred in zip(lugares, predicciones_binarias)}
        try:
            clima_hoy = obtener_clima_hoy()
            recomendaciones_filtradas = filtrar_por_clima(recomendaciones_dict, clima_hoy)
            score_exterior = recomendar(clima_hoy)
            st.session_state.clima_hoy = clima_hoy
            st.session_state.score_exterior = score_exterior
            st.info(f"Filtrado climático aplicado. Score exterior: {score_exterior:.2f}")
        except Exception as e:
            recomendaciones_filtradas = recomendaciones_dict
            st.session_state.clima_hoy = None
            st.warning("No se pudo obtener el clima actual. Las recomendaciones no han sido filtradas por condiciones meteorológicas.")
            st.text(f"Error: {str(e)}")
    
        # Guardar resultados en sesión
        st.session_state.lugares_recomendados = [lugar for lugar, v in recomendaciones_filtradas.items() if v == 1]
        st.session_state.mostrar_resultados = True
    
    # ------------------------------
    # ✅ 2. BLOQUE PERMANENTE: mostrar el mapa y el feedback si ya se hizo clic
    # ------------------------------
    if st.session_state.get("mostrar_resultados", False):
        lugares_recomendados = st.session_state.get("lugares_recomendados", [])
        clima_hoy = st.session_state.get("clima_hoy", None)
    
        if lugares_recomendados:
            st.success("Lugares recomendados según tus gustos y el clima actual:" if clima_hoy else "Lugares recomendados según tus gustos:")
            mostrar_mapa_recomendaciones(lugares_recomendados, LUGARES_INFO)
        else:
            st.warning("No se encontraron lugares recomendados para ti.")
    
        feedback = st.slider("¿Qué valoración darías a estas recomendaciones?", min_value=1, max_value=5, value=3)
        st.write("Tu valoración:", "⭐" * feedback)
    
        if st.button("Enviar valoración", key="enviar_valoracion"):
            # log_event("feedback", {"satisfaccion": feedback})
            st.success(f"¡Gracias por tu valoración de {feedback} estrellas!")
    
        if st.button("Volver a empezar", key="volver_a_empezar"):
            st.session_state.clear()
            st.experimental_rerun()


elif pagina == "Servicios":
    mostrar_servicios()
elif pagina == "Sobre nosotros":
    mostrar_sobre_nosotros()






















