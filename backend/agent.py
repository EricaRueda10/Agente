from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import unicodedata

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CAMPO_OBLIGATORIOS = [
    "edad",
    "estatura",
    "peso",
    "objetivo",
    "dias_disponibles",
]


def _limpiar_y_parsear_json(contenido):
    if "```" in contenido:
        partes = contenido.split("```")
        if len(partes) >= 2:
            contenido = partes[1]
        contenido = contenido.replace("json", "").strip()

    try:
        return json.loads(contenido)
    except Exception:
        return {"error": contenido}


def _perfil_completo(perfil):
    return all(
        perfil.get("edad")
        and perfil.get("estatura")
        and perfil.get("peso")
        and perfil.get("objetivo")
        and perfil.get("dias_disponibles")
    )


def _normalizar_perfil(perfil):
    return {
        "edad": perfil.get("edad"),
        "estatura": perfil.get("estatura"),
        "peso": perfil.get("peso"),
        "objetivo": perfil.get("objetivo") or "",
        "dias_disponibles": perfil.get("dias_disponibles"),
    }


def _campos_faltantes(perfil):
    faltan = []
    for campo in CAMPO_OBLIGATORIOS:
        valor = perfil.get(campo)
        if valor is None or valor == "":
            faltan.append(campo)
    return faltan


def _normalizar_texto(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return texto


def _extraer_preferencias_chat(historial_chat):
    texto_usuario = " ".join(
        m.get("content", "") for m in historial_chat if m.get("role") == "user"
    )
    texto = _normalizar_texto(texto_usuario)

    equipamiento = []
    formatos = []
    restricciones = []

    if "mancuerna" in texto or "mancuernas" in texto:
        equipamiento.append("mancuernas")
    if "maquina" in texto or "maquinas" in texto:
        equipamiento.append("maquinas")
    if "barra" in texto:
        equipamiento.append("barra")
    if "peso corporal" in texto or "calistenia" in texto:
        equipamiento.append("peso_corporal")
    if "banda" in texto or "bandas" in texto or "liga" in texto:
        equipamiento.append("bandas")

    if "tabata" in texto:
        formatos.append("tabata")
    if "hiit" in texto:
        formatos.append("hiit")
    if "circuito" in texto:
        formatos.append("circuito")
    if "hipertrof" in texto:
        formatos.append("hipertrofia")
    if "fuerza" in texto:
        formatos.append("fuerza")

    if "sin salto" in texto or "sin saltos" in texto:
        restricciones.append("sin_saltos")
    if "bajo impacto" in texto:
        restricciones.append("bajo_impacto")
    if "rodilla" in texto:
        restricciones.append("cuidar_rodilla")
    if "espalda" in texto and "dolor" in texto:
        restricciones.append("cuidar_espalda")

    return {
        "equipamiento": sorted(list(set(equipamiento))),
        "formatos": sorted(list(set(formatos))),
        "restricciones": sorted(list(set(restricciones))),
        "texto_libre": texto_usuario.strip(),
    }


def _generar_planes_por_intensidad(perfil, preferencias):
    contexto = f"""
Eres un Fit Coach profesional.

Perfil confirmado:
- edad: {perfil.get("edad")}
- estatura: {perfil.get("estatura")} cm
- peso: {perfil.get("peso")} kg
- objetivo: {perfil.get("objetivo")}
- dias_disponibles: {perfil.get("dias_disponibles")}

Preferencias detectadas desde el chat del usuario:
- equipamiento: {preferencias.get("equipamiento")}
- formatos: {preferencias.get("formatos")}
- restricciones: {preferencias.get("restricciones")}
- texto_libre: {preferencias.get("texto_libre")}

Responde SOLO JSON valido con esta estructura exacta:
{{
    "mensaje_coach": "",
    "planes_por_intensidad": {{
        "baja": {{"justificacion": "", "dias": []}},
        "media": {{"justificacion": "", "dias": []}},
        "alta": {{"justificacion": "", "dias": []}}
    }}
}}

Formato de cada dia:
{{
    "dia": "Dia 1",
    "grupo_muscular": "Pecho y triceps",
    "foco": "Hipertrofia tecnica",
    "ejercicios": [
        {{
            "grupo_muscular": "Pecho",
            "ejercicio": "Press de banca",
            "series_reps": "4x8",
            "descanso": "90s",
            "instrucciones": "",
            "tips": "",
            "video_busqueda": "Press de banca tecnica",
            "imagen_referencia": ""
        }}
    ]
}}

Reglas:
1. En cada intensidad crea exactamente {perfil.get("dias_disponibles")} dias.
2. Cada dia debe tener 4 a 6 ejercicios.
3. Ajusta volumen y exigencia segun intensidad (baja, media, alta).
4. Mantener recomendaciones seguras y progresivas.
5. Si el usuario pide "solo mancuernas", TODOS los ejercicios deben ser con mancuernas.
6. Si el usuario pide "solo maquinas", TODOS los ejercicios deben ser de maquinas.
7. Si el usuario pide TABATA, la rutina debe usar estructura TABATA (bloques por intervalos) y ejercicios compatibles.
8. Respeta restricciones detectadas (ej: sin saltos, bajo impacto, cuidar rodilla).
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": contexto}],
        temperature=0.4,
    )
    contenido = response.choices[0].message.content
    return _limpiar_y_parsear_json(contenido)


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
        temperature=0.7,
    )

    contenido = response.choices[0].message.content
    return _limpiar_y_parsear_json(contenido)


def generar_plan_conversacional(perfil, historial_chat):
    contexto = f"""
Actua como Fit Coach profesional con enfoque en seguridad y progresion.

Debes conducir una conversacion para obtener estos campos obligatorios:
- edad
- estatura (cm)
- peso (kg)
- objetivo
- dias_disponibles (dias por semana para entrenar)

Perfil parcial actual (puede venir incompleto):
{perfil}

Historial de conversacion completo:
{historial_chat}

Responde SOLO JSON valido con esta estructura exacta:
{{
    "mensaje_coach": "",
    "estado": "faltan_datos|rutina_lista",
    "campos_faltantes": ["edad", "estatura", "peso", "objetivo", "dias_disponibles"],
    "perfil_detectado": {{
        "edad": null,
        "estatura": null,
        "peso": null,
        "objetivo": "",
        "dias_disponibles": null
    }},
    "planes_por_intensidad": {{
        "baja": {{"justificacion": "", "dias": []}},
        "media": {{"justificacion": "", "dias": []}},
        "alta": {{"justificacion": "", "dias": []}}
    }},
    "preferencias_detectadas": {{
        "equipamiento": [],
        "formatos": [],
        "restricciones": []
    }}
}}

Formato de cada item en planes_por_intensidad.<intensidad>.dias:
{{
    "dia": "Dia 1",
    "grupo_muscular": "Pecho y triceps",
    "foco": "Hipertrofia tecnica",
    "ejercicios": [
        {{
            "grupo_muscular": "Pecho",
            "ejercicio": "Press de banca",
            "series_reps": "4x8",
            "descanso": "90s",
            "instrucciones": "",
            "tips": "",
            "video_busqueda": "Press de banca tecnica",
            "imagen_referencia": ""
        }}
    ]
}}

Reglas:
1. Si faltan datos, NO generes rutina: estado=faltan_datos, planes vacios y mensaje_coach pidiendo solo los campos faltantes en lenguaje natural.
2. Si ya tienes todos los datos, estado=rutina_lista y genera 3 planes (baja/media/alta).
3. Cada plan debe tener exactamente tantos dias como dias_disponibles.
4. En cada dia incluye 4 a 6 ejercicios.
5. Mantener recomendaciones seguras y progresivas.
6. En video_busqueda dejar texto de busqueda para YouTube.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": contexto}],
        temperature=0.6,
    )

    contenido = response.choices[0].message.content
    resultado = _limpiar_y_parsear_json(contenido)

    if "error" in resultado:
        return resultado

    perfil_detectado = _normalizar_perfil(resultado.get("perfil_detectado", {}))
    perfil_entrada = _normalizar_perfil(perfil or {})
    perfil_final = {
        "edad": perfil_entrada.get("edad") or perfil_detectado.get("edad"),
        "estatura": perfil_entrada.get("estatura") or perfil_detectado.get("estatura"),
        "peso": perfil_entrada.get("peso") or perfil_detectado.get("peso"),
        "objetivo": perfil_entrada.get("objetivo") or perfil_detectado.get("objetivo"),
        "dias_disponibles": perfil_entrada.get("dias_disponibles") or perfil_detectado.get("dias_disponibles"),
    }

    faltantes = _campos_faltantes(perfil_final)
    preferencias = _extraer_preferencias_chat(historial_chat)

    if not faltantes:
        planes = _generar_planes_por_intensidad(perfil_final, preferencias)
        if "error" in planes:
            return planes

        return {
            "mensaje_coach": planes.get("mensaje_coach") or "Perfecto, aqui tienes tu plan personalizado por intensidad.",
            "estado": "rutina_lista",
            "campos_faltantes": [],
            "perfil_detectado": perfil_final,
            "preferencias_detectadas": preferencias,
            "planes_por_intensidad": planes.get("planes_por_intensidad", {
                "baja": {"justificacion": "", "dias": []},
                "media": {"justificacion": "", "dias": []},
                "alta": {"justificacion": "", "dias": []},
            }),
        }

    return {
        "mensaje_coach": resultado.get("mensaje_coach") or "Necesito algunos datos mas para preparar tu plan.",
        "estado": "faltan_datos",
        "campos_faltantes": faltantes,
        "perfil_detectado": perfil_final,
        "preferencias_detectadas": preferencias,
        "planes_por_intensidad": {
            "baja": {"justificacion": "", "dias": []},
            "media": {"justificacion": "", "dias": []},
            "alta": {"justificacion": "", "dias": []},
        },
    }
