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
from folium.plugins import MarkerCluster
from folium import Html
from branca.element import IFrame
import html
from folium import Popup

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

POPUP_MAX_W = 1100   # ancho máx. en escritorio

def _popup_html_responsive(lugar):
    """
    Móvil: título + foto arriba + texto scroll debajo.
    Escritorio: dos columnas (texto izquierda, foto derecha).
    Altura limitada (82vh) para que la X de Leaflet se vea siempre.
    """
    import html as _html
    nombre = _html.escape(lugar.get("nombre", ""))
    descripcion = _html.escape(lugar.get("descripcion", ""))
    img = (lugar.get("imagen_url") or "").strip()

    img_block = f"""
      <div class="cell-img">
        <img src="{img}" alt="{nombre}" loading="lazy"
             style="width:100%;height:auto;border-radius:14px;display:block;" />
      </div>
    """ if img else ""

    return f"""
    <style>
      .pop-wrap {{
        width: min({POPUP_MAX_W}px, 95vw);
        height: clamp(420px, 82vh, 640px);   /* ⬅️ limita alto => X visible */
        background:#fff; border-radius:12px;
        box-sizing:border-box; margin:0 auto; padding:14px 16px;
        font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; color:#222;
        display:flex; flex-direction:column;
      }}
      .pop-title {{
        margin:0 0 10px 0; line-height:1.2;
        font-size:clamp(20px,2.3vw,30px);
      }}
      /* grid: móvil 1 columna, escritorio 2 columnas */
      .pop-grid {{
        display:grid; grid-template-columns: 1fr; gap:14px;
        /* área scrollable: ocupa todo el alto restante */
        overflow-y:auto; padding-right:4px;
      }}
      .cell-text p {{ margin:0; font-size:16px; line-height:1.55; text-align:justify; }}

      @media (min-width: 780px) {{
        .pop-grid {{ grid-template-columns: 1.1fr 0.9fr; gap:18px; }}
        .cell-text p {{ font-size:16px; }}
      }}
      @media (max-width: 779px) {{
        /* en móvil queremos foto ARRIBA y texto debajo */
        .cell-img {{ order: -1; }}
        .cell-text p {{ font-size:15px; line-height:1.6; }}
      }}
    </style>

    <div class="pop-wrap">
      <h2 class="pop-title">{nombre}</h2>
      <div class="pop-grid">
        {img_block}
        <div class="cell-text"><p>{descripcion}</p></div>
      </div>
    </div>
    """

def mostrar_mapa_recomendaciones(lugares_recomendados, LUGARES_INFO):
    m = folium.Map(location=[39.8997, -1.8123], zoom_start=12, tiles="OpenStreetMap")
    cluster = MarkerCluster().add_to(m)

    for key in LUGARES_INFO:#lugares_recomendados
        lugar = LUGARES_INFO.get(key)
        if not lugar:
            continue
        lat, lon = lugar.get("lat"), lugar.get("lon")
        if lat is None or lon is None:
            continue

        html_content = _popup_html_responsive(lugar)
        html_obj = Html(html_content, script=True)
        popup = folium.Popup(html_obj, max_width=2000, keep_in_view=True)  # grande pero dentro del mapa

        folium.Marker(
            location=[lat, lon],
            popup=popup,                       # la X se mantiene visible
            tooltip=lugar.get("nombre", ""),
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(cluster)

    # mapa fluido (en móvil ocupa todo el ancho de la columna)
    try:
        st_folium(m, height=520, use_container_width=True)
    except TypeError:
        st_folium(m, height=520)


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
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/8/87/IglesiaCarboneras.JPG"
    },  

    "PanteonMarquesesMoya": {
        "nombre": "Iglesia‑Panteón de los Marqueses de Moya",
        "lat": 39.90419,
        "lon": -1.81184,
        "descripcion": "La Iglesia-Panteón de los Marqueses de Moya es un monumento único en Carboneras de Guadazaón y un auténtico símbolo de su historia. Construida en el siglo XVI sobre el antiguo convento de Santo Domingo, destaca por su estilo gótico-isabelino, elegante y sobrio a la vez.En su interior descansan los Marqueses de Moya, Andrés de Cabrera y Beatriz de Bobadilla, figuras clave en la corte de los Reyes Católicos y protectores de Cristóbal Colón. Sus sepulcros, de piedra tallada con gran detalle, evocan el esplendor de la nobleza castellana de la época. El conjunto conserva elementos originales como la portada de arco apuntado y una cuidada decoración interior, que invitan a sumergirse en la historia local y en el papel que este rincón jugó en los grandes acontecimientos del siglo XV y XVI. Un lugar de visita obligada para los amantes de la historia y la arquitectura.",
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/0/08/Carboneras-iglesiaPante%C3%B3n_%282019%299522.jpg"
    },  

    "CastilloAliaga": {
        "nombre": "Castillo de Aliaga",
        "lat": 39.951194001639635, 
        "lon": -1.84319081923086,
        "descripcion": "El Castillo de Aliaga se alza sobre un cerro cercano a Carboneras de Guadazaón, dominando el paisaje con sus restos de murallas y su privilegiada vista del valle del Guadazaón. Construido en época medieval como fortaleza defensiva, formó parte del sistema de control territorial de la Serranía y fue testigo de siglos de historia local. Aunque hoy solo se conservan las ruinas, su emplazamiento permite imaginar la importancia estratégica que tuvo. La subida al castillo, entre pinares y sendas, culmina con un mirador natural que regala panorámicas espectaculares, especialmente al atardecer. Visitarlo es una oportunidad para combinar naturaleza, senderismo y un viaje al pasado, en un entorno donde el silencio y las vistas invitan a detenerse y contemplar.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/30e299d7c34cdab69548f78849e99d320ae10f34/imagenes/CastilloAliaga.png"
    },  

    "LagunaCaolin": {
        "nombre": "Laguna de Caolín",
        "lat": 39.84720272670936,
        "lon": -1.819389044226957,
        "descripcion": "Una joya escondida en la Serranía Baja de Cuenca. Sus aguas, teñidas por el caolín, adquieren un tono turquesa tan intenso como mágico, ofreciendo un escenario paisajístico que impacta al visitante. Rodeada por la tranquilidad del entorno, es el lugar perfecto para perderse en un paseo, relajarse en sus orillas o simplemente dejar volar la mirada hacia ese cielo despejado ideal para contemplar las estrellas. Un rincón íntimo y auténtico para los amantes de la calma, la fotografía y la naturaleza en estado puro.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/6908f89378bb433ab807a13c583bf90f5827c839/imagenes/LagunaCaolin.png"
    },  

    "RiberaRioGuadazaon": {
        "nombre": "Ribera y Vega del Río Guadazaón",
        "lat": 39.90780001314428, 
        "lon": -1.8501391205319577,
        "descripcion": "Este tramo del río Guadazaón integra una Reserva Natural Fluvial, un desfiladero calcáreo de gran belleza que conserva una notable pureza natural. Su curso, constante y fresco, discurre por un paisaje abierto en el que predomina la ribera despejada, arena y matorral bajo.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/6908f89378bb433ab807a13c583bf90f5827c839/imagenes/RiberaRioGuadaza%C3%B3n.png"
    },  

    "CerritoArena": {
        "nombre": "Cerrito de la Arena",
        "lat": 39.89086406647863, 
        "lon": -1.8221526191135788,
        "descripcion": "Un pequeño pero significativo altozano arqueológico donde convergen naturaleza y memoria ancestral. Aquí se descubrieron mazos neolíticos que revelan la presencia de sociedades humanas en tiempos remotos. Rodeado de un paisaje sereno y de rasgos rurales, el Cerrito invita a escalar con calma, respirar historia y sentir el pulso de un territorio milenario. Ideal para quienes disfrutan del senderismo pausado, la arqueología y los rincones cargados de pasado.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/6908f89378bb433ab807a13c583bf90f5827c839/imagenes/CerritoArena.png"
    }, 

    "MiradorCruz": {
        "nombre": "Mirador de la Cruz",
        "lat": 39.89114466708043, 
        "lon": -1.811936158954885,
        "descripcion": "Situado junto al barranco de la Cruz, este mirador natural ofrece una vista amplia y despejada sobre la serranía conquense y el entorno rural que rodea Carboneras de Guadazaón. El paraje, de unos 30 hectáreas, está dominado por pinar rodeno y curiosas formaciones areniscas que dan al paisaje un carácter escultórico y salvaje. Desde este punto elevado, los visitantes pueden disfrutar de panorámicas relajantes que incluyen las lomas, los barrancos y aldeas vecinas, ideal para contemplación, fotografía o relajarse en plena naturaleza.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/6908f89378bb433ab807a13c583bf90f5827c839/imagenes/MiradorDeLaCruz.jpg"
    }, 

    "FuenteTresCanos": {
        "nombre": "Fuente de los Tres Caños",
        "lat": 39.901025495667355, 
        "lon": -1.8099679469497392,
        "descripcion": "Una joya discreta y llena de encanto en el descanso del casco urbano, esta fuente tradicional destaca por sus tres caños que vierten agua —probablemente sobre un pilote rectangular tallado en piedra— evocando la serenidad de tiempos pasados. Esta estructura hidráulica, aunque humilde, posee un gran valor simbólico como punto de encuentro cotidiano de generaciones de vecinos y visitantes que acudían para proveerse de agua fresca.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/6908f89378bb433ab807a13c583bf90f5827c839/imagenes/FuenteTresCa%C3%B1os.png"
    },  

    "PuenteCristinasRioCabriel": {
        "nombre": "Puente de Cristinas (río Cabriel)",
        "lat": 39.93071335264869,
        "lon": -1.7232249678399227,
        "descripcion": "El puente de Cristinas se trata de un viaducto de estilo gótico tardío construido en el siglo XVI. Está ubicado junto a la carretera N‑420, a unos 3 km de Pajaroncillo, enclavado en un punto estratégico donde se cruzan rutas hacia Cañete, Teruel, Albarracín y Villar del Humo. El Cabriel, de aguas cristalinas, ha sido durante siglos una vía natural esencial para el transporte de madera y el paso de ganados. Fluye por parajes de gran valor paisajístico y ecológico, surcando hoces, meandros, cascadas y pozas, configurando un entorno contrastado entre la fuerza del agua y la serenidad del paisaje",
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/9/9f/Pajaroncillo-puenteCristinas_%282019%299516.jpg"
    }, 

    "TorcasPalancaresTierraMuerta": {
        "nombre": "Torcas de Palancares y Tierra Muerta",
        "lat": 40.022446164770116, 
        "lon": -1.9504629457191553,
        "descripcion": "Explora uno de los paisajes kársticos más fascinantes de la Serranía de Cuenca: un Monumento Natural donde el terreno se hunde en profundas y misteriosas dolinas. Con cerca de 30 torcas de tamaños que van desde la pequeña Torca de la Novia hasta la inmensa Torca Larga (más de 10 ha) o la impresionante Torca de las Colmenas (90 m de profundidad), este enclave sobrecoge por su belleza abrupta y su historia milenaria.La denominación de Tierra Muerta no es azarosa: aunque las lluvias son frecuentes, casi ninguna agua aflora en forma de manantial —toda se filtra hacia los acuíferos subterráneos—, dejando un entorno áspero, silencioso, donde la vegetación y la fauna sobreviven en equilibrio con la aridez.",
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/e/e7/Torcas_de_los_Palancares_-_Cuenca_-_Spain_-_panoramio.jpg"
    },  

    "LagunasCanadaHoyo": {
        "nombre": "Lagunas de Cañada del Hoyo",
        "lat": 39.98888093941978, 
        "lon": -1.8746057027507999,
        "descripcion": "Adéntrate en un paisaje kárstico único: siete lagunas circulares que emergen pujantes en un terreno calizo modelado por el agua y el tiempo. Cada una luce un color distinto—desde azules profundos hasta verdosos, negros o incluso lechosos—como una paleta viva al aire libre. Algunas acogen fenómenos naturales extraordinarios: la Laguna Gitana conserva estratos acuáticos inalterados, otras se tornan blancas por reacciones químicas y una ha llegado a enrojecer bajo la acción de microorganismos. Profundidades que superan los 30 m, vuelos sobre la roca viva, senderos accesibles y espacios protegidos: un rincón lleno de misterio, ciencia y belleza.",
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/0/05/Lagunas_de_Ca%C3%B1ada_del_Hoyo%2C_pan16_20101108_%285167346167%29.jpg"
    }, 

    "ChorrerasRioCabriel": {
        "nombre": "Las Chorreras del río Cabriel",
        "lat": 39.70466133418501, 
        "lon": -1.6191941477875167,
        "descripcion": "Descubre uno de los parajes más espectaculares de la Serranía de Cuenca: un tramo del río Cabriel que ha esculpido cascadas, pozas turquesa y cavernas tobáceas sobre piedra caliza. Este Monumento Natural, declarado en 2019, forma parte de la Reserva de la Biosfera del Valle del Cabriel y combina belleza geológica, aguas cristalinas y biodiversidad notable. Aunque el baño ahora está prohibido debido a recientes desprendimientos, se puede recorrer un sendero seguro (PR-CU-53) por la margen izquierda, con miradores impresionantes. Es un destino ideal para quienes buscan paisajes naturales, geología viva y fauna fluvial en estado casi salvaje.",
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Chorreras_de_Engu%C3%ADdanos_07.jpg"
    }, 

    "FachadaHarinas": {
        "nombre": "Fachada de la antigua Fábrica de Harinas",
        "lat": 39.898954262914344, 
        "lon": -1.8065016657198403,
        "descripcion": "Su arquitectura exterior transmite la solidez propia de la industria agroalimentaria de mediados del siglo pasado: una composición de múltiples plantas, ventanales ordenados que aseguran iluminación y ventilación en su interior, y una fusión de materiales como mampostería y ladrillo que otorgan carácter al edificio. Aunque hoy yace en estado de abandono, su fachada sigue evocando la vital actividad que un día albergó, y constituye un interesante vestigio del patrimonio industrial de Carboneras de Guadazaón",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/748dc62c925e45f6fab0fcd6ce2385968526ec1f/imagenes/FabricaHarinas.png"
    },  

    "Ruta1": {
        "nombre": "Ruta: Las Corveteras - Los Castellones - Castillo del Saladar (Pajaroncillo)",
        "lat": 39.95349525977749, 
        "lon": -1.7114109725881712,
        "descripcion": "Una excursión circular de cerca de 5,6 km y 3 horas de duración, que descubre rincones inolvidables de la Serranía Baja de Cuenca. Comienza atravesando pinares de rodeno, hasta alcanzar Los Castellones, con sus escarpadas formaciones rocosas y vistas al valle del Cabriel. El punto culminante lo ofrece el Castillo del Saladar, un antiguo castro celtibérico que guarda restos de murallas y aljibes tallados en la roca: su cumbre, accesible mediante cadenas, regala panorámicas memorables. El broche de oro llega al descender entre paisajes tallados por la erosión: “Las Corveteras”, chimeneas rocosas de formas caprichosas que evocan fantasía geológica. Tonos ocres bajo el sol, ecos de historia y el silencio del monte —esta ruta lo tiene todo.",
        "imagen_url": ""
    }, 

    "Ruta2": {
        "nombre": "Ruta: Selva Pascuala – Torre Barrachina – Torre Balbina",
        "lat": 39.92985933475362, 
        "lon": -1.672240749627503,
        "descripcion": "Un recorrido circular de unos 21 km, con un desnivel acumulado de 550 m, que se desarrolla entre los 951 m y los 1 172 m de altitud. Aunque la dificultad técnica es moderada, la distancia y el desnivel requieren buena condición física. El itinerario dura alrededor de 4 horas, incluido el tiempo para disfrutar los monumentos naturales e históricos que atraviesa. Comienza en el paraje de El Cañizar, accediendo por pista hasta el abrigo de arte rupestre levantino de Selva Pascuala, joya escenográfica e histórica. Prosigue hacia la Torre Barrachina, vestigio defensivo musulmán. El punto culminante es la Torre Balbina, una catedral de roca que remata en un mirador panorámico sobre el mar de pinos rodenos. Una experiencia ideal para quienes buscan viajar a través del tiempo, combinando arte milenario, arquitectura antigua y horizontes serranos en una ruta exigente pero fascinante.",
        "imagen_url": ""
    }, 

    "SaltoBalsa": {
        "nombre": "Salto de la Balsa",
        "lat": 40.0791327310064,
        "lon": -1.7769833334497602,
        "descripcion": "A sólo 2 km de Valdemoro-Sierra, este lugar mágico despliega una larga cascada tobácea de más de 50 m, donde el agua brota y se desliza por una roca porosa que forma charcas y arroyuelos antes de unirse al río Guadazaón. Su encanto reside en la extensión del salto más que en su altura. El acceso es sencillo: aparcamiento junto al puente sobre el Guadazaón y paseo de menos de 500 m hasta el mirador natural. El entorno está acondicionado con merendero, mesas y fuente. Primavera y época de lluvias exaltan su belleza; en invierno, el hielo lo transforma en un rincón de cuento.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/748dc62c925e45f6fab0fcd6ce2385968526ec1f/imagenes/ChorrerasValdemoro.png"
    },  

    "MiradorPicarcho": {
        "nombre": "Mirador del Picarcho",
        "lat": 39.895714368311324, 
        "lon": -1.8125385683922977,
        "descripcion": "A pocos pasos del centro de Carboneras de Guadazaón, este mirador privilegiado sobre el cordal ofrece vistas amplias del pueblo, los valles y montañas de la Serranía Baja. Al caer la tarde, el paisaje se tiñe de luz cálida, y por la noche —especialmente durante la fiesta de San Lorenzo— la oscuridad se convierte en un lienzo perfecto para las Perseidas, un espectáculo celestial que parece dibujarse en silencio en el firmamento. Ideal para una pausa contemplativa al aire libre, fotografía panorámica o simplemente para tomar aire: un lugar donde el cielo y la tierra se encuentran con magia. Si duermes en el pueblo, no olvides pasar por aquí: es mucho más que un mirador, es un puente hacia el infinito.",
        "imagen_url": "https://raw.githubusercontent.com/jorgeargudoo/RecomendadorTuristicoInteligente/748dc62c925e45f6fab0fcd6ce2385968526ec1f/imagenes/MiradorPicarcho.png"
    }  
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
            st.warning("No se encontraron lugares recomendados para ti. Por ello te mostramos todos.")
            mostrar_mapa_recomendaciones(LUGARES_INFO, LUGARES_INFO)
    
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





































