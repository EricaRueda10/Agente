"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import FitCoachView, {
  ChatMessage,
  DiaPlan,
  Intensidad,
  ResultadoCoach,
} from "./components/FitCoachView";

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
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const chatRef = useRef<HTMLDivElement | null>(null);
  const detallesEnCursoRef = useRef<Set<string>>(new Set());
  const detallesCargadosRef = useRef<Set<string>>(new Set());

  const intentarParsearResultado = (valor: unknown): ResultadoCoach | null => {
    if (typeof valor !== "string") {
      return null;
    }

    const texto = valor.trim();
    if (!texto.startsWith("{")) {
      return null;
    }

    try {
      const parsed = JSON.parse(texto);
      if (parsed && typeof parsed === "object" && "mensaje_coach" in parsed && "planes_por_intensidad" in parsed) {
        return parsed as ResultadoCoach;
      }
    } catch {
      return null;
    }

    return null;
  };

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

  const claveDetalle = (diaPlan: DiaPlan, intensidad: Intensidad) => {
    return `${intensidad}|${diaPlan.dia}|${diaPlan.grupo_muscular}|${diaPlan.foco}`;
  };

  const cargarDetalleDia = async (
    diaPlan: DiaPlan,
    intensidad: Intensidad,
    resultadoFuente?: ResultadoCoach,
  ) => {
    const baseResultado = resultadoFuente || resultado;
    if (!baseResultado || baseResultado.estado !== "rutina_lista") {
      return;
    }

    const key = claveDetalle(diaPlan, intensidad);
    if (detallesCargadosRef.current.has(key) || detallesEnCursoRef.current.has(key)) {
      return;
    }

    if (diaPlan.ejercicios?.length) {
      detallesCargadosRef.current.add(key);
      return;
    }

    detallesEnCursoRef.current.add(key);
    setLoadingDetalle(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/agente/chat/detalle-dia", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          perfil: baseResultado.perfil_detectado,
          preferencias: baseResultado.preferencias_detectadas || {
            equipamiento: [],
            formatos: [],
            restricciones: [],
            texto_libre: "",
          },
          intensidad,
          dia: diaPlan.dia,
          grupo_muscular: diaPlan.grupo_muscular,
          foco: diaPlan.foco,
        }),
      });

      if (!res.ok) {
        return;
      }

      const data = await res.json();
      const ejercicios = data?.resultado?.ejercicios;
      if (!Array.isArray(ejercicios)) {
        return;
      }

      detallesCargadosRef.current.add(key);

      setResultado((prev) => {
        if (!prev || prev.estado !== "rutina_lista") {
          return prev;
        }

        const plan = prev.planes_por_intensidad?.[intensidad];
        if (!plan) {
          return prev;
        }

        const diasActualizados = plan.dias.map((d) => {
          if (d.dia !== diaPlan.dia) {
            return d;
          }
          return {
            ...d,
            ejercicios,
          };
        });

        return {
          ...prev,
          planes_por_intensidad: {
            ...prev.planes_por_intensidad,
            [intensidad]: {
              ...plan,
              dias: diasActualizados,
            },
          },
        };
      });
    } finally {
      detallesEnCursoRef.current.delete(key);
      if (detallesEnCursoRef.current.size === 0) {
        setLoadingDetalle(false);
      }
    }
  };

  useEffect(() => {
    if (!resultado || resultado.estado !== "rutina_lista") {
      return;
    }
    const plan = resultado.planes_por_intensidad?.[intensidadActiva];
    if (!plan?.dias?.length) {
      return;
    }

    const dia = plan.dias.find((d) => d.dia === diaActivo) || plan.dias[0];
    if (dia && (!dia.ejercicios || dia.ejercicios.length === 0)) {
      void cargarDetalleDia(dia, intensidadActiva, resultado);
    }
  }, [resultado, intensidadActiva, diaActivo]);

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
              detallesEnCursoRef.current.clear();
              detallesCargadosRef.current.clear();
              setResultado(resultadoCoach);

              const primerDia =
                resultadoCoach.planes_por_intensidad?.[intensidadActiva]?.dias?.[0];
              if (
                resultadoCoach.estado === "rutina_lista" &&
                primerDia &&
                (!primerDia.ejercicios || primerDia.ejercicios.length === 0)
              ) {
                void cargarDetalleDia(primerDia, intensidadActiva, resultadoCoach);
              }

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
              const resultadoPosible = intentarParsearResultado(parsed.message);
              if (resultadoPosible) {
                detallesEnCursoRef.current.clear();
                detallesCargadosRef.current.clear();
                setError("");
                setResultado(resultadoPosible);

                const primerDia = resultadoPosible.planes_por_intensidad?.[intensidadActiva]?.dias?.[0];
                if (
                  resultadoPosible.estado === "rutina_lista" &&
                  primerDia &&
                  (!primerDia.ejercicios || primerDia.ejercicios.length === 0)
                ) {
                  void cargarDetalleDia(primerDia, intensidadActiva, resultadoPosible);
                }
              } else {
                setError(parsed.message || "No se pudo procesar el mensaje.");
              }
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
    <FitCoachView
      mensaje={mensaje}
      chat={chat}
      resultado={resultado}
      intensidadActiva={intensidadActiva}
      diaActivo={diaActivo}
      error={error}
      loading={loading}
      loadingDetalle={loadingDetalle}
      tieneRutina={tieneRutina}
      planActivo={planActivo}
      diaSeleccionado={diaSeleccionado}
      chatRef={chatRef}
      onEnviarMensaje={enviarMensaje}
      onMensajeChange={setMensaje}
      onIntensidadChange={setIntensidadActiva}
      onDiaChange={setDiaActivo}
    />
  );
}
