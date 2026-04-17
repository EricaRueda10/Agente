"use client";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type Intensidad = "baja" | "media" | "alta";

type PerfilDetectado = {
  edad: number | null;
  estatura: number | null;
  peso: number | null;
  objetivo: string;
  dias_disponibles: number | null;
};

type Ejercicio = {
  grupo_muscular: string;
  ejercicio: string;
  series_reps: string;
  descanso: string;
  instrucciones: string;
  tips: string;
  video_busqueda: string;
  imagen_referencia: string;
};

type DiaPlan = {
  dia: string;
  grupo_muscular: string;
  foco: string;
  ejercicios: Ejercicio[];
};

type PlanIntensidad = {
  justificacion: string;
  dias: DiaPlan[];
};

type ResultadoCoach = {
  mensaje_coach: string;
  estado: "faltan_datos" | "rutina_lista";
  campos_faltantes: string[];
  perfil_detectado: PerfilDetectado;
  planes_por_intensidad: Record<Intensidad, PlanIntensidad>;
  error?: string;
};

const INTENSIDADES: Intensidad[] = ["baja", "media", "alta"];

export default function Home() {
  const [mensaje, setMensaje] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hola, soy tu Fit Coach. Para empezar, dime tu edad, estatura, peso, objetivo y cuantos dias puedes entrenar por semana.",
    },
  ]);
  const [resultado, setResultado] = useState<ResultadoCoach | null>(null);
  const [intensidadActiva, setIntensidadActiva] = useState<Intensidad>("media");
  const [diaActivo, setDiaActivo] = useState<string>("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const chatRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [chat, loading]);

  const planActivo = useMemo(() => {
    return resultado?.planes_por_intensidad?.[intensidadActiva];
  }, [resultado, intensidadActiva]);

  const diaSeleccionado = useMemo(() => {
    return planActivo?.dias?.find((d) => d.dia === diaActivo) || null;
  }, [planActivo, diaActivo]);

  useEffect(() => {
    const primerDia = planActivo?.dias?.[0]?.dia || "";
    setDiaActivo(primerDia);
  }, [planActivo]);

  const enviarMensaje = async (e?: FormEvent) => {
    e?.preventDefault();

    if (!mensaje.trim()) {
      setError("Escribe un mensaje para conversar con tu coach.");
      return;
    }

    const nuevoChat: ChatMessage[] = [
      ...chat,
      { role: "user", content: mensaje.trim() },
    ];

    setError("");
    setLoading(true);
    setChat([...nuevoChat, { role: "assistant", content: "" }]);
    setMensaje("");

    try {
      const res = await fetch("http://127.0.0.1:8000/agente/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          historial_chat: nuevoChat,
        }),
      });

      if (!res.ok || !res.body) {
        setError("No se pudo procesar el mensaje. Revisa backend y API key.");
        setChat((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = {
              ...last,
              content: "No pude responder correctamente. Intenta de nuevo.",
            };
          }
          return next;
        });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const appendAssistantText = (chunk: string) => {
        setChat((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = {
              ...last,
              content: `${last.content}${chunk}`,
            };
          }
          return next;
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        let eventBoundary = buffer.indexOf("\n\n");
        while (eventBoundary !== -1) {
          const rawEvent = buffer.slice(0, eventBoundary);
          buffer = buffer.slice(eventBoundary + 2);

          let eventType = "message";
          let dataLine = "";

          for (const line of rawEvent.split("\n")) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
            }
            if (line.startsWith("data:")) {
              dataLine += line.slice(5).trim();
            }
          }

          if (dataLine) {
            const parsed = JSON.parse(dataLine);

            if (eventType === "token") {
              appendAssistantText(parsed.chunk || "");
            }

            if (eventType === "result") {
              const resultadoCoach: ResultadoCoach = parsed.resultado;
              setResultado(resultadoCoach);

              setChat((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant" && !last.content.trim()) {
                  next[next.length - 1] = {
                    ...last,
                    content: resultadoCoach.mensaje_coach || "Listo.",
                  };
                }
                return next;
              });
            }

            if (eventType === "error") {
              setError(parsed.message || "No se pudo procesar el mensaje.");
            }
          }

          eventBoundary = buffer.indexOf("\n\n");
        }
      }
    } catch {
      setError("No hay conexion con el backend en http://127.0.0.1:8000");
    } finally {
      setLoading(false);
    }
  };

  const tieneRutina = resultado?.estado === "rutina_lista";

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black p-4 md:p-6 text-white">
      <div className="mx-auto w-full max-w-7xl bg-gray-900/80 backdrop-blur-lg border border-gray-700 rounded-2xl shadow-2xl p-4 md:p-6">
        <h1 className="text-3xl font-bold mb-5 text-center">🏋️ FitAI Coach</h1>

        {error && (
          <div className="mb-4 p-3 rounded-lg border border-red-600 bg-red-900/40 text-red-200 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section className="border border-gray-700 bg-gray-900/70 rounded-xl p-4 flex flex-col min-h-[700px]">
            <h2 className="text-xl font-semibold mb-3">Chat en tiempo real</h2>

            <div ref={chatRef} className="flex-1 overflow-y-auto space-y-3 pr-1">
              {chat.map((m, idx) => (
                <div
                  key={idx}
                  className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "ml-auto bg-green-700/40 border border-green-600"
                      : "mr-auto bg-blue-700/30 border border-blue-600"
                  }`}
                >
                  {m.content}
                </div>
              ))}

              {loading && (
                <div className="max-w-[90%] mr-auto rounded-lg px-3 py-2 text-sm bg-blue-700/30 border border-blue-600 animate-pulse">
                  El coach esta pensando...
                </div>
              )}
            </div>

            <form onSubmit={enviarMensaje} className="mt-4 flex gap-2">
              <textarea
                className="flex-1 p-3 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 min-h-14 max-h-36"
                placeholder="Escribe aqui tu mensaje..."
                value={mensaje}
                onChange={(e) => setMensaje(e.target.value)}
              />
              <button
                type="submit"
                disabled={loading}
                className="self-end bg-gradient-to-r from-green-400 to-blue-500 text-black font-bold px-4 py-3 rounded-lg hover:scale-[1.02] transition disabled:opacity-60"
              >
                Enviar
              </button>
            </form>

            {resultado?.estado === "faltan_datos" && (
              <div className="mt-3 p-3 rounded-lg border border-yellow-600 bg-yellow-900/20 text-yellow-100 text-sm">
                Campos pendientes: {resultado.campos_faltantes.join(", ")}
              </div>
            )}
          </section>

          <section className="border border-gray-700 bg-gray-900/70 rounded-xl p-4 min-h-[700px] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-3">Rutina recomendada</h2>

            {!resultado && (
              <p className="text-gray-300 text-sm">
                Conversa con el coach. El te pedira edad, estatura, peso, objetivo y dias de entrenamiento.
              </p>
            )}

            {resultado && (
              <div className="space-y-4">
                <div className="p-3 bg-gray-800 rounded-lg border border-gray-600 text-sm">
                  <p>
                    <span className="text-gray-400">Perfil detectado:</span>{" "}
                    edad {resultado.perfil_detectado.edad ?? "-"}, estatura {resultado.perfil_detectado.estatura ?? "-"} cm,
                    peso {resultado.perfil_detectado.peso ?? "-"} kg, objetivo {resultado.perfil_detectado.objetivo || "-"},
                    dias {resultado.perfil_detectado.dias_disponibles ?? "-"}
                  </p>
                </div>

                <div className="flex gap-2">
                  {INTENSIDADES.map((intensidad) => {
                    const activa = intensidadActiva === intensidad;
                    return (
                      <button
                        key={intensidad}
                        onClick={() => setIntensidadActiva(intensidad)}
                        className={`px-3 py-2 rounded-lg text-sm font-semibold border ${
                          activa
                            ? "bg-green-500 text-black border-green-400"
                            : "bg-gray-800 border-gray-600 text-gray-200"
                        }`}
                      >
                        {intensidad.toUpperCase()}
                      </button>
                    );
                  })}
                </div>

                {!tieneRutina && (
                  <p className="text-sm text-gray-300">
                    Aun no hay rutina. Responde las preguntas del coach para que pueda construir tu plan.
                  </p>
                )}

                {tieneRutina && (
                  <>
                    <div className="p-3 bg-gray-800/70 rounded-lg border border-gray-600">
                      <p className="text-xs text-gray-400 mb-2">Selecciona dia</p>
                      <div className="flex flex-wrap gap-2">
                        {planActivo?.dias?.map((dia) => (
                          <button
                            key={dia.dia}
                            onClick={() => setDiaActivo(dia.dia)}
                            className={`px-3 py-1.5 rounded-md text-sm border ${
                              diaActivo === dia.dia
                                ? "bg-blue-500 text-black border-blue-400"
                                : "bg-gray-900 border-gray-700 text-gray-200"
                            }`}
                          >
                            {dia.dia}
                          </button>
                        ))}
                      </div>
                    </div>

                    {diaSeleccionado ? (
                      <div className="space-y-3">
                        <div className="p-3 bg-gray-800 rounded-lg border border-gray-600">
                          <p className="font-semibold text-green-300">{diaSeleccionado.dia}</p>
                          <p className="text-sm text-gray-200">{diaSeleccionado.grupo_muscular}</p>
                          <p className="text-xs text-gray-400">{diaSeleccionado.foco}</p>
                        </div>

                        {diaSeleccionado.ejercicios.map((item, index) => (
                          <div key={index} className="p-3 bg-gray-800 border border-gray-600 rounded-lg">
                            <h3 className="font-bold text-base">💪 {item.ejercicio}</h3>
                            <p className="text-xs text-blue-300 mt-1">Grupo: {item.grupo_muscular}</p>
                            <p className="text-sm text-gray-300 mt-1">Series/Reps: {item.series_reps}</p>
                            <p className="text-sm text-gray-300">Descanso: {item.descanso}</p>
                            <p className="text-sm text-gray-300 mt-2">Como hacerlo: {item.instrucciones}</p>
                            {item.tips && <p className="text-sm text-yellow-200 mt-1">Tip: {item.tips}</p>}

                            {(item.video_busqueda || item.ejercicio) && (
                              <a
                                className="inline-block mt-2 text-sm text-cyan-300 underline"
                                href={`https://www.youtube.com/results?search_query=${encodeURIComponent(
                                  item.video_busqueda || item.ejercicio,
                                )}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Ver tecnica en YouTube
                              </a>
                            )}

                            {item.imagen_referencia && (
                              <img
                                src={item.imagen_referencia}
                                alt={`Referencia de ${item.ejercicio}`}
                                className="mt-3 rounded-lg border border-gray-700 w-full max-h-64 object-cover"
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-300">
                        No hay dias disponibles para esta intensidad todavia.
                      </p>
                    )}

                    <div className="p-3 bg-blue-900/40 border border-blue-700 rounded-lg">
                      <strong className="text-blue-300">Justificacion {intensidadActiva}:</strong>
                      <p className="mt-1 text-gray-300 text-sm">{planActivo?.justificacion || "-"}</p>
                    </div>
                  </>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
