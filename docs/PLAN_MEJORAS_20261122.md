# Plan por fases — Football AI Lab + Basketball AI Lab (22/11/2026)

## Reglas no negociables

- Los Top 3 archivados, adicionales archivadas, sus timestamps y sus estados históricos son la fuente de verdad. Nunca sustituirlos por cálculos retrospectivos.
- Mantener separado Top 3, una adicional real, cuotas teóricas y líneas exploratorias.
- Ninguna fuente de apuestas o API debe consultarse si no estaba previamente habilitada. La optimización redistribuye el presupuesto gratuito, no lo aumenta.
- Ausencia de dato, de precio o de resultado nunca equivale a fallo de la selección. Toda rentabilidad mostrada es hipotética.
- Todas las novedades se prueban sobre una rama y se fusionan únicamente tras validación.

## Fases y criterio de aceptación

| Fase | Fútbol | Baloncesto | Aceptación |
| --- | --- | --- | --- |
| 1. Adicionales NBA | Referencia comparativa, sin mezclar ligas o deportes | Diagnóstico por mercados y versión, separado del Top 3 | Solo adicionales reales; no retocar contratos antiguos; no reajustar umbrales con muestra pequeña |
| 2. Cuotas Top 3 fútbol | Prioridad de partidos con contrato exactamente comparable; estados por mercado | Mantener la adicional real aparte de cuotas matemáticas | Misma cuota de peticiones por hora y mismos cooldowns; sin precios inventados |
| 3. Datos diarios | Desglose existente por día y liga, sin duplicar módulos | Nuevo desglose por noche NBA, mercado y versión | Vista estable con fechas de Madrid; pendientes no son fallos |
| 4. Salud | Indicador de antigüedad de la publicación y fuentes no disponibles | Indicador de antigüedad, pendientes y siguiente cron **previsto** | No confundir publicación con ejecución programada; la vigilancia existente sigue operando |
| 5. Calibración | Probabilidad archivada frente a acierto por origen/franja | Comparación por franja y modelo | Solo selecciones originales liquidadas; sin mezclar retrospectivo y prospectivo |
| 6. Móvil y navegación | Diagnósticos dentro del panel avanzado, plegables | Auditoría plegable con dos métricas principales separadas | Fichas existentes y filtros básicos intactos; sin sobrecargar la portada |

## Etapas de implantación

**A — Seguridad y diagnóstico:** congelar la semántica 3+1, añadir informes puros y regresiones. Esta fase NO modifica el selector del modelo ni reescribe historia.

**B — Cuotas:** priorizar las coincidencias exactas del Top 3 dentro del presupuesto que ya existe. El aumento de cobertura se comprobará de forma prospectiva tras rondas reales; no se declara mejora numérica hasta entonces.

**C — Visualización:** desglose de resultados y calibración, estado de salud y diseño progresivo para móvil, usando archivos ya publicados.

**D — Verificación:** ejecutar tests Python y Node en PR, validar GitHub Actions, verificar que los commits no afectan a `data/**` ni `output/**` históricos, y comprobar publicación de Pages tras merge.

**E — Ajuste del predictor (pendiente de evidencia):** no endurecer o relajar automáticamente la selección NBA por 15 adicionales. Requerir muestras mayores independientes por mercado, backtest sin filtración temporal y validación prospectiva. Mantener intacto el histórico incluso si se decide activar una versión futura.

## Reversión

Revertir únicamente los commits de código/web y pruebas del PR. Los archivos originales no se tocan y los pronósticos futuros no se vuelven a puntuar a posteriori. Los nuevos diagnósticos se derivan en el navegador o en ficheros de evaluación, nunca sustituyen el histórico.
