from fastapi import FastAPI
from pydantic import BaseModel
from agent import generar_rutina_inteligente
from fastapi.middleware.cors import CORSMiddleware

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
