# Football AI Lab — versión 0.4 experimental

Sistema de análisis de fútbol alojado en GitHub Actions, sin instalaciones locales y sin apuestas automáticas. Todo el proyecto es público. **No garantiza ganancias.**

## Abrir los resultados
- [Informe de los cinco campeonatos](output/informe.md): LaLiga, Premier League, Bundesliga, Serie A y Ligue 1; pronósticos para los siguientes 14 días.
- [Pronósticos del modelo Poisson/Elo](output/predicciones.csv).
- [Backtest retrospectivo Poisson/Elo](output/backtest_resumen.json) y [detalle](output/backtest.csv).
- [Contexto Machina Sports](output/contexto_machina.json): clasificaciones y, en Premier, bajas reportadas (NO necesariamente confirmadas).
- [Comparaciones InferSports](output/mercados.csv): referencias sin margen, NO cuotas reales necesariamente disponibles.
- [XGBoost experimental y validación](output_ml/validacion.json) y [predicciones ML](output_ml/predicciones_ml.csv).
- [Estado de siete roles especializados](output/estado_agentes.json).
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
