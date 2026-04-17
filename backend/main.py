from fastapi import FastAPI
from pydantic import BaseModel
from agent import generar_rutina_inteligente, generar_plan_conversacional
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DatosUsuario(BaseModel):
    objetivo: str
    pasos: int
    sueno: int


class PerfilUsuario(BaseModel):
    edad: Optional[int] = None
    estatura: Optional[int] = None
    peso: Optional[int] = None
    objetivo: Optional[str] = None
    dias_disponibles: Optional[int] = None


class MensajeChat(BaseModel):
    role: str
    content: str


class DatosConversacion(BaseModel):
    perfil: Optional[PerfilUsuario] = None
    historial_chat: List[MensajeChat] = []

historial_usuario = []

@app.post("/agente")
def agente(data: DatosUsuario):
    historial_usuario.append({
        "pasos": data.pasos,
        "sueno": data.sueno
    })

    resultado = generar_rutina_inteligente(
        data.objetivo,
        data.pasos,
        data.sueno,
        historial_usuario[-3:]
    )

    return {"resultado": resultado}


@app.post("/agente/chat")
def agente_chat(data: DatosConversacion):
    perfil = data.perfil.model_dump() if data.perfil else {}

    resultado = generar_plan_conversacional(
        perfil=perfil,
        historial_chat=[m.model_dump() for m in data.historial_chat[-12:]],
    )

    return {"resultado": resultado}


@app.post("/agente/chat/stream")
def agente_chat_stream(data: DatosConversacion):
    def event_generator():
        yield "event: start\ndata: {}\n\n"

        perfil = data.perfil.model_dump() if data.perfil else {}
        resultado = generar_plan_conversacional(
            perfil=perfil,
            historial_chat=[m.model_dump() for m in data.historial_chat[-12:]],
        )

        if resultado.get("error"):
            payload = json.dumps({"message": resultado.get("error")}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
            return

        mensaje = resultado.get("mensaje_coach", "")
        for token in mensaje.split(" "):
            chunk = f"{token} "
            payload = json.dumps({"chunk": chunk}, ensure_ascii=False)
            yield f"event: token\ndata: {payload}\n\n"

        payload = json.dumps({"resultado": resultado}, ensure_ascii=False)
        yield f"event: result\ndata: {payload}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
