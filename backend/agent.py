from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generar_rutina_inteligente(objetivo, pasos, sueno, historial):

    contexto = f"""
Eres un entrenador personal inteligente.

Datos del usuario:
- Objetivo: {objetivo}
- Pasos hoy: {pasos}
- Horas de sueño: {sueno}

Historial reciente:
{historial}

Tareas:
1. Analiza el estado del usuario
2. Decide nivel de intensidad (baja, media, alta)
3. Genera una rutina completa (ejercicios + tiempo)
4. Justifica brevemente la decisión

Responde en formato JSON así:
{{
  "intensidad": "",
  "rutina": [],
  "justificacion": ""
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": contexto}],
        temperature=0.7
    )

    contenido = response.choices[0].message.content

    # 🔥 limpiar si viene con ```json
    if "```" in contenido:
        contenido = contenido.split("```")[1]
        contenido = contenido.replace("json", "").strip()

    try:
        return json.loads(contenido)
    except:
        return {"error": contenido}
