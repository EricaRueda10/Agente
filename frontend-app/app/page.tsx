"use client";
import { useState } from "react";

export default function Home() {
  const [objetivo, setObjetivo] = useState("");
  const [pasos, setPasos] = useState(0);
  const [sueno, setSueno] = useState(0);
  const [resultado, setResultado] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const generarRutina = async () => {
    setLoading(true);

    const res = await fetch("http://localhost:8000/agente", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        objetivo,
        pasos: Number(pasos),
        sueno: Number(sueno),
      }),
    });

    const data = await res.json();
    setResultado(data.resultado);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black flex items-center justify-center p-6 text-white">
      
      <div className="bg-gray-900/80 backdrop-blur-lg border border-gray-700 rounded-2xl shadow-2xl p-8 w-full max-w-2xl">

        <h1 className="text-3xl font-bold text-center mb-6">
          🏋️ FitAI Coach
        </h1>

        {/* FORMULARIO */}
        <div className="space-y-4">
          <input
            className="w-full p-3 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder="Objetivo (ej: bajar grasa, ganar músculo)"
            value={objetivo}
            onChange={(e) => setObjetivo(e.target.value)}
          />

          <input
            className="w-full p-3 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500"
            type="number"
            placeholder="Pasos diarios"
            onChange={(e) => setPasos(Number(e.target.value))}
          />

          <input
            className="w-full p-3 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500"
            type="number"
            placeholder="Horas de sueño"
            onChange={(e) => setSueno(Number(e.target.value))}
          />

          <button
            onClick={generarRutina}
            className="w-full bg-gradient-to-r from-green-400 to-blue-500 text-black font-bold p-3 rounded-lg hover:scale-105 transition transform"
          >
            {loading ? "Generando..." : "Generar rutina inteligente"}
          </button>
        </div>

        {/* RESULTADO */}
        {resultado && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">📊 Resultado</h2>

            {/* INTENSIDAD */}
            <div className="mb-4 p-4 bg-gray-800 rounded-lg text-center border border-gray-600">
              <p className="text-sm text-gray-400">Nivel de entrenamiento</p>
              <p
                className={`text-2xl font-bold ${
                  resultado.intensidad === "alta"
                    ? "text-red-400"
                    : resultado.intensidad === "media"
                    ? "text-yellow-400"
                    : "text-green-400"
                }`}
              >
                {resultado.intensidad.toUpperCase()}
              </p>
            </div>

            {/* RUTINA */}
            <div className="space-y-3">
              {resultado.rutina.map((item: any, index: number) => (
                <div
                  key={index}
                  className="p-4 bg-gray-800 border border-gray-600 rounded-lg shadow"
                >
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    💪 {item.ejercicio}
                  </h3>
                  <p className="text-gray-300">⏱ {item.duracion}</p>

                  {item.detalles && (
                    <p className="text-sm text-gray-400 mt-1">
                      {typeof item.detalles === "string"
                        ? item.detalles
                        : JSON.stringify(item.detalles)}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* JUSTIFICACIÓN */}
            <div className="mt-6 p-4 bg-blue-900/40 border border-blue-700 rounded-lg">
              <strong className="text-blue-300">🧠 Justificación:</strong>
              <p className="mt-2 text-gray-300">
                {resultado.justificacion}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}