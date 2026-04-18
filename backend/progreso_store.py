import json
import os
from datetime import date, datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "progreso_store.json")
_LOCK = Lock()


def _ensure_store() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, ensure_ascii=False)


def _read_store() -> Dict[str, Any]:
    _ensure_store()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"users": {}}


def _write_store(data: Dict[str, Any]) -> None:
    _ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _week_key(when: date) -> str:
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


def _parse_date_or_today(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _get_user(data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    users = data.setdefault("users", {})
    if user_id not in users:
        users[user_id] = {
            "chat": [],
            "ultimo_resultado": None,
            "perfil": {},
            "preferencias": {},
            "sesiones": [],
            "metricas_corporales": [],
            "racha_dias": 0,
            "ultimo_entreno_fecha": None,
        }
    return users[user_id]


def _resultado_legacy_vacio(resultado: Any) -> bool:
    if not isinstance(resultado, dict):
        return False
    if resultado.get("mensaje_coach") != "No pude construir la rutina en este intento. Intenta de nuevo.":
        return False

    planes = resultado.get("planes_por_intensidad") or {}
    if not isinstance(planes, dict):
        return True

    for intensidad in ("baja", "media", "alta"):
        plan = planes.get(intensidad) or {}
        dias = plan.get("dias") if isinstance(plan, dict) else None
        if isinstance(dias, list) and len(dias) > 0:
            return False
    return True


def _construir_resultado_respaldo(perfil: Dict[str, Any], preferencias: Dict[str, Any]) -> Dict[str, Any]:
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

    def dia_base(intensidad: str, indice: int) -> Dict[str, Any]:
        objetivo = (perfil.get("objetivo") or "").lower()
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

    return {
        "mensaje_coach": mensaje,
        "estado": "rutina_lista",
        "campos_faltantes": [],
        "perfil_detectado": perfil,
        "preferencias_detectadas": preferencias,
        "planes_por_intensidad": {
            "baja": {
                "justificacion": "Base segura para arrancar con tecnica y adherencia.",
                "dias": [dia_base("baja", indice) for indice in range(1, dias_disponibles + 1)],
            },
            "media": {
                "justificacion": "Volumen equilibrado para progresar sin sobrecarga.",
                "dias": [dia_base("media", indice) for indice in range(1, dias_disponibles + 1)],
            },
            "alta": {
                "justificacion": "Mayor exigencia para empujar adaptacion y rendimiento.",
                "dias": [dia_base("alta", indice) for indice in range(1, dias_disponibles + 1)],
            },
        },
    }


def save_contexto_chat(
    user_id: str,
    historial_chat: List[Dict[str, Any]],
    resultado: Dict[str, Any],
) -> None:
    with _LOCK:
        data = _read_store()
        user = _get_user(data, user_id)
        user["chat"] = historial_chat[-20:]
        if _resultado_legacy_vacio(resultado):
            resultado = _construir_resultado_respaldo(user.get("perfil", {}), user.get("preferencias", {}))
        user["ultimo_resultado"] = resultado
        user["perfil"] = resultado.get("perfil_detectado", {})
        user["preferencias"] = resultado.get("preferencias_detectadas", {})
        _write_store(data)


def get_contexto_chat(user_id: str) -> Dict[str, Any]:
    with _LOCK:
        data = _read_store()
        user = _get_user(data, user_id)
        resultado = user.get("ultimo_resultado")
        if _resultado_legacy_vacio(resultado):
            resultado = _construir_resultado_respaldo(user.get("perfil", {}), user.get("preferencias", {}))
        return {
            "chat": user.get("chat", []),
            "ultimo_resultado": resultado,
            "perfil": user.get("perfil", {}),
            "preferencias": user.get("preferencias", {}),
        }


def _actualizar_racha(user: Dict[str, Any], fecha_entreno: date) -> None:
    ultimo = user.get("ultimo_entreno_fecha")
    if not ultimo:
        user["racha_dias"] = 1
        user["ultimo_entreno_fecha"] = fecha_entreno.isoformat()
        return

    try:
        ultimo_date = datetime.strptime(ultimo, "%Y-%m-%d").date()
    except Exception:
        user["racha_dias"] = 1
        user["ultimo_entreno_fecha"] = fecha_entreno.isoformat()
        return

    if fecha_entreno == ultimo_date:
        return

    if fecha_entreno == (ultimo_date + timedelta(days=1)):
        user["racha_dias"] = int(user.get("racha_dias", 0)) + 1
    else:
        user["racha_dias"] = 1

    user["ultimo_entreno_fecha"] = fecha_entreno.isoformat()


def registrar_sesion(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    fecha = _parse_date_or_today(payload.get("fecha"))
    registros = payload.get("registros", [])
    ejercicios_planeados = int(payload.get("ejercicios_planeados", 0))

    completados = 0
    carga_total = 0.0
    for item in registros:
        hecho = bool(item.get("hecho"))
        reps = int(item.get("reps") or 0)
        peso = float(item.get("peso") or 0)
        if hecho:
            completados += 1
        carga_total += max(0, reps) * max(0.0, peso)

    with _LOCK:
        data = _read_store()
        user = _get_user(data, user_id)

        sesion = {
            "fecha": fecha.isoformat(),
            "intensidad": payload.get("intensidad"),
            "dia": payload.get("dia"),
            "ejercicios_planeados": ejercicios_planeados,
            "ejercicios_completados": completados,
            "cumplimiento_pct": round((completados / ejercicios_planeados) * 100, 2) if ejercicios_planeados > 0 else 0,
            "carga_total": round(carga_total, 2),
            "registros": registros,
        }
        user.setdefault("sesiones", []).append(sesion)

        peso_corporal = payload.get("peso_corporal")
        perimetros = payload.get("perimetros") or {}
        if peso_corporal is not None or perimetros:
            user.setdefault("metricas_corporales", []).append(
                {
                    "fecha": fecha.isoformat(),
                    "peso_corporal": peso_corporal,
                    "perimetros": perimetros,
                }
            )

        if completados > 0:
            _actualizar_racha(user, fecha)

        _write_store(data)

    return sesion


def _resumen_semana(sesiones: List[Dict[str, Any]], week: str) -> Tuple[int, int, float, float]:
    week_sessions = [s for s in sesiones if _week_key(_parse_date_or_today(s.get("fecha"))) == week]
    planificados = sum(int(s.get("ejercicios_planeados", 0)) for s in week_sessions)
    completados = sum(int(s.get("ejercicios_completados", 0)) for s in week_sessions)
    carga_total = sum(float(s.get("carga_total", 0.0)) for s in week_sessions)
    adherencia = round((completados / planificados) * 100, 2) if planificados > 0 else 0.0
    return planificados, completados, adherencia, round(carga_total, 2)


def _resumen_sesion(sesion: Dict[str, Any]) -> Dict[str, Any]:
    planificados = int(sesion.get("ejercicios_planeados", 0))
    completados = int(sesion.get("ejercicios_completados", 0))
    cumplimiento = round((completados / planificados) * 100, 2) if planificados > 0 else 0.0
    return {
        "fecha": sesion.get("fecha"),
        "dia": sesion.get("dia"),
        "intensidad": sesion.get("intensidad"),
        "ejercicios_planeados": planificados,
        "ejercicios_completados": completados,
        "cumplimiento_pct": cumplimiento,
        "carga_total": float(sesion.get("carga_total", 0.0)),
    }


def get_dashboard(user_id: str) -> Dict[str, Any]:
    with _LOCK:
        data = _read_store()
        user = _get_user(data, user_id)
        sesiones = user.get("sesiones", [])
        metricas = user.get("metricas_corporales", [])

        week = _week_key(date.today())
        planificados, completados, adherencia, carga_total = _resumen_semana(sesiones, week)
        week_sessions = [s for s in sesiones if _week_key(_parse_date_or_today(s.get("fecha"))) == week]
        week_sessions = sorted(week_sessions, key=lambda item: item.get("fecha", ""), reverse=True)

        peso_actual = None
        perimetros_actuales = {}
        if metricas:
            ultima = metricas[-1]
            peso_actual = ultima.get("peso_corporal")
            perimetros_actuales = ultima.get("perimetros") or {}

        return {
            "adherencia_semana_pct": adherencia,
            "ejercicios_planificados_semana": planificados,
            "ejercicios_completados_semana": completados,
            "carga_total_semana": carga_total,
            "racha_dias": int(user.get("racha_dias", 0)),
            "peso_corporal_actual": peso_actual,
            "perimetros_actuales": perimetros_actuales,
            "sesiones_semana": [_resumen_sesion(s) for s in week_sessions],
            "sesiones_recientes": [_resumen_sesion(s) for s in sesiones[-5:]][::-1],
        }


def get_adherencia_actual(user_id: str) -> float:
    dashboard = get_dashboard(user_id)
    return float(dashboard.get("adherencia_semana_pct", 0.0))
