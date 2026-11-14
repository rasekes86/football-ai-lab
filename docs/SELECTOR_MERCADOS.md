# Selector de mercados v0.6: estado, criterios y uso

## Función
Generar un Top 3 por partido y un Top 3 global para la próxima jornada, sin colocación de apuestas. Se publican en \`output/selecciones.json\` y \`output/selecciones.csv\`, y un resumen en \`output/informe.md\`.

## Modelos y mercados
- Probabilidades de resultado 1X2 y doble oportunidad (1X, X2, 12) calculadas exclusivamente mediante el consenso Poisson/Elo.
- Más/menos goles totales (0,5 a 4,5), goles de cada equipo (0,5 a 2,5), ambos marcan y hándicaps europeos de medio gol mediante distribución Poisson de goles.
- 1X2 Poisson/Elo y mercados de goles Poisson **no son perfectamente coherentes entre sí** por la mezcla Elo. Se identifica siempre la procedencia en cada selección.
- Córners, tiros, tiros a puerta y tarjetas: estimaciones exploratorias basadas en muestras históricas, dispersión y condición local/visitante; no se muestran en el Top 3 principal sin validación temporal específica.
- Los mercados de tiros de jugador, goleador o tarjetas de jugador no están implementados y nunca se inventan.

## Reglas del Top
- Probabilidad estimada mínima: 55 %.
- Cuota justa matemática mínima: 1,15. Esto evita mercados casi triviales, **no equivale a una cuota real disponible**.
- Máximo una selección por familia en el mismo partido. El Top global muestra como máximo una por partido.
- No exige rellenar las tres plazas si no hay candidatos aptos.
- Orden por probabilidad estimada, **no por rentabilidad**. Puede haber correlación entre categorías.
- Las probabilidades de goles todavía no tienen una evaluación de calibración prospectiva específica para cada mercado.

## Comparador de valor
- Solo se considera precio ofrecido si proviene de The Odds API, actualizado hace menos de seis horas y marcado como comparación de cuota real.
- La comparación usa EV teórico = probabilidad del modelo × cuota ofrecida - 1. Para publicar una discrepancia exploratoria se exige EV>3 %, sin que implique ventaja real comprobada.
- InferSports fair odds y las cuotas justas del modelo **NO son cuotas ofrecidas**.
- Si no hay fuente de cuotas reales activada, la lista de valor queda vacía y se informa de que faltan precios verificados.
- El modo valor está limitado por ahora a 1X2.

## Qué pedir desde ChatGPT
"Consulta Football AI Lab y enséñame las tres selecciones más probables para Real Madrid–Celta, con fuente de probabilidades, riesgos y datos no disponibles."
"Muéstrame el Top 3 global de Football AI Lab y comprueba si hay cuotas reales o solo cuotas justas."
"¿Qué mercados de córners y tiros siguen siendo exploratorios y cuáles no están disponibles?"

## Límites
No hay apuestas automáticas. No hay garantías de acierto ni rentabilidad. Los pronósticos se puntúan contra resultados posteriores en el auditor, pero el rendimiento por mercado todavía requiere backtesting y seguimiento adicional. Las cuotas se filtran por frescura y proveedor; las conexiones gratuitas pueden no cubrir un mercado. La información no debe interpretarse como una instrucción para apostar.
