# Fase 3 — Liquidación postpartido verificable (6 ligas)

## Qué se publica

El motor diario sigue calculando el Top 3 *antes* de cada partido y congelándolo en
`output/historico_selecciones.csv`. Este archivo **no se modifica nunca por un resultado
postpartido**. Las cuotas de `output/historico_oportunidades_150.csv` siguen separadas.

Se añaden dos archivos derivados:
- `output/estadisticas_finales_verificadas.json`: caché de estadísticas ESPN summary y
  auditoría. Solo aparece una estadística si fue realmente devuelta como entero no
  negativo, con nombre inequívoco, y si coinciden competición, fecha local, dos
  equipos, marcador final y evento.
- `output/desglose_postpartido.json`: estado y explicación de cada selección archivada;
  goles de cada equipo, tiros, tiros a puerta, córners, amarillas y rojas, cada una
  con datos local/visitante/total o `null`, procedencia y URL cuando existe.

## Fuentes / reglas

1. `football-data.co.uk` (CSV de ligas): estadísticas que ya están en el histórico
   se reutilizan para la liquidación. Las celdas vacías se conservan como `None`,
   **nunca se completan con cero ni con estimaciones**. Las fechas y los nombres
   se normalizan con las mismas equivalencias que usa el motor.
2. Marcadores: resultados oficiales registrados y cotejados, más resultados ESPN
   con estado explícito de finalización. Se aplican los controles de
   `verified_results.py`.
3. ESPN `scoreboard?dates=YYYYMMDD`: únicamente después de dos horas desde el
   inicio y con `status.type.completed == true` y estado final.
4. ESPN `summary?event={event_id}`: solo se consulta cuando falta alguna de las
   métricas de conteo necesarias para las selecciones archivadas. Verifica que el
   ID, los clubes y los goles coinciden con el partido previamente validado.
   Si discrepa, se **descartan sus estadísticas** (incluido un marcador
   aparentemente parecido). Se rechazan partidos duplicados por identidad.
5. Métricas reconocidas: `totalShots`/`shots`, `shotsOnTarget`/`shotsOnGoal`,
   `cornerKicks`/`corners`, `yellowCards`, `redCards`. Solo números enteros
   inequívocos: no se interpretan fracciones ni porcentajes como conteos.
6. Caché: reutiliza los datos con mismo encuentro y mismo marcador cuando las
   API gratuitas no responden; el cache no sobrescribe estadísticas que existan
   en el histórico CSV.

La consulta se limita a 24 jornadas-liga y 18 resúmenes de partido por ejecución
diaria. Si se superan los límites, faltan estadísticas o hay conflicto, la
selección queda `ESTADISTICA_NO_DISPONIBLE`. Si falta marcador, se mantiene
`RESULTADO_NO_DISPONIBLE`. Una ausencia no es una pérdida.

**Fuentes públicas experimentales:** ESPN site API no es una API oficial
garantizada ni tiene cobertura uniforme por competición o partido.
El proveedor football-data.co.uk establece restricciones de uso en su propia
web. Este proyecto se plantea como uso personal de investigación; revisar sus
condiciones antes de reutilizar o distribuir conjuntos de datos derivados a
escala comercial.

## Separación temporal

La ampliación de históricos es exclusiva para `settle_selections`,
`evaluate_offers` y `prospective_evaluate` del pipeline. Los modelos
Poisson/Elo, el entrenamiento, el selector prepartido, la validación temporal
retrospectiva y los pronósticos archivados continúan usando **el histórico
original**. No hay aprendizaje automático en línea ni beneficios demostrados.

## Pruebas y trazabilidad

```bash
python -m unittest discover -s tests -v
python -m football_ai_lab.pipeline --days 14 --backtest-games 120
node --test site/tests/*.test.mjs
```

Tests específicos: `tests/test_postmatch_stats.py` comprueba los cuatro
mercados de conteo, finalización, nombres, marcador, valores vacíos,
prioridad CSV, caché, corrección temporal y seis competiciones.

La web `site/` consume `output/desglose_postpartido.json` y muestra
estadísticas y fuentes dentro de cada ficha, sin cambiar las tarjetas del
dashboard. Un archivo JSON aún no publicado deja las fichas anteriores
operativas y el panel avisa de la carga parcial.

Todo saldo de cuotas sigue siendo una **simulación de 1 unidad**, sin apuestas
reales ni precios indicativos verificados.
