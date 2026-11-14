# Arquitectura v0.2 y estado de integración

## Núcleo diario
GitHub Actions → agentes Python de datos → modelo Poisson/Elo → mercado opcional → auditoría retrospectiva → seguimiento → publicación JSON/CSV/Markdown.

No hay siete LLM ejecutándose por cada partido; los agentes del pipeline son funciones especializadas. Las skills de Codex y Claude son para sesiones de desarrollo/investigación, no son parte del cron.

## Estado por fases
- Fase 1 (cloud gratis): completada, acciones programadas y manuales.
- Fase 2 (doble modelo): completada, Poisson y Elo combinados con pesos fijos, sin calibración independiente.
- Fase 3 (evaluación): walk-forward retrospectivo implementado con comparación a baseline móvil. Pruebas prospectivas pendientes.
- Fase 4 (cuotas): The Odds API 1X2 implementado, desactivado por defecto; la skill de InferSports instalada para uso interactivo, pero no conectada al motor diario.
- Fase 5 (agentes): siete roles con estados en output/estado_agentes.json. No se emplea LangGraph porque el flujo es secuencial y determinista.
- Fase 6 (ChatGPT): el repositorio y sus resultados pueden leerse desde ChatGPT mediante conexión a GitHub. Google Sheets requiere autorizar IMPORTDATA desde navegador de escritorio.

## Archivos auditables
Consulta output/predicciones.csv, output/backtest.csv, output/mercados.csv, output/estado_agentes.json y output/informe.md.

## Riesgos
El calendario depende de un endpoint público no oficial; los nombres pueden ser distintos entre fuentes. No se publican pronósticos con datos insuficientes. El backtest mide error predictivo y no rentabilidad; ninguna comparación de cuotas sería fiable sin marca temporal y validación.


### Extensión InferSports
Se añadió un adaptador Python para la skill original: consulta fair.sh de forma limitada y solo incorpora referencias de probabilidades si coinciden los equipos, la fecha y la marca temporal, sin clave. No coloca apuestas, no modifica el modelo y no garantiza datos para cada encuentro. La integración de The Odds API sigue siendo opcional, bajo consentimiento explícito mediante secretos.
