import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
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

if pagina == "Descubre Carboneras de Guadazaón":
    mostrar_informacion_local()
elif pagina == "Recomendador turístico":
    st.header("Recomendador turístico")
    datos_usuario = formulario_usuario()
    if st.button("Obtener recomendaciones"):
        predicciones_finales = pd.DataFrame([
            {"nombre": "Castillo de Aliaga", "lat": 39.867, "lon": -1.818, "descripcion": "Castillo medieval."},
            {"nombre": "Parque Natural", "lat": 39.865, "lon": -1.815, "descripcion": "Senderos y áreas verdes."}
        ])
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
