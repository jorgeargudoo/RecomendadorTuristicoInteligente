import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from logger import log_event  # Importa nuestra función de logging

# -------------------------
# CONFIGURACIÓN INICIAL
# -------------------------
st.set_page_config(page_title="Turismo Carboneras de Guadazaón", layout="wide")

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
    genero = st.selectbox("¿Cuál es tu género?", ["Hombre", "Mujer"])
    residencia = st.selectbox("¿Vives en Carboneras?", ["Sí", "No"])
    freq_actividad = st.selectbox("¿Con qué frecuencia realizas actividades turísticas?",
                                  ["Solo en fiestas o vacaciones", "De vez en cuando",
                                   "Varias veces por semana", "A diario"])
    freq_recom = st.selectbox("¿Con qué frecuencia recomiendas actividades a otras personas?",
                              ["Nunca", "Pocas veces", "A menudo", "Siempre"])
    actividades = st.multiselect(
        "¿Qué actividades recomendarías a familias?",
        ["Senderismo", "Museos", "Restaurantes", "Parques"]
    )

    datos_usuario = {
        "edad": edad,
        "genero": genero,
        "residencia": residencia,
        "freq_actividad": freq_actividad,
        "freq_recom": freq_recom,
        "actividades_familias": actividades
    }
    return datos_usuario

def mostrar_informacion_local():
    st.header("Descubre Carboneras de Guadazaón")
    st.subheader("Bares y Restaurantes")
    st.write("- Bar La Plaza\n- Restaurante Los Amigos\n- Café Sol")
    st.subheader("Hostales y Alojamiento")
    st.write("- Hostal El Molino\n- Posada del Pueblo")
    st.subheader("Actividades")
    st.write("• Rutas de senderismo\n• Talleres de cerámica\n• Degustación de productos locales")
    st.subheader("Semana Cultural")
    st.write("Durante la última semana de agosto, se realizan actividades culturales, conciertos y mercados artesanales.")
    st.subheader("Domingo de Procesiones en Mayo")
    st.write("Se celebra con desfiles tradicionales y música en vivo.")
    st.subheader("Lugares de interés")
    st.write("Aquí aparecerá la lista de todos los lugares con su información. (Opcional: botón 'Ver en el mapa')")

# -------------------------
# CUERPO PRINCIPAL
# -------------------------
st.title("Portal Turístico de Carboneras de Guadazaón")

opcion = st.radio("Selecciona una opción:", 
                  ["Sistema inteligente de recomendación turística", "Descubre Carboneras de Guadazaón"])

# Log de selección
log_event("navegacion", {"opcion": opcion})

if opcion == "Sistema inteligente de recomendación turística":
    st.header("Recomendador turístico")
    datos_usuario = formulario_usuario()

    if st.button("Obtener recomendaciones"):
        log_event("cuestionario", datos_usuario)

        # [ESPACIO MODELO] Aquí cargarás el modelo
        # predicciones_modelo = modelo.predict(datos_usuario_transformado)

        # [ESPACIO LÓGICA DIFUSA] Aquí aplicarás las reglas
        # predicciones_finales = aplicar_logica_difusa(predicciones_modelo)

        # DEMO DE PREDICCIONES
        predicciones_finales = pd.DataFrame([
            {"nombre": "Castillo de Aliaga", "lat": 39.867, "lon": -1.818, "descripcion": "Castillo medieval."},
            {"nombre": "Parque Natural", "lat": 39.865, "lon": -1.815, "descripcion": "Senderos y áreas verdes."}
        ])
        st.success("¡Recomendaciones generadas!")
        mostrar_mapa_recomendaciones(predicciones_finales)
        log_event("recomendaciones", {"lugares": predicciones_finales["nombre"].tolist()})

        # Feedback
        feedback = st.radio("¿Te resultaron útiles estas recomendaciones?", ["Sí", "No"])
        if st.button("Enviar feedback"):
            log_event("feedback", {"satisfaccion": feedback})
            st.success("¡Gracias por tu opinión!")

elif opcion == "Descubre Carboneras de Guadazaón":
    mostrar_informacion_local()
