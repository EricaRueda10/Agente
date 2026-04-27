import { FormEvent, ReactNode, RefObject } from "react";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type Intensidad = "baja" | "media" | "alta";

export type PerfilDetectado = {
  edad: number | null;
  estatura: number | null;
  peso: number | null;
  objetivo: string;
  dias_disponibles: number | null;
};

export type PreferenciasDetectadas = {
  equipamiento: string[];
  formatos: string[];
  restricciones: string[];
  texto_libre: string;
};

export type Ejercicio = {
  grupo_muscular: string;
  ejercicio: string;
  series_reps: string;
  descanso: string;
  instrucciones: string;
  tips: string;
  video_busqueda: string;
  imagen_referencia: string;
};

export type DiaPlan = {
  dia: string;
  grupo_muscular: string;
  foco: string;
  ejercicios: Ejercicio[];
};

export type PlanIntensidad = {
  justificacion: string;
  dias: DiaPlan[];
};

export type ResultadoCoach = {
  mensaje_coach: string;
  estado: "faltan_datos" | "rutina_lista";
  campos_faltantes: string[];
  perfil_detectado: PerfilDetectado;
  preferencias_detectadas?: PreferenciasDetectadas;
  planes_por_intensidad: Record<Intensidad, PlanIntensidad>;
  error?: string;
};

const INTENSIDADES: Intensidad[] = ["baja", "media", "alta"];

type FitCoachViewProps = {
  topBar?: ReactNode;
  systemMessage?: string;
  chatHabilitado?: boolean;
  mensaje: string;
  chat: ChatMessage[];
  resultado: ResultadoCoach | null;
  intensidadActiva: Intensidad;
  diaActivo: string;
  error: string;
  loading: boolean;
  loadingDetalle: boolean;
  diasEnCarga: string[];
  tieneRutina: boolean;
  planActivo: PlanIntensidad | undefined;
  diaSeleccionado: DiaPlan | null;
  chatRef: RefObject<HTMLDivElement | null>;
  onEnviarMensaje: (e?: FormEvent) => void;
  onMensajeChange: (value: string) => void;
  onIntensidadChange: (intensidad: Intensidad) => void;
  onDiaChange: (dia: string) => void;
};

export default function FitCoachView({
  topBar,
  systemMessage,
  chatHabilitado = true,
  mensaje,
  chat,
  resultado,
  intensidadActiva,
  diaActivo,
  error,
  loading,
  loadingDetalle,
  diasEnCarga,
  tieneRutina,
  planActivo,
  diaSeleccionado,
  chatRef,
  onEnviarMensaje,
  onMensajeChange,
  onIntensidadChange,
  onDiaChange,
}: FitCoachViewProps) {
  const estadoPerfil = resultado
    ? [
        {
          key: "edad",
          label: "Edad",
          ok: Boolean(resultado.perfil_detectado.edad),
          valor: resultado.perfil_detectado.edad ? `${resultado.perfil_detectado.edad} años` : "Falta",
        },
        {
          key: "estatura",
          label: "Estatura",
          ok: Boolean(resultado.perfil_detectado.estatura),
          valor: resultado.perfil_detectado.estatura ? `${resultado.perfil_detectado.estatura} cm` : "Falta",
        },
        {
          key: "peso",
          label: "Peso",
          ok: Boolean(resultado.perfil_detectado.peso),
          valor: resultado.perfil_detectado.peso ? `${resultado.perfil_detectado.peso} kg` : "Falta",
        },
        {
          key: "objetivo",
          label: "Objetivo",
          ok: Boolean(resultado.perfil_detectado.objetivo?.trim()),
          valor: resultado.perfil_detectado.objetivo?.trim() || "Falta",
        },
        {
          key: "dias_disponibles",
          label: "Días",
          ok: Boolean(resultado.perfil_detectado.dias_disponibles),
          valor: resultado.perfil_detectado.dias_disponibles
            ? `${resultado.perfil_detectado.dias_disponibles} por semana`
            : "Falta",
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black p-3 sm:p-4 md:p-6 text-white">
      <div className="mx-auto w-full max-w-7xl bg-gray-900/80 backdrop-blur-lg border border-gray-700 rounded-xl sm:rounded-2xl shadow-2xl p-3 sm:p-4 md:p-6">
        <h1 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-5 text-center">🏋️ FitAI Coach</h1>

        {topBar && <div className="mb-4">{topBar}</div>}

        {systemMessage && (
          <div className="mb-4 rounded-lg border border-emerald-600 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100">
            {systemMessage}
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-lg border border-red-600 bg-red-900/40 text-red-200 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-5">
          <section className="border border-gray-700 bg-gray-900/70 rounded-xl p-3 sm:p-4 flex flex-col h-[62vh] min-h-[420px] max-h-[760px] lg:min-h-[700px] lg:h-auto">
            <h2 className="text-xl font-semibold mb-3">Chat en tiempo real</h2>

            <div ref={chatRef} className="flex-1 overflow-y-auto space-y-3 pr-1">
              {chat.map((m, idx) => (
                <div
                  key={idx}
                  className={`max-w-[95%] sm:max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
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

            <form onSubmit={onEnviarMensaje} className="mt-4 flex flex-col sm:flex-row gap-2">
              <textarea
                className="flex-1 p-3 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 min-h-24 sm:min-h-14 max-h-36"
                placeholder={chatHabilitado ? "Escribe aqui tu mensaje..." : "Inicia sesion con Google para hablar con el coach."}
                value={mensaje}
                disabled={!chatHabilitado || loading}
                onChange={(e) => onMensajeChange(e.target.value)}
              />
              <button
                type="submit"
                disabled={loading || !chatHabilitado}
                className="w-full sm:w-auto self-stretch sm:self-end bg-gradient-to-r from-green-400 to-blue-500 text-black font-bold px-4 py-3 rounded-lg hover:scale-[1.02] transition disabled:opacity-60"
              >
                Enviar
              </button>
            </form>

            {!chatHabilitado && (
              <div className="mt-3 p-3 rounded-lg border border-amber-700 bg-amber-900/30 text-amber-200 text-sm">
                Debes iniciar sesion con Google para conversar con el agente.
              </div>
            )}

            {resultado?.estado === "faltan_datos" && (
              <div className="mt-3 p-3 rounded-lg border border-yellow-600 bg-yellow-900/20 text-yellow-100 text-sm">
                Campos pendientes: {resultado.campos_faltantes.join(", ")}
              </div>
            )}
          </section>

          <section className="border border-gray-700 bg-gray-900/70 rounded-xl p-3 sm:p-4 h-[58vh] min-h-[360px] sm:h-[62vh] md:h-[66vh] lg:h-[70vh] lg:min-h-[540px] max-h-[860px] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-3">Rutina recomendada</h2>

            {!resultado && (
              <p className="text-gray-300 text-sm">
                Conversa con el coach. El te pedira edad, estatura, peso, objetivo y dias de entrenamiento.
              </p>
            )}

            {resultado && (
              <div className="space-y-4">
                <div className="p-3 bg-gray-800/70 rounded-lg border border-gray-600 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-gray-100">Datos para armar tu rutina</p>
                    <p className="text-xs text-gray-400 mt-1">El coach va completando cada dato a medida que conversas.</p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {estadoPerfil.map((campo) => (
                      <div
                        key={campo.key}
                        className={`rounded-md border p-2.5 flex items-center justify-between gap-3 ${
                          campo.ok
                            ? "border-emerald-600/70 bg-emerald-900/20"
                            : "border-amber-600/70 bg-amber-900/20"
                        }`}
                      >
                        <span className="text-gray-100 font-medium">{campo.label}</span>
                        <span className={`font-semibold text-right ${campo.ok ? "text-emerald-300" : "text-amber-300"}`}>
                          {campo.ok ? "Completo" : "Pendiente"}
                          <span className="block text-[11px] font-normal mt-0.5 text-gray-300">
                            {campo.ok ? campo.valor : campo.valor}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {resultado.preferencias_detectadas && (
                  <div className="p-3 bg-purple-900/30 rounded-lg border border-purple-600 space-y-2">
                    <p className="text-sm font-semibold text-purple-300">✨ Preferencias detectadas:</p>

                    {resultado.preferencias_detectadas.equipamiento.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs text-gray-400">Equipamiento:</span>
                        {resultado.preferencias_detectadas.equipamiento.map((eq) => (
                          <span
                            key={eq}
                            className="px-2 py-1 text-xs bg-orange-600/70 text-orange-100 rounded-full border border-orange-500"
                          >
                            {eq}
                          </span>
                        ))}
                      </div>
                    )}

                    {resultado.preferencias_detectadas.formatos.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs text-gray-400">Formatos:</span>
                        {resultado.preferencias_detectadas.formatos.map((fmt) => (
                          <span
                            key={fmt}
                            className="px-2 py-1 text-xs bg-blue-600/70 text-blue-100 rounded-full border border-blue-500"
                          >
                            {fmt}
                          </span>
                        ))}
                      </div>
                    )}

                    {resultado.preferencias_detectadas.restricciones.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs text-gray-400">Restricciones:</span>
                        {resultado.preferencias_detectadas.restricciones.map((rest) => (
                          <span
                            key={rest}
                            className="px-2 py-1 text-xs bg-red-600/70 text-red-100 rounded-full border border-red-500"
                          >
                            {rest}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {INTENSIDADES.map((intensidad) => {
                    const activa = intensidadActiva === intensidad;
                    return (
                      <button
                        key={intensidad}
                        onClick={() => onIntensidadChange(intensidad)}
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
                        {planActivo?.dias?.map((dia) => {
                          const detallePendiente = diasEnCarga.includes(dia.dia);
                          return (
                            <button
                              key={dia.dia}
                              onClick={() => onDiaChange(dia.dia)}
                              className={`px-3 py-1.5 rounded-md text-sm border ${
                                diaActivo === dia.dia
                                  ? "bg-blue-500 text-black border-blue-400"
                                  : "bg-gray-900 border-gray-700 text-gray-200"
                              }`}
                            >
                              <span className="inline-flex items-center gap-2">
                                {dia.dia}
                                {detallePendiente && (
                                  <span
                                    className="inline-block h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin"
                                    aria-label="Cargando detalle"
                                    title="Cargando detalle"
                                  />
                                )}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {diaSeleccionado ? (
                      <div className="space-y-3">
                        <div className="p-3 bg-gray-800 rounded-lg border border-gray-600">
                          <p className="font-semibold text-green-300">{diaSeleccionado.dia}</p>
                          <p className="text-xs sm:text-sm text-gray-200">{diaSeleccionado.grupo_muscular}</p>
                          <p className="text-[11px] sm:text-xs text-gray-400">{diaSeleccionado.foco}</p>
                        </div>

                        {loadingDetalle && diaSeleccionado.ejercicios.length === 0 && (
                          <div className="p-3 bg-gray-800 border border-gray-600 rounded-lg text-xs sm:text-sm text-gray-300 animate-pulse">
                            Cargando detalle del dia...
                          </div>
                        )}

                        {!loadingDetalle && diaSeleccionado.ejercicios.length === 0 && (
                          <div className="p-3 bg-gray-800 border border-gray-600 rounded-lg text-xs sm:text-sm text-gray-300">
                            Aun no se cargo el detalle de este dia. El coach debe completarlo en segundo plano.
                          </div>
                        )}

                        {diaSeleccionado.ejercicios.map((item, index) => (
                          <div key={index} className="p-3 bg-gray-800 border border-gray-600 rounded-lg">
                            <h3 className="font-bold text-sm sm:text-base leading-snug">💪 {item.ejercicio}</h3>
                            <p className="text-[11px] sm:text-xs text-blue-300 mt-1">Grupo: {item.grupo_muscular}</p>
                            <p className="text-xs sm:text-sm text-gray-300 mt-1">Series/Reps: {item.series_reps}</p>
                            <p className="text-xs sm:text-sm text-gray-300">Descanso: {item.descanso}</p>
                            <p className="text-xs sm:text-sm text-gray-300 mt-2 leading-relaxed">Como hacerlo: {item.instrucciones}</p>
                            {item.tips && <p className="text-xs sm:text-sm text-yellow-200 mt-1 leading-relaxed">Tip: {item.tips}</p>}

                            {(item.video_busqueda || item.ejercicio) && (
                              <a
                                className="inline-block mt-2 text-xs sm:text-sm text-cyan-300 underline"
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
