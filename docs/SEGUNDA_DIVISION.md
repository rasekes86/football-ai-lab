# Football AI Lab · Segunda División (fase 0.9)

La Segunda División de España se añade como sexta competición a \`LEAGUES\`:
- \`SP2\` — Football-Data, CSV históricos de resultados y métricas opcionales.
- \`esp.2\` — ESPN, calendario y eventos; endpoint público no documentado.

**Todo queda separado de LaLiga de Primera (\`SP1\`).** Las estadísticas y el backtest
se calculan por liga. Los filiales, como Real Sociedad II, no se equiparan con los
primeros equipos. Solo se pronostican enfrentamientos con historial suficiente
y equivalencias de nombre verificables.

## Qué se añade al flujo existente
- Calendario, 1X2 Poisson/Elo, XGBoost semanal experimental, goles, dobles oportunidades,
  hándicaps, Top 3 y dossiers completos por encuentro.
- Historias de Segunda con goles y, si están disponibles, tiros, tiros a puerta,
  córners y tarjetas. El auditor walk-forward debe aprobar **cada línea SP2**
  antes de que pueda entrar en el Top 3.
- Seguimiento prospectivo por liga y por mercado, sin contar ausencias como fallos.

## Límites
- ESPN es una fuente no oficial y puede no publicar fechas o encuentros de todas
  las jornadas; el equipo debe estar identificado de manera exacta/normalizada.
- La cobertura y validez de estadística avanzada puede variar entre temporadas.
- Machina Sports no ofrece necesariamente clasificación de Segunda con el conector
  actual: se deja "sin dato", nunca se copia la de Primera.
- Understat/xG no se utiliza para Segunda: no hay garantía de cobertura.
- InferSports y cuotas reales no garantizan cobertura para SP2; sin fuente fiable,
  el sistema no declara apuestas de valor.
- Las cuotas justas son matemáticas, no precios ofrecidos. Los filtros
  retrospectivos NO validan prospectivamente una estrategia de apuestas.
- Los CSV gratuitos pueden tener restricciones de uso automatizado/comercial;
  revisar condiciones de las fuentes antes de ampliar el servicio.

## Pruebas
\`python -m unittest discover -s tests -v\`

## Ver resultados
\`output/informes_partidos.md\`, \`output/selecciones.json\`,
\`output/validacion_conteos.json\`, \`output/evaluacion_selecciones.json\`.
