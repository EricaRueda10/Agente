from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import unicodedata
import re
import time
import copy

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=20.0, max_retries=0)
PLAN_CACHE_TTL = 900
_PLAN_CACHE = {}
_DAY_DETAIL_CACHE = {}

CAMPO_OBLIGATORIOS = [
    "edad",
    "estatura",
    "peso",
    "objetivo",
    "dias_disponibles",
]


def _limpiar_y_parsear_json(contenido):
    texto = contenido.strip()

    if "```" in texto:
        partes = texto.split("```")
        if len(partes) >= 2:
            texto = partes[1]
        texto = texto.replace("json", "").strip()

    candidatos = [texto]
    inicio_objeto = texto.find("{")
    final_objeto = texto.rfind("}")
    if inicio_objeto != -1 and final_objeto != -1 and final_objeto > inicio_objeto:
        candidatos.append(texto[inicio_objeto : final_objeto + 1])

    inicio_array = texto.find("[")
    final_array = texto.rfind("]")
    if inicio_array != -1 and final_array != -1 and final_array > inicio_array:
        candidatos.append(texto[inicio_array : final_array + 1])

    for candidato in candidatos:
        try:
            return json.loads(candidato)
        except Exception:
            continue

    return {"error": texto}


def _rescatar_json_desde_error(valor_error):
    if not isinstance(valor_error, str):
        return None

    texto = valor_error.strip()
    if not texto:
        return None

    for simbolo_inicio, simbolo_fin in (("{", "}"), ("[", "]")):
        inicio = texto.find(simbolo_inicio)
        final = texto.rfind(simbolo_fin)
        if inicio == -1 or final == -1 or final <= inicio:
            continue

        fragmento = texto[inicio : final + 1]
        try:
            decodificador = json.JSONDecoder()
            recuperado, _ = decodificador.raw_decode(fragmento)
            if isinstance(recuperado, dict) and "error" not in recuperado:
                return recuperado
            if isinstance(recuperado, list):
                return {"planes_por_intensidad": recuperado}
        except Exception:
            recuperado = _limpiar_y_parsear_json(fragmento)
            if isinstance(recuperado, dict) and "error" not in recuperado:
                return recuperado

    return None


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
    equipamiento = []
    formatos = []
    restricciones = []
    mensajes_usuario = [m.get("content", "") for m in historial_chat if m.get("role") == "user"]
    for mensaje in mensajes_usuario:
        texto = _normalizar_texto(mensaje)

        if any(
            frase in texto
            for frase in (
                "sin ninguna preferencia",
                "sin preferencia",
                "reinicia la rutina",
                "reinicia rutina",
                "reiniciar la rutina",
                "quitar preferencias",
                "quita preferencias",
            )
        ):
            equipamiento = []
            formatos = []
            restricciones = []

        if "mancuerna" in texto or "mancuernas" in texto:
            equipamiento = ["mancuernas"]
        if "maquina" in texto or "maquinas" in texto:
            equipamiento = ["maquinas"]
        if "barra" in texto:
            equipamiento = ["barra"]
        if "peso corporal" in texto or "calistenia" in texto:
            equipamiento = ["peso_corporal"]
        if "banda" in texto or "bandas" in texto or "liga" in texto:
            equipamiento = ["bandas"]

        if "tabata" in texto:
            formatos = ["tabata"]
        if "hiit" in texto:
            formatos = ["hiit"]
        if "circuito" in texto:
            formatos = ["circuito"]
        if "hipertrof" in texto:
            formatos = ["hipertrofia"]
        if "fuerza" in texto:
            formatos = ["fuerza"]
        if "quema grasa" in texto or "quemar grasa" in texto:
            formatos = ["quema_grasa"]
        if "funcional" in texto:
            formatos = ["funcional"]

        if "sin salto" in texto or "sin saltos" in texto:
            restricciones = ["sin_saltos"]
        if "bajo impacto" in texto:
            restricciones = ["bajo_impacto"]
        if "rodilla" in texto:
            restricciones = ["cuidar_rodilla"]
        if "espalda" in texto and "dolor" in texto:
            restricciones = ["cuidar_espalda"]

    texto_usuario = " ".join(mensajes_usuario)

    return {
        "equipamiento": sorted(list(set(equipamiento))),
        "formatos": sorted(list(set(formatos))),
        "restricciones": sorted(list(set(restricciones))),
        "texto_libre": texto_usuario.strip(),
    }


def _texto_usuario_completo(historial_chat):
    return " ".join(
        m.get("content", "") for m in historial_chat if m.get("role") == "user"
    )


def _buscar_patron(texto, patrones):
    for patron in patrones:
        match = re.search(patron, texto, flags=re.IGNORECASE)
        if match:
            return match
    return None


def _numero_palabra_a_entero(texto):
    mapa = {
        "uno": 1,
        "una": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
    }
    return mapa.get(texto.strip(), None)


def _inferir_estatura_cm(valor_str, unidad):
    try:
        valor = float(valor_str.replace(",", "."))
    except Exception:
        return None

    unidad = (unidad or "").strip().lower()
    if unidad in {"cm", "centimetros", "centimetro"}:
        cm = int(round(valor))
        return cm if 120 <= cm <= 230 else None

    if unidad in {"m", "metro", "metros"}:
        cm = int(round(valor * 100))
        return cm if 120 <= cm <= 230 else None

    # Sin unidad explicita: inferencia por rango.
    if valor >= 100:
        cm = int(round(valor))
        return cm if 120 <= cm <= 230 else None

    if 1.2 <= valor <= 2.3:
        cm = int(round(valor * 100))
        return cm if 120 <= cm <= 230 else None

    return None


def _inferir_peso_kg(valor_str):
    try:
        valor = float(valor_str.replace(",", "."))
    except Exception:
        return None

    kg = int(round(valor))
    if 30 <= kg <= 300:
        return kg
    return None


def _extraer_perfil_chat(historial_chat):
    edad = None
    estatura = None
    peso = None
    objetivo = ""
    dias_disponibles = None

    match_edad = _buscar_patron(
        texto,
        [
            r"(?:tengo|edad)\s*(\d{1,2})\s*anos",
            r"(\d{1,2})\s*(?:anos|años)"
        ],
    )
    if match_edad:
        edad = int(match_edad.group(1))

    match_estatura_cm = _buscar_patron(
        texto,
        [
            r"(?:mido|estatura)\s*(\d{2,3})\s*(?:cm)?"
        ],
    )
    match_estatura_m = _buscar_patron(
        texto,
        [
            r"(?:mido|estatura)\s*(1\.\d{1,2})\s*m",
            r"(?:mido|estatura)\s*(1,\d{1,2})\s*m",
        ],
    )
    if match_estatura_m:
        valor = match_estatura_m.group(1).replace(",", ".")
        estatura = int(float(valor) * 100)
    elif match_estatura_cm:
        estatura = int(match_estatura_cm.group(1))

    match_peso = _buscar_patron(
        texto,
        [
            r"(?:peso|peso actual)\s*(\d{2,3})\s*(?:kg)?"
        ],
    )
    if match_peso:
        peso = int(match_peso.group(1))

    match_dias = _buscar_patron(
        texto,
        [
            r"(?:puedo entrenar|entreno|entrenar)\s*(\d)\s*dias",
            r"(\d)\s*dias\s*(?:por semana|a la semana)?",
            r"(\d)\s*(?:dias|días)"
        ],
    )
    if match_dias:
        dias_disponibles = int(match_dias.group(1))

    objetivos = [
        "perder grasa",
        "bajar grasa",
        "bajar de peso",
        "deficit calorico",
        "déficit calorico",
        "deficit",
        "quemar grasa",
        "ganar masa muscular",
        "hipertrofia",
        "tonificar",
        "fuerza",
        "resistencia",
        "recomposicion corporal",
        "mantenerme",
    ]
    for mensaje in [m.get("content", "") for m in historial_chat if m.get("role") == "user"]:
        texto = _normalizar_texto(mensaje)

        match_edad = _buscar_patron(
            texto,
            [
                r"(?:tengo|edad|cumpli|cumplo)\s*(\d{1,2})\s*anos",
                r"(?:tengo|edad)\s*(\d{1,2})\b",
                r"(\d{1,2})\s*anos",
            ],
        )
        if match_edad:
            valor_edad = int(match_edad.group(1))
            if 12 <= valor_edad <= 90:
                edad = valor_edad

        # Altura con o sin unidad: "mido 1.75", "mido 1,75", "estatura 175", "altura 175 cm".
        match_estatura = _buscar_patron(
            texto,
            [
                r"(?:mido|estatura|altura)\s*(?:de\s*)?(\d{1,3}(?:[\.,]\d{1,2})?)\s*(cm|m|metros|metro|centimetros|centimetro)?",
                r"(\d{3})\s*cm\b",
                r"(1[\.,]\d{1,2})\b",
            ],
        )
        if match_estatura:
            valor_altura = match_estatura.group(1)
            unidad_altura = match_estatura.group(2) if len(match_estatura.groups()) >= 2 else ""
            altura_cm = _inferir_estatura_cm(valor_altura, unidad_altura)
            if altura_cm:
                estatura = altura_cm

        # Peso con o sin kg explicito: "peso 75", "75 kg", "peso actual 74.5".
        match_peso = _buscar_patron(
            texto,
            [
                r"(?:peso|peso actual|mi peso es|estoy pesando)\s*(\d{2,3}(?:[\.,]\d{1,2})?)\s*(?:kg|kilo|kilos)?",
                r"(\d{2,3}(?:[\.,]\d{1,2})?)\s*(?:kg|kilo|kilos)\b",
            ],
        )
        if match_peso:
            peso_kg = _inferir_peso_kg(match_peso.group(1))
            if peso_kg:
                peso = peso_kg

        # Dias semanales con numero o palabra: "5 dias", "cinco dias", "puedo entrenar 4".
        match_dias_num = _buscar_patron(
            texto,
            [
                r"(?:puedo entrenar|entreno|entrenar|disponible)\s*(\d)\s*dias",
                r"(\d)\s*dias\s*(?:por semana|a la semana)?",
                r"(\d)\s*dias\b",
            ],
        )
        if match_dias_num:
            dias_valor = int(match_dias_num.group(1))
            if 1 <= dias_valor <= 7:
                dias_disponibles = dias_valor
        else:
            match_dias_txt = _buscar_patron(
                texto,
                [
                    r"(uno|una|dos|tres|cuatro|cinco|seis|siete)\s*dias",
                ],
            )
            if match_dias_txt:
                dias_texto = _numero_palabra_a_entero(match_dias_txt.group(1))
                if dias_texto:
                    dias_disponibles = dias_texto

        for obj in objetivos:
            if obj in texto:
                objetivo = obj

    return {
        "edad": edad,
        "estatura": estatura,
        "peso": peso,
        "objetivo": objetivo,
        "dias_disponibles": dias_disponibles,
    }


def _fusionar_perfiles(perfil_entrada, perfil_extraido):
    return {
        "edad": perfil_extraido.get("edad") if perfil_extraido.get("edad") is not None else perfil_entrada.get("edad"),
        "estatura": perfil_extraido.get("estatura") if perfil_extraido.get("estatura") is not None else perfil_entrada.get("estatura"),
        "peso": perfil_extraido.get("peso") if perfil_extraido.get("peso") is not None else perfil_entrada.get("peso"),
        "objetivo": perfil_extraido.get("objetivo") if perfil_extraido.get("objetivo") else perfil_entrada.get("objetivo"),
        "dias_disponibles": perfil_extraido.get("dias_disponibles") if perfil_extraido.get("dias_disponibles") is not None else perfil_entrada.get("dias_disponibles"),
    }


def _cache_key_plan(perfil, preferencias):
    objetivo = _normalizar_texto((perfil.get("objetivo") or "").strip())
    return json.dumps(
        {
            "perfil": {
                "edad": perfil.get("edad"),
                "estatura": perfil.get("estatura"),
                "peso": perfil.get("peso"),
                "objetivo": objetivo,
                "dias_disponibles": perfil.get("dias_disponibles"),
            },
            "preferencias": {
                "equipamiento": sorted(preferencias.get("equipamiento", [])),
                "formatos": sorted(preferencias.get("formatos", [])),
                "restricciones": sorted(preferencias.get("restricciones", [])),
            },
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _detectar_intentos_campos(historial_chat):
    texto = _normalizar_texto(_texto_usuario_completo(historial_chat))
    intentos = {}

    match_edad = _buscar_patron(
        texto,
        [
            r"(?:tengo|edad|cumpli|cumplo)\s*(\d{1,2})\s*anos",
            r"(\d{1,2})\s*anos",
        ],
    )
    if match_edad:
        edad_valor = int(match_edad.group(1))
        if not (12 <= edad_valor <= 90):
            intentos["edad"] = "rango"

    match_estatura = _buscar_patron(
        texto,
        [
            r"(?:mido|estatura|altura)\s*(?:de\s*)?(\d{1,3}(?:[\.,]\d{1,2})?)\s*(cm|m|metros|metro|centimetros|centimetro)?",
            r"(\d{3})\s*cm\b",
            r"(1[\.,]\d{1,2})\b",
        ],
    )
    if match_estatura:
        valor_altura = match_estatura.group(1)
        unidad_altura = match_estatura.group(2) if len(match_estatura.groups()) >= 2 else ""
        if _inferir_estatura_cm(valor_altura, unidad_altura) is None:
            intentos["estatura"] = "formato"

    match_peso = _buscar_patron(
        texto,
        [
            r"(?:peso|peso actual|mi peso es|estoy pesando)\s*(\d{2,3}(?:[\.,]\d{1,2})?)\s*(?:kg|kilo|kilos)?",
            r"(\d{2,3}(?:[\.,]\d{1,2})?)\s*(?:kg|kilo|kilos)\b",
        ],
    )
    if match_peso and _inferir_peso_kg(match_peso.group(1)) is None:
        intentos["peso"] = "formato"

    match_dias_num = _buscar_patron(
        texto,
        [
            r"(\d)\s*dias\b",
        ],
    )
    if match_dias_num:
        dias_valor = int(match_dias_num.group(1))
        if not (1 <= dias_valor <= 7):
            intentos["dias_disponibles"] = "rango"

    return intentos


def _resumen_campos_capturados(perfil):
    partes = []
    if perfil.get("edad"):
        partes.append(f"edad {perfil.get('edad')}")
    if perfil.get("estatura"):
        partes.append(f"estatura {perfil.get('estatura')} cm")
    if perfil.get("peso"):
        partes.append(f"peso {perfil.get('peso')} kg")
    if perfil.get("objetivo"):
        partes.append(f"objetivo {perfil.get('objetivo')}")
    if perfil.get("dias_disponibles"):
        partes.append(f"dias {perfil.get('dias_disponibles')}")
    return partes


def _siguiente_campo_faltante(faltantes, perfil=None, intentos=None):
    perfil = perfil or {}
    intentos = intentos or {}

    # Si el usuario intento dar un campo y fallo validacion, priorizar ese campo.
    for campo in ("estatura", "peso", "dias_disponibles", "objetivo", "edad"):
        if campo in faltantes and campo in intentos:
            return campo

    # Flujo mas natural: si ya hay datos fisicos u objetivo, no bloquear por edad de inmediato.
    tiene_contexto = any(
        [
            perfil.get("estatura"),
            perfil.get("peso"),
            perfil.get("objetivo"),
            perfil.get("dias_disponibles"),
        ]
    )

    if tiene_contexto:
        orden = ["estatura", "peso", "objetivo", "dias_disponibles", "edad"]
    else:
        orden = ["edad", "estatura", "peso", "objetivo", "dias_disponibles"]

    for campo in orden:
        if campo in faltantes:
            return campo
    return faltantes[0] if faltantes else None


def _mensaje_faltantes(faltantes, perfil=None, intentos=None):
    intentos = intentos or {}
    perfil = perfil or {}
    etiquetas = {
        "edad": "tu edad",
        "estatura": "tu estatura en cm",
        "peso": "tu peso en kg",
        "objetivo": "tu objetivo principal",
        "dias_disponibles": "cuantos dias puedes entrenar por semana",
    }

    ayudas = {
        "edad": "Edad: ejemplo 25 anos.",
        "estatura": "Estatura: puedes decir 175, 175 cm, 1.75 o 1,75.",
        "peso": "Peso: puedes decir 75 o 75 kg.",
        "objetivo": "Objetivo: ejemplo ganar masa muscular, perder grasa o fuerza.",
        "dias_disponibles": "Dias por semana: ejemplo 3, 4, 5 o seis dias.",
    }

    preguntas = {
        "edad": "¿Que edad tienes?",
        "estatura": "¿Cual es tu estatura?",
        "peso": "¿Cual es tu peso actual?",
        "objetivo": "¿Cual es tu objetivo principal?",
        "dias_disponibles": "¿Cuantos dias por semana puedes entrenar?",
    }

    capturados = _resumen_campos_capturados(perfil)
    prefijo_capturados = ""
    if capturados:
        prefijo_capturados = "Ya tengo: " + ", ".join(capturados) + ". "

    campo_objetivo = _siguiente_campo_faltante(faltantes, perfil, intentos)
    if not campo_objetivo:
        return "Perfecto, ya tengo todo lo necesario para construir tu rutina."

    prefijo = ""
    if campo_objetivo in intentos:
        prefijo = "Te entendi, pero ese dato no lo pude validar. "

    if not capturados:
        return (
            "Vamos paso a paso para hacerlo facil. "
            + preguntas.get(campo_objetivo, "")
            + " "
            + ayudas.get(campo_objetivo, "")
            + " Si quieres, tambien puedes mandarme varios datos en un solo mensaje."
        )

    return (
        prefijo_capturados
        + prefijo
        + "Ahora solo dime "
        + etiquetas.get(campo_objetivo, campo_objetivo)
        + ". "
        + preguntas.get(campo_objetivo, "")
        + " "
        + ayudas.get(campo_objetivo, "")
    )


def _planes_vacios():
    return {
        "baja": {"justificacion": "", "dias": []},
        "media": {"justificacion": "", "dias": []},
        "alta": {"justificacion": "", "dias": []},
    }


def _dia_base_respaldo(perfil, intensidad, indice):
    objetivo = _normalizar_texto((perfil.get("objetivo") or "").strip())
    if any(clave in objetivo for clave in ("masa", "muscular", "hipertrof")):
        grupos = [
            ("Pecho y triceps", "Empuje tecnico y controlado"),
            ("Espalda y biceps", "Tiron con rango completo"),
            ("Piernas", "Base de fuerza y volumen"),
            ("Hombros y abdomen", "Estabilidad y postura"),
        ]
    elif any(clave in objetivo for clave in ("grasa", "definir", "perder", "bajar peso")):
        grupos = [
            ("Cuerpo completo", "Bloque metabolico y constante"),
            ("Piernas y gluteos", "Control y gasto energetico"),
            ("Espalda y core", "Tension sostenida y tecnica"),
            ("Torso y brazos", "Trabajo continuo sin impacto"),
        ]
    else:
        grupos = [
            ("Cuerpo completo", "Acondicionamiento general"),
            ("Tren superior", "Control de tecnica y volumen"),
            ("Tren inferior", "Fuerza y estabilidad"),
            ("Core y movilidad", "Calidad de movimiento"),
        ]

    grupo_muscular, foco_base = grupos[(indice - 1) % len(grupos)]
    foco_por_intensidad = {
        "baja": foco_base,
        "media": f"{foco_base} progresivo",
        "alta": f"{foco_base} exigente",
    }

    return {
        "dia": f"Dia {indice}",
        "grupo_muscular": grupo_muscular,
        "foco": foco_por_intensidad.get(intensidad, foco_base),
        "ejercicios": [],
    }


def _construir_planes_respaldo(perfil, preferencias):
    dias_disponibles = perfil.get("dias_disponibles") or 3
    try:
        dias_disponibles = int(dias_disponibles)
    except Exception:
        dias_disponibles = 3
    dias_disponibles = max(2, min(dias_disponibles, 6))

    equipamiento = preferencias.get("equipamiento", []) or []
    restricciones = preferencias.get("restricciones", []) or []

    mensaje = "Tu rutina base quedo lista. Selecciona un dia para ver el detalle completo."
    if equipamiento:
        mensaje = f"Tu rutina base ya respeta {', '.join(equipamiento[:2])}. Selecciona un dia para ver el detalle completo."
    if restricciones:
        mensaje = f"Tu rutina base ya respeta {', '.join(restricciones[:2])}. Selecciona un dia para ver el detalle completo."

    return {
        "mensaje_coach": mensaje,
        "planes_por_intensidad": {
            "baja": {
                "justificacion": "Base segura para arrancar con tecnica y adherencia.",
                "dias": [_dia_base_respaldo(perfil, "baja", indice) for indice in range(1, dias_disponibles + 1)],
            },
            "media": {
                "justificacion": "Volumen equilibrado para progresar sin sobrecarga.",
                "dias": [_dia_base_respaldo(perfil, "media", indice) for indice in range(1, dias_disponibles + 1)],
            },
            "alta": {
                "justificacion": "Mayor exigencia para empujar adaptacion y rendimiento.",
                "dias": [_dia_base_respaldo(perfil, "alta", indice) for indice in range(1, dias_disponibles + 1)],
            },
        },
    }


def _planes_tienen_dias(planes):
    if not isinstance(planes, dict):
        return False
    for intensidad in ("baja", "media", "alta"):
        plan = planes.get(intensidad) or {}
        dias = plan.get("dias") if isinstance(plan, dict) else None
        if isinstance(dias, list) and len(dias) > 0:
            return True
    return False


def _normalizar_planes_rescatados(resultado):
    if not isinstance(resultado, dict):
        return None

    if "planes_por_intensidad" not in resultado and all(k in resultado for k in ("baja", "media", "alta")):
        resultado = {
            "mensaje_coach": resultado.get("mensaje_coach", ""),
            "planes_por_intensidad": {
                "baja": resultado.get("baja", {"justificacion": "", "dias": []}),
                "media": resultado.get("media", {"justificacion": "", "dias": []}),
                "alta": resultado.get("alta", {"justificacion": "", "dias": []}),
            },
        }

    if "planes_por_intensidad" not in resultado:
        return None

    planes = resultado.get("planes_por_intensidad") or {}
    if not isinstance(planes, dict):
        return None
    for intensidad in ("baja", "media", "alta"):
        plan = planes.get(intensidad) or {}
        if not isinstance(plan, dict):
            plan = {}
        dias = plan.get("dias") or []
        if not isinstance(dias, list):
            dias = []
        planes[intensidad] = {
            "justificacion": plan.get("justificacion", ""),
            "dias": dias,
        }

    return {
        "mensaje_coach": resultado.get("mensaje_coach", "Perfecto, aqui tienes tu plan personalizado por intensidad."),
        "planes_por_intensidad": planes,
    }


def _cache_key_day_detail(perfil, preferencias, intensidad, dia, grupo_muscular, foco):
    objetivo = _normalizar_texto((perfil.get("objetivo") or "").strip())
    return json.dumps(
        {
            "perfil": {
                "edad": perfil.get("edad"),
                "estatura": perfil.get("estatura"),
                "peso": perfil.get("peso"),
                "objetivo": objetivo,
                "dias_disponibles": perfil.get("dias_disponibles"),
            },
            "preferencias": {
                "equipamiento": sorted(preferencias.get("equipamiento", [])),
                "formatos": sorted(preferencias.get("formatos", [])),
                "restricciones": sorted(preferencias.get("restricciones", [])),
            },
            "intensidad": intensidad,
            "dia": dia,
            "grupo_muscular": grupo_muscular,
            "foco": foco,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _generar_planes_por_intensidad(perfil, preferencias):
    cache_key = _cache_key_plan(perfil, preferencias)
    ahora = time.time()
    cache_item = _PLAN_CACHE.get(cache_key)
    if cache_item and (ahora - cache_item["ts"] <= PLAN_CACHE_TTL):
        return copy.deepcopy(cache_item["value"])

    contexto = f"""
Eres un Fit Coach profesional de alto nivel.

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

Tu enfoque tecnico:
- Debes pensar como entrenador real: seguridad, progresion y adherencia.
- Ajusta la seleccion de ejercicios a nivel del usuario y objetivo.
- Da instrucciones concretas y ejecutables (tecnica, postura, tempo y control).
- Usa tips utiles de coaching, no texto generico.

Responde SOLO JSON valido con esta estructura exacta:
{{
    "mensaje_coach": "",
    "planes_por_intensidad": {{
        "baja": {{"justificacion": "", "dias": []}},
        "media": {{"justificacion": "", "dias": []}},
        "alta": {{"justificacion": "", "dias": []}}
    }}
}}

Formato de cada dia (respuesta RAPIDA, sin detalle completo de ejercicios):
{{
    "dia": "Dia 1",
    "grupo_muscular": "Pecho y triceps",
    "foco": "Hipertrofia tecnica",
    "ejercicios": []
}}

Reglas:
1. En cada intensidad crea exactamente {perfil.get("dias_disponibles")} dias.
2. Ajusta volumen y exigencia segun intensidad (baja, media, alta).
3. Respuesta inicial RAPIDA: deja siempre ejercicios=[] en cada dia.
4. Mantener recomendaciones seguras y progresivas.
5. Si el usuario pide "solo mancuernas", TODOS los ejercicios deben ser con mancuernas.
6. Si el usuario pide "solo maquinas", TODOS los ejercicios deben ser de maquinas.
7. Si el usuario pide TABATA, la rutina debe usar estructura TABATA (bloques por intervalos) y ejercicios compatibles.
8. Respeta restricciones detectadas (ej: sin saltos, bajo impacto, cuidar rodilla).
9. justificacion por intensidad debe ser breve (maximo 140 caracteres).
10. mensaje_coach debe incluir feedback motivador, una recomendacion de ejecucion y una pauta de progresion semanal (maximo 320 caracteres).
11. Si formatos incluye "tabata":
- TODOS los dias deben ser en formato TABATA (intervalos)
- foco debe mencionar intervalos o alta intensidad
12. Si formatos incluye "calistenia":
- SOLO usar peso corporal
- ejercicios como push-ups, squats, pull-ups, planks
13. Si formatos incluye "yoga":
- rutina basada en movilidad, respiracion y estiramientos
- usar nombres reales de posturas
14. Si formatos incluye "hiit":
- incluir bloques de alta intensidad + descanso
"""

    try:
        response = client.with_options(timeout=20.0, max_retries=0).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": contexto}],
            temperature=0.25,
            max_tokens=850,
            response_format={"type": "json_object"},
        )
    except Exception:
        return {"error": "El coach esta tardando mas de lo esperado. Intenta nuevamente en unos segundos."}

    contenido = response.choices[0].message.content
    resultado = _limpiar_y_parsear_json(contenido)
    if "error" not in resultado:
        _PLAN_CACHE[cache_key] = {"ts": ahora, "value": copy.deepcopy(resultado)}
    return resultado


def generar_detalle_dia(perfil, preferencias, intensidad, dia, grupo_muscular, foco):
    cache_key = _cache_key_day_detail(
        perfil=perfil,
        preferencias=preferencias,
        intensidad=intensidad,
        dia=dia,
        grupo_muscular=grupo_muscular,
        foco=foco,
    )
    ahora = time.time()
    cache_item = _DAY_DETAIL_CACHE.get(cache_key)
    if cache_item and (ahora - cache_item["ts"] <= PLAN_CACHE_TTL):
        return copy.deepcopy(cache_item["value"])

    contexto = f"""
Eres un Fit Coach profesional. Genera el detalle de un solo dia.

Perfil:
- edad: {perfil.get("edad")}
- estatura: {perfil.get("estatura")} cm
- peso: {perfil.get("peso")} kg
- objetivo: {perfil.get("objetivo")}

Preferencias:
- equipamiento: {preferencias.get("equipamiento")}
- formatos: {preferencias.get("formatos")}
- restricciones: {preferencias.get("restricciones")}

Dia a detallar:
- intensidad: {intensidad}
- dia: {dia}
- grupo_muscular: {grupo_muscular}
- foco: {foco}

Responde SOLO JSON valido con esta estructura exacta:
{{
  "ejercicios": [
    {{
      "grupo_muscular": "",
      "ejercicio": "",
      "series_reps": "",
      "descanso": "",
      "instrucciones": "",
      "tips": "",
      "video_busqueda": "",
      "imagen_referencia": ""
    }}
  ]
}}

Reglas:
1. Devuelve exactamente 4 ejercicios.
2. Respeta intensidad, foco y restricciones.
3. Si pidio solo mancuernas o solo maquinas, cumplir en todos los ejercicios.
4. Si pidio tabata, usar estructura de intervalos compatible.
5. Instrucciones cortas y accionables (max 16 palabras).
6. Tips breves de coaching (max 12 palabras).
"""

    try:
        response = client.with_options(timeout=20.0, max_retries=0).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": contexto}],
            temperature=0.2,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
    except Exception:
        return {"error": "No pude cargar el detalle del dia a tiempo. Intenta nuevamente."}

    contenido = response.choices[0].message.content
    resultado = _limpiar_y_parsear_json(contenido)
    if "error" not in resultado:
        _DAY_DETAIL_CACHE[cache_key] = {"ts": ahora, "value": copy.deepcopy(resultado)}
    return resultado


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

    response = client.with_options(timeout=20.0, max_retries=0).chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": contexto}],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    contenido = response.choices[0].message.content
    return _limpiar_y_parsear_json(contenido)

def _fusionar_con_historial(perfil_actual, historial_chat):
    perfil = perfil_actual.copy()

    for mensaje in historial_chat:
        if mensaje.get("role") != "user":
            continue

        extraido = _extraer_perfil_chat([mensaje])

        for key, value in extraido.items():
            if value:
                perfil[key] = value

    return perfil

def generar_plan_conversacional(perfil, historial_chat):
    perfil_entrada = _normalizar_perfil(perfil or {})
    perfil_detectado_chat = _extraer_perfil_chat(historial_chat)
    perfil_final = _fusionar_perfiles(perfil_entrada, perfil_detectado_chat)
    perfil_final = _fusionar_con_historial(perfil_final, historial_chat)

    faltantes = _campos_faltantes(perfil_final)
    intentos = _detectar_intentos_campos(historial_chat)
    preferencias = _extraer_preferencias_chat(historial_chat)

    if not faltantes:
        planes = _generar_planes_por_intensidad(perfil_final, preferencias)
        if "error" in planes:
            recuperado = _rescatar_json_desde_error(planes.get("error"))
            normalizado = _normalizar_planes_rescatados(recuperado)
            if normalizado:
                planes = normalizado
            else:
                return {
                    "estado": "rutina_lista",
                    "campos_faltantes": faltantes,
                    "perfil_detectado": perfil_final,
                    "preferencias_detectadas": preferencias,
                    **_construir_planes_respaldo(perfil_final, preferencias),
                }

        normalizado = _normalizar_planes_rescatados(planes)
        if normalizado:
            planes = normalizado

        if not _planes_tienen_dias(planes.get("planes_por_intensidad", planes)):
            planes = _construir_planes_respaldo(perfil_final, preferencias)

        return {
            "mensaje_coach": planes.get("mensaje_coach") or "Perfecto, aqui tienes tu plan personalizado por intensidad.",
            "estado": "rutina_lista",
            "campos_faltantes": [],
            "perfil_detectado": perfil_final,
            "preferencias_detectadas": preferencias,
            "planes_por_intensidad": planes.get("planes_por_intensidad", _planes_vacios()),
        }

    return {
        "mensaje_coach": _mensaje_faltantes(faltantes, perfil_final, intentos),
        "estado": "faltan_datos",
        "campos_faltantes": faltantes,
        "perfil_detectado": perfil_final,
        "preferencias_detectadas": preferencias,
        "planes_por_intensidad": _planes_vacios(),
    }
