# Fase 5 — Radar inteligente de pronósticos (prepartido)

## Qué añade

Nueva pestaña **Radar inteligente** en el dashboard, accesible desde la barra
lateral y desde la portada. La herramienta cruza los mercados prepartido
que ya publica el selector con las estadísticas recientes, **sin generar
pronósticos nuevos, sin modificar el Top 3 y sin tocar el histórico prospectivo**.

Filtra: mercado, competición, equipo, probabilidad estimada mínima,
calidad/origen del pronóstico (incluido Top 3), cuota justa *teórica* mínima,
cobertura estadística mínima, ventana de 5/10/20 encuentros y condición
(todos o local jugando en casa / visitante jugando fuera). Se puede ordenar
por inicio, probabilidad del modelo o cobertura estadística.

Cada ficha incluye equipos/escudos, fecha, mejor selección disponible
dentro del mercado elegido, probabilidad original, etiqueta de validación,
cuota justa teórica y desglose ampliable de las estadísticas de ambos clubes.
Al abrir la ficha principal se conserva el Top 3, el histórico y las
estadísticas verificadas de ese encuentro, si existen.

## Origen de los datos

La ejecución diaria crea `output/radar_contexto_equipos.json` utilizando
`src/football_ai_lab/radar_context.py`.

- Los pronósticos y las probabilidades proceden
  **exclusivamente** de `output/pronosticos_mercados_futuros.json`.
- Las estadísticas de apoyo proceden del **histórico original**
  `football-data.co.uk`, ya usado por el motor. El radar no consulta
  nuevos proveedores ni usa estadísticas obtenidas después del encuentro.
- El corte de datos usa la fecha de inicio del encuentro en Madrid:
  únicamente se aceptan resultados con fecha **estrictamente anterior**
  a ese día, porque el histórico original no siempre incluye hora fiable.
- Cada pareja (fecha, local, visitante) se cuenta una sola vez dentro
  de su competición y no se mezclan clubes con nombres no equivalentes.
- Para cada club se calculan ventanas de 5, 10 y 20 encuentros
  completados en esa liga, tanto sin filtrar por sede como filtrando por
  su condición de local/visitante, sin introducir jornadas futuras.
- Las métricas abarcan goles, córners, tiros totales, tiros a puerta,
  amarillas, rojas y faltas cuando existen. Los valores se calculan como
  **totales observados por partido**, nunca como probabilidades nuevas.
- Los `null` significan que faltan recuentos de uno o ambos equipos:
  no se convierten en cero. Se informa tanto del denominador de partidos
  anteriores como de cuántos contienen una observación completa.

## Interpretación responsable

El porcentaje etiquetado **Probabilidad estimada del modelo** procede
del selector actual, no de una operación con las medias recientes.
La **cobertura estadística** representa observaciones disponibles /
partidos previos considerados; **NO** representa confianza, certeza ni
ventaja de mercado.

El radar puede mostrar la frecuencia con la que una línea calculada
se cumplió en los partidos previos de un club, únicamente para líneas
numéricas reconocidas de goles o conteos. Esa frecuencia es
descriptiva; **no se usa** para sustituir probabilidades.

Las líneas de un mismo partido están correlacionadas. Que una
selección tenga una probabilidad estimada elevada no implica valor:
para ello hacen falta cuotas comerciales verificadas y evaluación
prospectiva independiente. En este radar **no hay ROI, EV ni ranking
de apuestas rentables**.

Si no hay muestra suficiente para ambos clubes (menos de tres partidos
con datos en la condición elegida), se marca *Muestra limitada*.
Si un mercado no genera predicciones, se muestra el estado vacío,
sin completar con estadísticas a posteriori.

## Arquitectura y pruebas

- Motor: `src/football_ai_lab/radar_context.py`.
- Interfaz: `site/radar.mjs` (comparativas puras y filtros) y
  `site/app.js` + `site/index.html` + `site/styles.css`.
- Feed nuevo: `output/radar_contexto_equipos.json` generado por
  `src/football_ai_lab/pipeline.py` y publicado por
  `.github/workflows/daily.yml`.
- Python: `tests/test_radar_context.py`, verifica corte temporal,
  duplicados, sede, cobertura y valores ausentes.
- JavaScript: `site/tests/radar.test.mjs`, verifica filtros, mercado,
  contexto limitado, frecuencias descriptivas y preservación del Top 3.

Ejecutar las comprobaciones:

```bash
python -m unittest discover -s tests -v
node --test site/tests/*.test.mjs
python -m football_ai_lab.pipeline --days 14 --backtest-games 120
```

El despliegue web se realiza en
<https://rasekes86.github.io/football-ai-lab/#radar> mediante GitHub Pages.
