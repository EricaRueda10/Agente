# FitAI Coach - Frontend

Frontend de FitAI Coach construido con Next.js.

## Requisitos

- Node.js 18+ (recomendado: Node.js 20 o superior)
- npm
- Backend corriendo en http://localhost:8000

## Levantar el proyecto

Ejecuta estos comandos desde esta carpeta (frontend-app):

```bash
npm install
npm run dev
```

Luego abre:

- http://localhost:3000

## Scripts disponibles

```bash
npm run dev    # modo desarrollo
npm run build  # build de produccion
npm run start  # ejecutar build en produccion
npm run lint   # linting
```

## Flujo completo (frontend + backend)

Este frontend hace peticiones POST a:

- http://localhost:8000/agente

Por eso debes tener el backend activo al mismo tiempo.

## Errores comunes

1. Error Cannot find module react o react/jsx-runtime
	Solucion:

```bash
npm install
npm run dev
```

2. Error de conexion al generar rutina
	Causa: backend apagado o puerto diferente.
	Solucion: confirma que FastAPI este corriendo en el puerto 8000.

3. Error 500 desde backend
	Causa frecuente: falta OPENAI_API_KEY.
	Solucion: define la variable en el entorno del backend antes de levantar uvicorn.
