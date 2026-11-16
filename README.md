# Football AI Lab — versión 0.8 experimental

Sistema de análisis de fútbol alojado en GitHub Actions, sin instalaciones locales y sin apuestas automáticas. Todo el proyecto es público. **No garantiza ganancias.**

## Fase 3 — estadísticas postpartido y Top 3

- [Dashboard con desglose de estadísticas](https://rasekes86.github.io/football-ai-lab/): pulsa sobre un partido para ver goles, tiros, córners, tarjetas y la explicación de cada selección.
- [Auditoría de estadísticas finales](output/estadisticas_finales_verificadas.json) y [desglose por pronóstico](output/desglose_postpartido.json).
- [Reglas y fuentes de la liquidación](docs/FASE_3_POSTPARTIDO.md). Los datos ausentes no cuentan como fallos.

## Abrir los resultados
- [Informe de las seis competiciones](output/informe.md): LaLiga, Segunda División, Premier League, Bundesliga, Serie A y Ligue 1; pronósticos para los siguientes 14 días.
- [Pronósticos del modelo Poisson/Elo](output/predicciones.csv).
- [Backtest retrospectivo Poisson/Elo](output/backtest_resumen.json) y [detalle](output/backtest.csv).
- [Contexto Machina Sports](output/contexto_machina.json): clasificaciones y, en Premier, bajas reportadas (NO necesariamente confirmadas).
- [Comparaciones InferSports](output/mercados.csv): referencias sin margen, NO cuotas reales necesariamente disponibles.
- [XGBoost experimental y validación](output_ml/validacion.json) y [predicciones ML](output_ml/predicciones_ml.csv).
- [Estado de los roles especializados](output/estado_agentes.json).
- [Panel Google Sheets](https://docs.google.com/spreadsheets/d/1XSDuxhggZ3UCNkJDmakYG8WQdWPcqQtykj49DuIqJsU/edit): fotografía; las pestañas Auto requieren autorizar IMPORTDATA desde navegador de escritorio.

## Cómo preguntar al sistema desde ChatGPT

Gracias a la conexión GitHub, podemos generar solicitudes que GitHub Actions responde en un Issue público.

- **Prepartido:** título del Issue `[ANALISIS] Athletic Club vs Espanyol | 2026-11-20`.
- **Instantánea de directo:** título del Issue `[DIRECTO] Manchester City vs Fulham | 2026-11-21`.

El usuario puede pedírmelo en lenguaje natural desde ChatGPT; el flujo utiliza los títulos estandarizados. El análisis en directo consulta el proveedor en ese momento y rechaza instantáneas obsoletas. **No es vigilancia continua**, ni un modelo nuestro de predicción minuto a minuto. Ver [guía de solicitudes](docs/REQUESTS.md) y [Issue de prueba real](https://github.com/rasekes86/football-ai-lab/issues/1).

## Componentes del sistema

1. **Datos:** resultados CSV de football-data.co.uk + calendario del endpoint público no oficial de ESPN.
2. **Contexto:** Machina Sports / sports-skills (clasificaciones en cinco ligas, bajas reportadas de Premier).
3. **Predicción habitual:** Poisson/Elo de ponderación fija 70/30, sin calibración prospectiva.
4. **ML experimental:** XGBoost con 4.261 partidos de entrenamiento y 1.096 posteriores para evaluación en el primer ensayo. Se recalcula semanalmente. NO se mezcla automáticamente.
5. **Mercado:** InferSports keyless, hasta tres consultas por ejecución, con control de antigüedad y consistencia. The Odds API permanece desactivada sin clave y activación explícita.
6. **Auditoría:** walk-forward Brier/log loss y comparación entre modelos sobre una muestra de validación temporal.
7. **Publicación:** GitHub Actions escribe CSV, JSON y Markdown; seguimiento histórico de predicciones prepartido.

Las skills MIT originales de Machina Sports, Football Match Predictor e InferSports están disponibles en `.agents/skills/` y `.claude/skills/`. La skill de auditoría está adaptada de Claude Quant y conserva atribución en [proveniencia](third_party/UPSTREAM.md). Las skills no equivalen a agentes LLM autónomos ejecutándose diariamente: el cron funciona con Python y evita consumo de tokens de IA por partido.

## Automatización gratis
- [Daily](.github/workflows/daily.yml): diariamente a las 07:17 UTC y manualmente.
- [ML](.github/workflows/ml.yml): los lunes a las 06:43 UTC y manualmente.
- [Requests](.github/workflows/request.yml): cuando el propietario abre un Issue con los prefijos admitidos.

Los programas corren en runners públicos de GitHub; las fuentes gratuitas tienen límites y condiciones, por lo que no se garantiza coste cero fuera de las cuotas incluidas o si se activan servicios de pago. No se capturan cuotas de casas de apuestas para apostar con dinero real.

## Principales límites
- Datos gratuitos con cobertura desigual, horarios y nombres que pueden cambiar.
- Ni XGBoost ni Poisson/Elo han probado ventaja sobre precios reales de casas; métricas históricas no demuestran rentabilidad.
- Machina informa contextos que todavía NO se usan como features predictivas.
- Directo bajo demanda no sustituye a un monitor de baja latencia para toda una jornada.
- Google Sheets necesita permitir la importación externa para sincronizar automáticamente.
- No se ha desplegado un servidor continuo ni LangGraph: los "agentes" del flujo automático son roles deterministas Python.

## Desarrollo
```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m football_ai_lab.pipeline --days 14 --backtest-games 120
python -m pip install -e '.[ml]'
python -m football_ai_lab.ml --days 14
```

[Arquitectura y estado exacto de las fases](docs/ARCHITECTURE.md).


## Novedades v0.5 — datos, seguimiento prospectivo y auditoría
Consulta [la guía detallada de las fases 1, 2 y 4](docs/FASES_1_2_4.md).

- [Contexto de partidos](output/contexto_partidos.json): últimos 5 encuentros, tiros, descanso, enfrentamientos y cobertura.
- [xG histórico verificado (muestra limitada)](output/contexto_xg.json): Understat/Machina si la fuente devuelve datos comprobables.
- [Resultados reales y calibración](output/evaluacion_real.json): separa pronósticos archivados de backtests.
- [Discrepancias entre modelos](output_ml/discrepancias.csv): diferencias informativas, nunca apuestas.
- [Auditoría de pesos temporales](output_ml/auditoria_pesos.json): candidatos no aplicados automáticamente.

Las probabilidades oficiales siguen utilizando el consenso Poisson/Elo 70/30 hasta que exista evidencia suficiente para cambiarlo.


## Nuevo selector de mercados (v0.6)
- Calcula un **Top 3 por partido** y un **Top 3 general** basado en probabilidades experimentales: 1X2, doble oportunidad, total de goles, ambos marcan, goles por equipo y hándicaps de medio gol (dos vías).
- Para evitar tres selecciones casi idénticas, usa como máximo una de cada familia por partido. Se aplica un mínimo de probabilidad del 55 % y una **cuota justa matemática mínima de 1,15**, no una cuota ofrecida.
- Los córners, tiros, tiros a puerta y tarjetas se calculan solo como **exploratorios** cuando hay muestras históricas suficientes; no aparecen en el Top 3 hasta superar validación temporal por mercado.
- **Jugadores** (tiros, goleadores, tarjetas) siguen bloqueados hasta disponer de datos de participación y métricas individuales válidas.
- **Valor esperado exploratorio**: únicamente si existen cuotas 1X2 realmente ofrecidas y recientes de The Odds API con activación explícita; no inventa cuotas para goles ni dobles oportunidades. La fuente InferSports solo aporta referencias fair (no ofrecidas).
- Archivos [selecciones.json](output/selecciones.json), [selecciones.csv](output/selecciones.csv); también aparece un resumen en el [informe diario](output/informe.md) y al analizar un partido mediante GitHub Issues.
- Son estimaciones experimentales para investigación; no constituyen apuestas recomendadas ni tienen una ventaja financiera demostrada.


## Validación temporal de córners, tiros y tarjetas (v0.7)
- Nuevo auditor [`output/validacion_conteos.json`](output/validacion_conteos.json): prueba cada mercado y línea contra la frecuencia histórica conocida **antes** del partido en cinco ligas.
- Exige al menos 85 observaciones válidas, cobertura mínima 65 %, mejora mínima de Brier de 0,003, mejora mínima de log loss de 0,005 y error de calibración ECE ≤0,09.
- **Solo** las líneas que superen todos los filtros pueden competir con los mercados de goles en el Top 3, como **aptas retrospectivamente y pendientes de confirmación prospectiva**.
- Si ninguna línea supera la auditoría, no se incorpora ninguna al ranking. No se inventan tiros de jugadores ni cuotas reales.
- Las solicitudes desde ChatGPT reutilizan la auditoría publicada únicamente si tiene menos de ocho días.


## Fase v0.8 — seguimiento por mercado, dossier completo y jugadores
- [Informe unificado de partidos (Markdown)](output/informes_partidos.md) y [datos estructurados](output/informes_partidos.json). Incluye pronóstico, forma, tiros/córners, descanso, historial, Top 3, XGBoost cuando sea reciente y explícitas ausencias de datos.
- [Selecciones originales congeladas](output/historico_selecciones.csv): primera publicación prepartido, no se sustituye retrospectivamente por un Top 3 posterior.
- [Resultados y liquidación de cada mercado](output/seguimiento_selecciones.csv) y [métricas prospectivas](output/evaluacion_selecciones.json): por liga, mercado y origen del modelo; sin penalizar estadísticas ausentes.
- [Muestra de jugadores ya disputados](output/jugadores_historico.json): consulta acotada de ESPN summary (público no oficial) y registro de titularidad y estadísticas existentes, nunca supuestas. **No predice todavía tiros/goles individuales.** Esta fuente es experimental, de cobertura variable y no autoriza uso comercial.
- [Telegram opcional](docs/TELEGRAM.md): el módulo envía un resumen en ejecuciones manuales o programadas solo si se configuran en GitHub los dos secretos; no requiere pagos. Actualmente sin activar en la cuenta.
- [Guía de la nueva versión](docs/AVANCES_V08.md): capacidades reales, datos ausentes y requisitos pendientes.

**No se ha activado ninguna API de pago, no se han conectado casas de apuestas y no hay apuestas automáticas.**


- [Cobertura y calidad de las estadísticas individuales](output/cobertura_jugadores.json): distingue partidos realmente jugados de suplentes no utilizados y cuantifica cuándo hay muestras históricas suficientes para INVESTIGAR, nunca para activar automáticamente apuestas de jugadores.


## Derechos y condiciones de las fuentes

Consulta [las notas sobre licencias y límites de uso](docs/FUENTES_Y_DERECHOS.md).
La gratuidad de los datos no implica autorización ilimitada para bots, IA o uso comercial.


## LaLiga Hypermotion — Segunda División (SP2)
Segunda División se ha integrado como sexta competición con CSV históricos de
Football-Data y calendario de ESPN (código `esp.2`). Los cálculos y las
auditorías de mercado se separan de los de Primera; no se habilitan
automáticamente córners, tiros ni tarjetas si su validación no es suficiente.
Las cuotas externas, xG auténtico y alineaciones siguen sujetos a cobertura.
[Guía de la integración](docs/SEGUNDA_DIVISION.md).


## Cuotas >1,50: evaluación también después del partido

Se guardan por separado las cuatro selecciones de Segunda comentadas el 15/11/2026, con las probabilidades **prepartido congeladas** y las cuotas anotadas como **INDICATIVAS_NO_VERIFICADAS**. Cuando se conozca el resultado, [seguimiento_oportunidades_150.csv](output/seguimiento_oportunidades_150.csv) calcula acierto/error, Brier y retorno **hipotético** de una unidad; [evaluacion_oportunidades_150.json](output/evaluacion_oportunidades_150.json) resume los resultados y [oportunidades_150.md](output/oportunidades_150.md) los presenta de forma legible.

Solo en caso de contar con una oferta real registrada por API y fecha se distinguirá el análisis del precio capturado; no hay apuestas ejecutadas ni beneficio realizado. [Documentación](docs/SEGUIMIENTO_CUOTAS_150.md).

### Explorador de mercados

En [Football AI Lab Dashboard](https://rasekes86.github.io/football-ai-lab/#markets) puedes filtrar el histórico real de las seis ligas por córners, faltas, tiros, goles, tarjetas, 1X2, doble oportunidad y ambos marcan. Muestra frecuencias por línea y liga, totales por partido y **acierto prospectivo del Top 3 en una métrica separada**. Los datos de faltas sin fuente verificable permanecen ausentes, nunca se estiman. Archivo derivado: `output/mercados_historicos.json` (últimos 365 días).

### Ver pronósticos futuros por categoría

[Explorar próximos pronósticos por mercado](https://rasekes86.github.io/football-ai-lab/#markets):
selecciona «Córners», «Tiros», «Doble oportunidad» u otra categoría para ver
los próximos partidos con sus líneas y probabilidades del modelo. El histórico
real se mantiene en un desplegable secundario. La fuente es
`output/pronosticos_mercados_futuros.json`, actualizada con el motor diario.
Se distingue el Top 3 original de los pronósticos adicionales y no se inventan
probabilidades de faltas ni tarjetas rojas, mercados aún sin modelo prepartido.

### Fase 4 — Auditoría prospectiva de mercados

El [Explorador de mercados](https://rasekes86.github.io/football-ai-lab/#markets) permite consultar los pronósticos futuros y, debajo, un cuadro de **fiabilidad y calibración prospectivas** por categoría y liga. Se archivan las primeras probabilidades de cada partido antes del inicio, se liquidan solo con datos verificables y se calculan tasa de acierto, Brier, logloss y ECE, con advertencias de muestra pequeña. No altera el Top 3 original ni reescribe históricos: [metodología](docs/FASE_4_AUDITORIA.md). Los informes nuevos son `output/historico_mercados_futuros.csv`, `output/seguimiento_mercados_futuros.csv` y `output/fiabilidad_mercados_futuros.json`.

### Fase 5 — Radar de pronósticos futuros

[Abre el Radar inteligente](https://rasekes86.github.io/football-ai-lab/#radar). Filtra mercados futuros por liga, probabilidad, calidad, cobertura y cuota justa teórica. Cada encuentro presenta comparativas de estadísticas previas de ambos equipos en ventanas de 5/10/20 partidos (general o local/fuera), con muestras verificables y acceso a su ficha. El radar no altera el Top 3 ni atribuye rentabilidad a las probabilidades. Consulta la [metodología de la Fase 5](docs/FASE_5_RADAR.md).

### Fase 7 — Resúmenes y resultados por Telegram

Se ha implementado la [alerta opcional por Telegram](docs/TELEGRAM.md) sobre los pronósticos futuros y su liquidación prospectiva de la Fase 4. Permite filtrar mercados, ligas, probabilidad, calidad y horizonte; notifica aciertos y fallos verificados sin contar estadísticas ausentes como derrotas. El envío automático queda **desactivado hasta que configures dos secretos y la variable de activación en GitHub**, sin compartirlos con ChatGPT. El estado anti-duplicados solo se confirma después de una entrega correcta. Reutiliza el análisis diario, sin nuevas APIs de pago.

### Fase 8 — Cuotas reales (integración opcional)

[Cuotas reales · Dashboard](https://rasekes86.github.io/football-ai-lab/#realodds).
El comparador consulta **The Odds API V4** únicamente si has habilitado
`ENABLE_REAL_ODDS=true` y guardado `THE_ODDS_API_KEY` como secreto de GitHub.
Contrasta 1X2 y goles totales con precio de bookmaker, coincidencia exacta
de línea y sentido, fecha de actualización, margen de la misma casa y
diferencia de probabilidad. No sustituye la simulación de +1,50,
no infiere cuotas inexistentes y **no afirma rentabilidad**.
Guía de alta, costes y metodología:
[docs/FASE_8_CUOTAS_REALES.md](docs/FASE_8_CUOTAS_REALES.md).

