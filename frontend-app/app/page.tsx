"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { CredentialResponse, GoogleLogin, googleLogout } from "@react-oauth/google";
import FitCoachView, {
  ChatMessage,
  DiaPlan,
  Intensidad,
  ResultadoCoach,
} from "./components/FitCoachView";

type GoogleSessionUser = {
  sub: string;
  name: string;
  email: string;
  picture?: string;
};

const GOOGLE_USER_KEY = "fitai_google_user";
const INITIAL_CHAT: ChatMessage[] = [
  {
    role: "assistant",
    content:
      "Hola, soy tu Fit Coach. Para arrancar rapido, cuentame edad, estatura, peso, objetivo y dias por semana (en el orden que quieras).",
  },
];

const decodeJwtPayload = (jwt: string): Record<string, unknown> | null => {
  try {
    const payload = jwt.split(".")[1];
    if (!payload) {
      return null;
    }
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
};

const mapGoogleUser = (payload: Record<string, unknown>): GoogleSessionUser | null => {
  const sub = typeof payload.sub === "string" ? payload.sub : "";
  const name = typeof payload.name === "string" ? payload.name : "";
  const email = typeof payload.email === "string" ? payload.email : "";
  const picture = typeof payload.picture === "string" ? payload.picture : undefined;

  if (!sub || !email) {
    return null;
  }

  return {
    sub,
    name: name || email,
    email,
    picture,
  };
};

export default function Home() {
  const googleClientEnabled = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID);
  const [mensaje, setMensaje] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>(INITIAL_CHAT);
  const [resultado, setResultado] = useState<ResultadoCoach | null>(null);
  const [intensidadActiva, setIntensidadActiva] = useState<Intensidad>("media");
  const [diaActivo, setDiaActivo] = useState<string>("");
  const [error, setError] = useState("");
  const [errorAuth, setErrorAuth] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const [diasEnCarga, setDiasEnCarga] = useState<string[]>([]);
  const [reiniciando, setReiniciando] = useState(false);
  const [mensajeSistema, setMensajeSistema] = useState("");
  const [authUser, setAuthUser] = useState<GoogleSessionUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const chatRef = useRef<HTMLDivElement | null>(null);
  const detallesEnCursoRef = useRef<Set<string>>(new Set());
  const detallesCargadosRef = useRef<Set<string>>(new Set());

  const userIdActual = authUser ? `google:${authUser.sub}` : "";
  const chatHabilitado = Boolean(authUser);

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
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(GOOGLE_USER_KEY);
    if (!stored) {
      setAuthReady(true);
      return;
    }

    try {
      const parsed = JSON.parse(stored) as GoogleSessionUser;
      if (parsed?.sub && parsed?.email) {
        setAuthUser(parsed);
      }
    } catch {
      window.localStorage.removeItem(GOOGLE_USER_KEY);
    } finally {
      setAuthReady(true);
    }
  }, []);

  useEffect(() => {
    if (!authReady) {
      return;
    }

    if (!authUser) {
      setChat(INITIAL_CHAT);
      setResultado(null);
      setError("");
      setDiasEnCarga([]);
      setMensajeSistema("");
      return;
    }

    const cargarContexto = async () => {
      try {
        const res = await fetch(`https://agente-backend-65g2.onrender.com/progreso/contexto/${encodeURIComponent(`google:${authUser.sub}`)}`);
        if (!res.ok) {
          setChat(INITIAL_CHAT);
          setResultado(null);
          return;
        }

        const data = await res.json();
        const contexto = data?.resultado;
        if (contexto?.chat?.length) {
          setChat(contexto.chat);
        } else {
          setChat(INITIAL_CHAT);
        }
        setResultado(contexto?.ultimo_resultado || null);
      } catch {
        setChat(INITIAL_CHAT);
        setResultado(null);
      }
    };

    void cargarContexto();
  }, [authReady, authUser]);

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
    if (!planActivo?.dias?.length) return;

  const existe = planActivo.dias.some((d) => d.dia === diaActivo);

  if (!existe) {
    setDiaActivo(planActivo.dias[0].dia);
  }
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
    setDiasEnCarga((prev) => (prev.includes(diaPlan.dia) ? prev : [...prev, diaPlan.dia]));
    setLoadingDetalle(true);
    try {
      const res = await fetch("https://agente-backend-65g2.onrender.com/agente/chat/detalle-dia", {
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
      setDiasEnCarga((prev) => prev.filter((dia) => dia !== diaPlan.dia));
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

    if (!chatHabilitado || !userIdActual) {
      setError("Debes iniciar sesion con Google antes de hablar con el coach.");
      return;
    }

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
  const res = await fetch("https://agente-backend-65g2.onrender.com/agente/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: userIdActual || undefined,
      historial_chat: nuevoChat,
    }),
  });

  if (!res.ok) {
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

  const data = await res.json();
  const resultadoCoach: ResultadoCoach = data.resultado;

  // limpiar estados
  detallesEnCursoRef.current.clear();
  detallesCargadosRef.current.clear();
  setDiasEnCarga([]);
  setError("");

  // guardar resultado
  setResultado(resultadoCoach);

  // cargar primer día automáticamente
  const primerDia =
    resultadoCoach.planes_por_intensidad?.[intensidadActiva]?.dias?.[0];

  if (
    resultadoCoach.estado === "rutina_lista" &&
    primerDia &&
    (!primerDia.ejercicios || primerDia.ejercicios.length === 0)
  ) {
    void cargarDetalleDia(primerDia, intensidadActiva, resultadoCoach);
  }

  // actualizar respuesta del chat
  setChat((prev) => {
    const next = [...prev];
    const last = next[next.length - 1];

    if (last?.role === "assistant") {
      next[next.length - 1] = {
        ...last,
        content: resultadoCoach.mensaje_coach || "Listo.",
      };
    }

    return next;
  });

} catch {
  setError("No hay conexion con el backend en https://agente-backend-65g2.onrender.com");
} finally {
  setLoading(false);
}

  const tieneRutina = resultado?.estado === "rutina_lista";

  const onGoogleSuccess = (credentialResponse: CredentialResponse) => {
    const credential = credentialResponse.credential;
    if (!credential) {
      setErrorAuth("No se pudo validar el login de Google.");
      return;
    }

    const payload = decodeJwtPayload(credential);
    if (!payload) {
      setErrorAuth("No se pudo leer la credencial de Google.");
      return;
    }

    const user = mapGoogleUser(payload);
    if (!user) {
      setErrorAuth("No se pudo obtener la informacion del usuario.");
      return;
    }

    setErrorAuth("");
    setAuthUser(user);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(GOOGLE_USER_KEY, JSON.stringify(user));
    }
  };

  const onGoogleError = () => {
    setErrorAuth("Fallo el inicio de sesion con Google.");
  };

  const cerrarSesion = () => {
    googleLogout();
    setAuthUser(null);
    setResultado(null);
    setChat(INITIAL_CHAT);
    setError("");
    setDiasEnCarga([]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(GOOGLE_USER_KEY);
    }
  };

  const reiniciarAgente = async () => {
    if (!userIdActual || reiniciando) {
      return;
    }

    setReiniciando(true);
    try {
      const res = await fetch("https://agente-backend-65g2.onrender.com/agente/chat/reiniciar", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: userIdActual }),
      });

      if (!res.ok) {
        if (res.status === 404) {
          setError("Tu backend no tiene la ruta de reinicio cargada. Reinicia el backend y vuelve a intentar.");
        } else {
          setError("No se pudo reiniciar el agente. Intenta de nuevo.");
        }
        return;
      }

      detallesEnCursoRef.current.clear();
      detallesCargadosRef.current.clear();
      setDiasEnCarga([]);
      setMensaje("");
      setError("");
      setResultado(null);
      setDiaActivo("");
      setIntensidadActiva("media");
      setChat(INITIAL_CHAT);
      setMensajeSistema("Agente reiniciado correctamente. La conversacion comenzo desde cero.");
      window.setTimeout(() => setMensajeSistema(""), 4500);
    } catch {
      setError("No hay conexion con el backend en https://agente-backend-65g2.onrender.com");
    } finally {
      setReiniciando(false);
    }
  };

  const topBar = (
    <div className="rounded-lg border border-gray-700 bg-gray-800/60 p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div className="text-sm text-gray-200">
        {authUser ? (
          <>
            <p className="font-semibold text-green-300">Sesion activa: {authUser.name}</p>
            <p className="text-xs text-gray-400">{authUser.email}</p>
          </>
        ) : (
          <>
            <p className="font-semibold text-amber-300">Debes iniciar sesion para hablar con el coach</p>
            <p className="text-xs text-gray-400">El chat solo esta habilitado para usuarios autenticados.</p>
          </>
        )}
      </div>

      <div className="flex flex-col items-start sm:items-end gap-2">
        {authUser ? (
          <div className="flex flex-wrap gap-2 justify-start sm:justify-end">
            <button
              onClick={reiniciarAgente}
              disabled={reiniciando}
              className="px-3 py-2 rounded-md text-sm font-semibold bg-amber-400 text-black hover:brightness-110 disabled:opacity-60"
            >
              {reiniciando ? "Reiniciando..." : "Reiniciar agente"}
            </button>
            <button
              onClick={cerrarSesion}
              className="px-3 py-2 rounded-md text-sm font-semibold bg-red-500 text-black hover:brightness-110"
            >
              Cerrar sesion
            </button>
          </div>
        ) : !googleClientEnabled ? (
          <p className="text-xs text-amber-300">
            Configura NEXT_PUBLIC_GOOGLE_CLIENT_ID para habilitar login con Google.
          </p>
        ) : (
          <GoogleLogin onSuccess={onGoogleSuccess} onError={onGoogleError} />
        )}
        {errorAuth && <p className="text-xs text-red-300">{errorAuth}</p>}
      </div>
    </div>
  );

  return (
    <FitCoachView
      topBar={topBar}
      systemMessage={mensajeSistema}
      chatHabilitado={chatHabilitado}
      mensaje={mensaje}
      chat={chat}
      resultado={resultado}
      intensidadActiva={intensidadActiva}
      diaActivo={diaActivo}
      error={error}
      loading={loading}
      loadingDetalle={loadingDetalle}
      diasEnCarga={diasEnCarga}
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
}