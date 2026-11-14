# Solicitudes desde ChatGPT con GitHub Issues

Si GitHub está conectado a ChatGPT, se puede crear una consulta pública a través del conector y después leer el comentario generado por GitHub Actions.

## Prepartido
Título exacto:
`[ANALISIS] Athletic Club vs Espanyol | 2026-11-20`

- Verifica el calendario en una de cinco ligas, con equipo local primero y fecha española.
- Obtiene Poisson/Elo, marcador esperado y referencia InferSports si existe.
- Si el partido no coincide o faltan datos, no se inventa ninguna estimación.
- Enlace de la prueba completada: https://github.com/rasekes86/football-ai-lab/issues/1

## Directo (instantánea, no seguimiento automático)
Título exacto:
`[DIRECTO] Manchester City vs Fulham | 2026-11-21`

- Solo el día del partido (tolerancia ±1 día UTC); nunca para un partido lejano.
- Consulta la skill read-only de InferSports en ese momento.
- Exige equipos, fecha, estado live y una marca temporal verificable dentro de cinco minutos.
- Si la fuente tiene probabilidades implícitas de mercado válidas, las muestra; NO se presentan como probabilidades de un modelo propio entrenado in-play.
- Puede responder con "sin datos" si no hay cobertura. No se ha comprobado en un partido realmente en juego.

## Privacidad y costes
Todos los Issues y sus respuestas son públicos: no incluyas datos personales. El workflow solo se activa con Issues creados por el dueño del repositorio. Las acciones y consultas están sometidas a límites gratuitos. No hay automatización de apuestas ni monitorización minuto a minuto desatendida.
