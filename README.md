# Football AI Lab

Sistema experimental de análisis prepartido de fútbol en la nube. Sin instalar software local, sin apuestas automáticas y sin APIs de pago en el MVP.

## ¿Qué hace?
- Descarga resultados históricos de LaLiga y Premier League de [football-data.co.uk](https://www.football-data.co.uk/).
- Consulta calendarios públicos mediante el endpoint no oficial de ESPN (puede cambiar o fallar).
- Predice probabilidades 1X2 y over 2,5 con un modelo Poisson regularizado.
- Conserva las primeras predicciones realizadas antes de cada encuentro, y las evalúa cuando termina.
- Genera CSV derivados para Google Sheets y un informe en Markdown.
- Ejecuta pruebas y pipeline diariamente mediante GitHub Actions.

## Uso en la nube
En **Actions → Analisis futbol diario → Run workflow** puedes ejecutar el análisis manualmente. Automáticamente se intenta ejecutar cada día a las 07:17 UTC; la programación puede sufrir retrasos. Los CSV se publican en la carpeta output; no hay datos de demostración en esos archivos.

## Panel Google Sheets
[Ver panel](https://docs.google.com/spreadsheets/d/1XSDuxhggZ3UCNkJDmakYG8WQdWPcqQtykj49DuIqJsU/edit).

Para vincular los CSV, Google Sheets puede requerir autorización de la función IMPORTDATA desde navegador de escritorio. Más detalles en docs/CLOUD_SETUP.md.

## Desarrollo y pruebas
Python >=3.11, biblioteca estándar, sin clave API.

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m football_ai_lab.pipeline --demo
python -m football_ai_lab.pipeline --days 7
~~~

Los datos ficticios se escriben exclusivamente en output_demo, nunca en output.

## Limitaciones
- Los pronósticos NO equivalen a recomendaciones de apuestas, ni está demostrada ventaja económica.
- Sin cuotas de casas reales, sin lesiones, alineaciones, xG detallado ni análisis en directo.
- Fuentes públicas con posibles límites, errores o cambios de formato.
- Puede haber partidos sin pronóstico por nombres incompatibles o histórico insuficiente.
- Calibración y backtest walk-forward son el siguiente paso.
- No redistribuir datos externos sin autorización. Solo se guardan predicciones derivadas.

## Estructura
- src/football_ai_lab/sources.py: ingesta de datos.
- src/football_ai_lab/core.py: modelo Poisson.
- src/football_ai_lab/pipeline.py: generación y seguimiento.
- tests/: controles básicos de calidad.
- .github/workflows/daily.yml: ejecución en nube.
- AGENTS.md / CLAUDE.md: normas para Codex / Claude Code.


## Actualización v0.2 — fases 2 a 5
- Motor de consenso **70 % Poisson + 30 % Elo**; si Elo no dispone de suficientes datos, solo Poisson.
- Calendario consultado para **14 días**, no solo siete.
- Backtesting **walk-forward retrospectivo** (hasta 120 encuentros por liga) con Brier y log loss comparados con frecuencia histórica.
- Mercado: comparación 1X2 opcional mediante The Odds API, desactivada sin THE_ODDS_API_KEY y ENABLE_ODDS=1. No realiza apuestas.
- Agentes operativos: datos, contexto (sin configurar), predictor, mercado, auditor, evaluador y publicador. Son funciones Python, no LLM autónomos.
- Nuevos archivos: output/backtest.csv, output/backtest_resumen.json, output/mercados.csv y output/estado_agentes.json.
- Skills originales de Machina Sports, Football Match Predictor e InferSports disponibles en .agents/skills y .claude/skills. Skill de auditoría adaptada de Claude Quant.
- **Las skills externas no se ejecutan automáticamente en GitHub Actions** salvo pruebas offline de sus scripts. Consulta third_party/UPSTREAM.md y docs/ARCHITECTURE.md.
- **Google Sheets** aún requiere autorizar la importación automática desde navegador de escritorio; los datos presentes son una fotografía de los últimos resultados publicados.


## InferSports keyless en el pipeline (experimental)
El módulo src/football_ai_lab/infersports.py consulta **como máximo tres partidos por ejecución**, por medio de los scripts oficiales de InferSports. Rechaza resultados caducados, equipos distintos y probabilidades mal normalizadas. GitHub Actions habilita ENABLE_INFERSPORTS=1; si la fuente gratuita falla, los pronósticos Poisson/Elo siguen disponibles. No se obtienen cuotas ofrecidas de esa referencia, solo probabilidades de mercado sin margen. La comparación es informativa y no implica una apuesta recomendable.
