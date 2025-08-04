import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import joblib
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import requests
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
        resp = requests.get(
            f"{self.base_url}/prediccion/especifica/municipio/diaria/{id_municipio}",
            headers={"api_key": self.api_key}
        )
        return resp.json().get("datos")

    def get_datos_prediccion(self, datos_url):
        resp = requests.get(datos_url)
        return resp.json()[0]  # día de hoy

    def extraer_datos_relevantes(self, prediccion_dia):
        return {
            "fecha": prediccion_dia["fecha"],
            "tmax": int(prediccion_dia["temperatura"]["maxima"]),
            "tmin": int(prediccion_dia["temperatura"]["minima"]),
            "lluvia": int(prediccion_dia["probPrecipitacion"][0]["value"]) if prediccion_dia["probPrecipitacion"][0]["value"] else 0,
            "UV": int(prediccion_dia.get("uvMax", 5))  # valor por defecto si no hay UV
        }

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

def mostrar_mapa_recomendaciones(predicciones):
    m = folium.Map(location=[39.8667, -1.8167], zoom_start=13)
    for _, lugar in predicciones.iterrows():
        folium.Marker(
            [lugar['lat'], lugar['lon']],
            popup=f"{lugar['nombre']} - {lugar['descripcion']}"
        ).add_to(m)
    st_folium(m, width=700, height=500)

def formulario_usuario():
    st.write("Por favor, rellena este formulario para obtener recomendaciones personalizadas:")

    edad = st.slider("¿Cuál es tu edad?", 10, 80, 25)
    genero = st.selectbox("¿Cuál es tu género?", ["Hombre", "Mujer", "Otro"])
    genero_cod = 0 if genero == "Hombre" else 1 if genero == "Mujer" else 0.5

    residencia_opciones = ["Sí, todo el año", "Solo en verano o en vacaciones", "No, pero soy de aquí", "No"]
    residencia = st.selectbox("¿Vives en Carboneras?", residencia_opciones)
    residencia_dict = {op: 0 for op in residencia_opciones}
    residencia_dict[residencia] = 1

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
    
LUGARES_EXTERIOR = {"castillo_aliaga", "parque_natural", "mirador_sierra"}

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
        # Crear input como DataFrame de una fila
        df_usuario = pd.DataFrame([datos_usuario])
        
        # Predecir con el modelo cargado
        modelo_recomendador = cargar_modelo()
        predicciones_binarias = modelo_recomendador.predict(df_usuario)[0]
        
        # Extraer los nombres de lugares a partir de las columnas del modelo
        lugares = [col.replace("valoracion_", "") for col in modelo_recomendador.estimators_[0].classes_]
        recomendaciones_dict = {lugar: int(pred) for lugar, pred in zip(lugares, predicciones_binarias)}
        
        # Intentar obtener clima desde AEMET
        API_KEY_AEMET = st.secrets["API_KEY_AEMET"]
        aemet = AEMET(api_key=API_KEY_AEMET)
        clima_hoy = None
        try:
            datos_url = aemet.get_prediccion_url("16064")  # ID de Carboneras de Guadazaón
            prediccion_dia = aemet.get_datos_prediccion(datos_url)
            clima_hoy = aemet.extraer_datos_relevantes(prediccion_dia)
            recomendaciones_filtradas = filtrar_por_clima(recomendaciones_dict, clima_hoy)
            st.info(f"Filtrado climático aplicado. Score exterior: {recomendar(clima_hoy):.2f}")
        except Exception as e:
            recomendaciones_filtradas = recomendaciones_dict
            st.warning("No se pudo obtener el clima actual desde AEMET. Las recomendaciones no han sido filtradas por condiciones meteorológicas.")
        
        # Mostrar lugares recomendados
        lugares_recomendados = [lugar for lugar, v in recomendaciones_filtradas.items() if v == 1]
        
        st.success("Lugares recomendados según tus gustos y el clima actual:" if clima_hoy else "Lugares recomendados según tus gustos:")
        for lugar in lugares_recomendados:
            st.write(f"- {lugar}")

        st.success("¡Recomendaciones generadas!")
        mostrar_mapa_recomendaciones(predicciones_finales)
        feedback = st.slider("¿Qué valoración darías a estas recomendaciones?", min_value=1, max_value=5, value=3)
        st.write("Tu valoración:", "⭐" * feedback)
        if st.button("Enviar valoración"):
            # log_event("feedback", {"satisfaccion": feedback})
            st.success(f"¡Gracias por tu valoración de {feedback} estrellas!")
elif pagina == "Servicios":
    mostrar_servicios()
elif pagina == "Sobre nosotros":
    mostrar_sobre_nosotros()

