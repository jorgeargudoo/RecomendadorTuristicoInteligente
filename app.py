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

    for clave in lugares_recomendados:
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
        "lat": 39.901,  # aproximado desde waymarking GPS: N 39° 54.058 → 39.901; W 1° 48.786 → -1.8131:contentReference[oaicite:1]{index=1}
        "lon": -1.8131,
        "descripcion": "Iglesia medieval (siglos XIII‑XIV) con techos mudéjares, portada isabelina y espadaña herreriana.",
        "imagen_url": ""
    },
    "PanteonMarquesesMoya": {
        "nombre": "Iglesia‑Panteón de los Marqueses de Moya",
        "lat": 39.901,  # misma ubicación aproximada que la iglesia anterior
        "lon": -1.8131,
        "descripcion": "Templo gótico‑isabelino donde descansan los fundadores dominicos, tumba de los Marqueses de Moya.",
        "imagen_url": ""
    },
    "CastilloAliaga": {
        "nombre": "Castillo de Aliaga",
        "lat": 39.90,  # aproximado según ruta y descripciones visuales:contentReference[oaicite:2]{index=2}
        "lon": -1.82,
        "descripcion": "Ruinas medievales en colina (1 044 m alt.) con restos de murallas escalonadas de planta irregular.",
        "imagen_url": ""
    },
    "LagunaCaolin": {
        "nombre": "Laguna de Caolín",
        "lat": 39.90,  # aproximado dentro del entorno de Carboneras
        "lon": -1.82,
        "descripcion": "Antigua cantera convertida en laguna turquesa, paisaje natural llamativo.",
        "imagen_url": ""
    },
    "RiberaRioGuadazaon": {
        "nombre": "Ribera del Río Guadazaón",
        "lat": 39.883,  # coordenadas de Carboneras como referencia justa
        "lon": -1.800,
        "descripcion": "Tramo de ribera agrícola junto al río Guadazaón: huertas, flora de ribera y paseo tranquilo.",
        "imagen_url": ""
    },
    "CerritoArena": {
        "nombre": "Cerrito de la Arena",
        "lat": 39.883,  # estimado cerca del entorno urbano
        "lon": -1.800,
        "descripcion": "Cerro y yacimiento neolítico con hallazgos de útiles prehistóricos (mazos de piedra).",
        "imagen_url": ""
    },
    "MiradorCruz": {
        "nombre": "Mirador de la Cruz",
        "lat": 39.90,  # estimado loma cercana
        "lon": -1.80,
        "descripcion": "Mirador panorámico sobre la loma con cruz, vistas de campos y montes serranos.",
        "imagen_url": ""
    },
    "FuenteTresCanos": {
        "nombre": "Fuente de los Tres Caños",
        "lat": 39.883,  # centro urbano
        "lon": -1.800,
        "descripcion": "Fuente pública con tres caños y pilón en el pueblo, antiguo punto de abrevadero.",
        "imagen_url": ""
    },
    "PuenteCristinasRioCabriel": {
        "nombre": "Puente de las Cristinas (río Cabriel)",
        "lat": 39.89,  # aproximado entre Carboneras y Pajaroncillo:contentReference[oaicite:3]{index=3}
        "lon": -1.79,
        "descripcion": "Puente del siglo XVI sobre el Cabriel, financiado por dominicos, restaurado recientemente.",
        "imagen_url": ""
    },
    "TorcasPalancaresTierraMuerta": {
        "nombre": "Torcas de Palancares / Tierra Muerta",
        "lat": 39.95,  # aproximado Serranía de Cuenca
        "lon": -1.80,
        "descripcion": "Monumento Natural: 22 dolinas kársticas profundas en zona forestal protegida.",
        "imagen_url": ""
    },
    "LagunasCanadaHoyo": {
        "nombre": "Lagunas de Cañada del Hoyo",
        "lat": 39.9846,  # desde Panoramio GPS:contentReference[oaicite:4]{index=4}
        "lon": -1.8734,
        "descripcion": "Complejo de lagunas kársticas multicolor, Monumento Natural declarado en 2007.",
        "imagen_url": ""
    },
    "ChorrerasRioCabriel": {
        "nombre": "Las Chorreras del río Cabriel",
        "lat": 39.95,  # estimado entre Enguídanos y Víllora
        "lon": -1.70,
        "descripcion": "Cascadas, pozas turquesas y senderos junto al Cabriel, entorno geológico singular.",
        "imagen_url": ""
    },
    "FachadaHarinas": {
        "nombre": "Fachada de la antigua fábrica de harinas",
        "lat": 39.883,  # centro urbano
        "lon": -1.800,
        "descripcion": "Imponente fachada industrial de la vieja fábrica (1948), ahora en desuso.",
        "imagen_url": ""
    },
    "Ruta1": {
        "nombre": "Sendero Hoz del río Algarra",
        "lat": 39.87,  # aproximado entorno del río afluente
        "lon": -1.82,
        "descripcion": "Sendero por la hoz del río Algarra entre vegetación de ribera y roquedo.",
        "imagen_url": ""
    },
    "Ruta2": {
        "nombre": "Ruta de los molinos de agua",
        "lat": 39.883,
        "lon": -1.800,
        "descripcion": "Ruta para descubrir antiguos molinos hidráulicos junto al cauce y huertas del pueblo.",
        "imagen_url": ""
    },
    "SaltoBalsa": {
        "nombre": "Salto de la Balsa",
        "lat": 39.90,  # ubicación aproximada entorno húmedo
        "lon": -1.78,
        "descripcion": "Pequeña cascada y pozas naturales en el arroyo la Balsa en entorno boscoso.",
        "imagen_url": ""
    },
    "MiradorPicarcho": {
        "nombre": "Mirador del Picarcho",
        "lat": 39.967,  # coordenadas de Cañada del Hoyo → asumir cerro cercano:contentReference[oaicite:5]{index=5}
        "lon": -1.900,
        "descripcion": "Mirador en cerro con vistas panorámicas y yacimiento arqueológico de Edad del Bronce.",
        "imagen_url": ""
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
    if st.button("Obtener recomendaciones"):
        # Asegurarse de que las columnas de entrada coincidan con las del modelo
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

        # Predecir con el modelo cargado
        modelo_recomendador = cargar_modelo()
        predicciones_binarias = modelo_recomendador.predict(df_usuario)[0]
        
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

        recomendaciones_dict = {lugar: int(pred) for lugar, pred in zip(lugares, predicciones_binarias)}
        
        # Intentar obtener clima desde AEMET
        clima_hoy = None
        try:
            clima_hoy = obtener_clima_hoy()  # usa la función cacheada
            recomendaciones_filtradas = filtrar_por_clima(recomendaciones_dict, clima_hoy)
            st.info(f"Filtrado climático aplicado. Score exterior: {recomendar(clima_hoy):.2f}")
        except Exception as e:
            recomendaciones_filtradas = recomendaciones_dict
            st.warning("No se pudo obtener el clima actual. Las recomendaciones no han sido filtradas por condiciones meteorológicas.")
            st.text(f"Error: {str(e)}")
        # Guardar resultados en session_state
        st.session_state.lugares_recomendados = [lugar for lugar, v in recomendaciones_filtradas.items() if v == 1]
        st.session_state.clima_hoy = clima_hoy
        st.session_state.mostrar_resultados = True
        
        # Mostrar mensaje de éxito
        st.success(
            "Lugares recomendados según tus gustos y el clima actual:"
            if st.session_state.clima_hoy else "Lugares recomendados según tus gustos:"
        )
        
        # Mostrar mapa con marcadores interactivos
        mostrar_mapa_recomendaciones(st.session_state.lugares_recomendados, LUGARES_INFO)
        
        # Feedback interactivo
        feedback = st.slider("¿Qué valoración darías a estas recomendaciones?", min_value=1, max_value=5, value=3)
        st.write("Tu valoración:", "⭐" * feedback)
        
        if st.button("Enviar valoración"):
            # log_event("feedback", {"satisfaccion": feedback})
            st.success(f"¡Gracias por tu valoración de {feedback} estrellas!")
        
        # Botón para reiniciar (opcional)
        if st.button("Volver a empezar"):
            st.session_state.clear()
            st.experimental_rerun()

elif pagina == "Servicios":
    mostrar_servicios()
elif pagina == "Sobre nosotros":
    mostrar_sobre_nosotros()












