# Recomendador Turístico Inteligente para Carboneras de Guadazaón

Aplicación web interactiva desarrollada como parte del **Trabajo Fin de Grado en Ciencia de Datos (UPV)**.  
El sistema ofrece **recomendaciones turísticas personalizadas** combinando un modelo de **aprendizaje automático supervisado**, un **filtro climático basado en lógica difusa** y datos meteorológicos en tiempo real.

---

## 1. Objetivo del proyecto

El objetivo principal es diseñar e implementar un **sistema de recomendación turística inteligente** que:

- Adapte las recomendaciones al **perfil del usuario**.
- Tenga en cuenta las **condiciones meteorológicas actuales**.
- Priorice la **usabilidad**, la **interpretabilidad** y la **reproducibilidad**.
- Sirva como caso de estudio real de aplicación de técnicas de Ciencia de Datos.

---

## 2. Descripción funcional

El sistema sigue un flujo de decisión en dos etapas:

1. **Predicción basada en perfil del usuario**  
   Un modelo de machine learning multi-salida predice la idoneidad de distintos puntos de interés a partir de las respuestas del usuario.

2. **Filtrado climático mediante lógica difusa**  
   Se evalúa la conveniencia de actividades al aire libre usando:
   - Temperatura máxima y mínima
   - Probabilidad de precipitación
   - Índice UV  

   En función de este análisis, se priorizan o descartan recomendaciones de exterior.

Finalmente, las recomendaciones se muestran en un **mapa interactivo**, junto con información contextual de cada lugar.

---

## 3. Arquitectura del sistema

El proyecto se estructura en los siguientes módulos:

- **Interfaz de usuario**: aplicación web con Streamlit.
- **Modelo de recomendación**: modelo entrenado previamente y cargado en producción.
- **Sistema de lógica difusa**: evaluación de idoneidad climática.
- **Servicios externos**: obtención de datos meteorológicos.
- **Registro de eventos**: almacenamiento de interacciones anónimas para análisis posterior.

---

## 4. Descripción de los archivos principales

### 4.1 `app.py`

Archivo principal que ejecuta la aplicación Streamlit.  
Incluye:

- Definición de la interfaz de usuario.
- Recogida de datos mediante formularios.
- Carga y uso del modelo de recomendación.
- Implementación del sistema de lógica difusa.
- Integración con APIs meteorológicas (AEMET y OpenUV).
- Visualización de resultados mediante mapas interactivos.
- Gestión de sesión y cookies.
- Registro de eventos de uso y feedback del usuario.

---

### 4.2 `logger_gsheets.py`

Módulo encargado del **registro de eventos anónimos** en Google Sheets, entre ellos:

- Envío del formulario.
- Predicciones generadas.
- Condiciones meteorológicas consultadas.
- Valoraciones del usuario.

Este registro permite analizar el uso del sistema y evaluar su funcionamiento.

---

### 4.3 `modelo_turismo.pkl`

Archivo serializado que contiene el **modelo de aprendizaje automático entrenado** a partir de datos de encuestas.  
Se utiliza en la fase de predicción para determinar qué lugares son adecuados para cada perfil.

---

### 4.4 `imagenes/`

Directorio con las imágenes empleadas en la interfaz para enriquecer la experiencia visual y contextualizar las recomendaciones.

---

## 5. Tecnologías utilizadas

- **Lenguaje**: Python  
- **Interfaz**: Streamlit  
- **Machine Learning**: scikit-learn  
- **Lógica difusa**: scikit-fuzzy  
- **Visualización geográfica**: Folium  
- **Persistencia de eventos**: Google Sheets API  
- **Otras librerías**: pandas, numpy, joblib, requests

---

## 6. Configuración y reproducibilidad

La aplicación requiere definir variables sensibles mediante `secrets.toml` (Streamlit):

```toml
API_KEY_AEMET = "TU_API_KEY"
API_KEY_OPENUV = "TU_API_KEY"
COOKIE_PASSWORD = "PASSWORD_SEGURA"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."

