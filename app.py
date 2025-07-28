import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from logger_gsheets import log_event  # Importa nuestra función de logging

# -------------------------
# CONFIGURACIÓN INICIAL
# -------------------------
st.set_page_config(page_title="Turismo en Carboneras de Guadazaón", layout="wide")

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

    # Edad
    edad = st.slider("¿Cuál es tu edad?", 10, 80, 25)

    # Género
    genero = st.selectbox("¿Cuál es tu género?", ["Hombre", "Mujer", "Otro"])
    if genero == "Hombre":
        genero_cod = 0
    elif genero == "Mujer":
        genero_cod = 1
    else:
        genero_cod = 0.5  # Valor neutro

    # Residencia (one-hot)
    residencia_opciones = ["Sí, todo el año", "Solo en verano o en vacaciones", "No, pero soy de aquí", "No"]
    residencia = st.selectbox("¿Vives en Carboneras?", residencia_opciones)
    residencia_dict = {op: 0 for op in residencia_opciones}
    residencia_dict[residencia] = 1

    # Frecuencia de actividades turísticas (map 0-3)
    actividad_opciones = ["Solo en fiestas o vacaciones", "De vez en cuando", "Varias veces por semana", "A diario"]
    freq_actividad = st.selectbox("¿Con qué frecuencia realizas actividades turísticas?", actividad_opciones)
    actividad_map = {actividad_opciones[i]: i for i in range(len(actividad_opciones))}
    freq_actividad_cod = actividad_map[freq_actividad]

    # Frecuencia de recomendaciones (1 a 5)
    freq_recom_opciones = ["Nunca", "Pocas veces", "A veces", "A menudo", "Siempre"]
    freq_recom = st.selectbox("¿Con qué frecuencia recomiendas actividades a otras personas?", freq_recom_opciones)
    freq_recom_map = {freq_recom_opciones[i]: i + 1 for i in range(len(freq_recom_opciones))}
    freq_recom_cod = freq_recom_map[freq_recom]

        # Actividades recomendadas por grupos
    actividades_disponibles = [
        "Naturaleza y paseos", "Rutas", "Monumentos o historia",
        "Sitios tranquilos para descansar", "Eventos o fiestas",
        "Bares y restaurantes"
    ]
    
    st.subheader("¿Qué actividades recomendarías a familias?")
    actividades_familias = st.multiselect(
        "Selecciona actividades para familias",
        actividades_disponibles,
        key="familias"
    )
    
    st.subheader("¿Qué actividades recomendarías a jóvenes?")
    actividades_jovenes = st.multiselect(
        "Selecciona actividades para jóvenes",
        actividades_disponibles,
        key="jovenes"
    )
    
    st.subheader("¿Qué actividades recomendarías a mayores?")
    actividades_mayores = st.multiselect(
        "Selecciona actividades para mayores",
        actividades_disponibles,
        key="mayores"
    )
    # Codificar actividades como columnas binarias
    def codificar_actividades(actividades_seleccionadas, grupo):
        return {f"{grupo}_{actividad}": 1 if actividad in actividades_seleccionadas else 0
                for actividad in actividades_disponibles}

    recom_familias = codificar_actividades(actividades_familias, "recom_familias")
    recom_jovenes = codificar_actividades(actividades_jovenes, "recom_jovenes")
    recom_mayores = codificar_actividades(actividades_mayores, "recom_mayores")

    # Crear un diccionario con todas las variables
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
# log_event("navegacion", {"opcion": opcion})

if opcion == "Sistema inteligente de recomendación turística":
    st.header("Recomendador turístico")
    datos_usuario = formulario_usuario()

    if st.button("Obtener recomendaciones"):
        # log_event("cuestionario", datos_usuario)

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
        # log_event("recomendaciones", {"lugares": predicciones_finales["nombre"].tolist()})

        # Feedback
        feedback = st.slider(
            "¿Qué valoración darías a estas recomendaciones?",
            min_value=1,
            max_value=5,
            value=3
        )
        st.write("Tu valoración:", "⭐" * feedback)
        
        if st.button("Enviar valoración"):
            log_event("feedback", {"satisfaccion": feedback})
            st.success(f"¡Gracias por tu valoración de {feedback} estrellas!")


elif opcion == "Descubre Carboneras de Guadazaón":
    mostrar_informacion_local()
