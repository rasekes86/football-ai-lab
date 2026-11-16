# Football AI Lab Dashboard · web estática

Interfaz responsive y accesible para las seis ligas y el seguimiento de pronósticos del repositorio.

## Páginas y funciones
- **Resumen:** próximos encuentros, acierto del Top 3 y balance simulado de cuotas.
- **Partidos:** búsqueda por equipo/mercado, filtros de competición, fecha y estado; ficha de cada partido con sus **tres primeras selecciones archivadas**.
- **Histórico Top 3:** resultados individuales, aciertos, fallos, pendientes y ausencia de estadística.
- **Cuotas +1,50:** cotizaciones indicativas / API (si se habilita), una unidad simulada por selección, ROI hipotético y gráfica.
- **Modelo:** cobertura de las seis ligas, métricas por liga y explicación de las fuentes.

Sin dependencias de frontend, sin API keys, sin servidor, sin cookies y sin operaciones de apuestas.

## Origen de los datos
La web consulta por HTTPS la rama `main/output` del repositorio **público**:
- `predicciones.csv` y `historico_predicciones.csv`
- `selecciones.csv`, `historico_selecciones.csv`, `seguimiento_selecciones.csv`
- `seguimiento.csv` y `seguimiento_oportunidades_150.csv`
- `evaluacion_selecciones.json`, `evaluacion_oportunidades_150.json`, `evaluacion_real.json`

Las fuentes se cargan al entrar o pulsar **Actualizar**, sin redeplegar cada vez que el motor diario actualiza sus CSV. Las respuestas raw de GitHub pueden tener caché, por lo que la actualización no es en tiempo real. El resultado y el ROI solo cuentan liquidaciones marcadas `FINALIZADO` con resultado 1 o 0; nunca contabilizan los pendientes como fallos. Las selecciones del histórico archivado prevalecen frente a los recálculos actuales.

## Publicación
Workflow: [`.github/workflows/pages.yml`](../.github/workflows/pages.yml). El disparador es un push que cambie `site/**` o el propio workflow, además de `workflow_dispatch`.

En GitHub, configurar **Settings → Pages → Build and deployment → Source → GitHub Actions**. Si Pages todavía no estaba habilitado, este paso puede ser necesario antes de que el workflow publique. Tras un despliegue exitoso:
`https://rasekes86.github.io/football-ai-lab/`

## Desarrollo y validación
Desde la raíz del repositorio:

```bash
node --check site/data.mjs
node --check site/app.js
node --test site/tests/*.test.mjs
python -m http.server 8000
```

Abrir `http://localhost:8000/site/`; no abrir `index.html` con el esquema `file://`, ya que los módulos ES requieren HTTP(S). El motor de Python y sus CSV históricos permanecen independientes.

## Escudos de equipos
El despliegue genera `site/crests.json` a partir de los nombres de partidos y del catálogo de clubes de ESPN. El código está en `site/scripts/build_crests.py`; no altera las predicciones ni guarda imágenes ajenas. Utilizamos enlaces `a.espncdn.com` únicamente para identificar equipos. Los nombres ambiguos o sin escudo se representan con las iniciales originales. Las marcas y logotipos pertenecen a sus titulares. La generación se comprueba con `site/tests/test_crests.py` y se incluye en el artefacto de GitHub Pages, sin necesidad de versionar el JSON generado.

## Explorador de mercados (v1.2)

La pestaña **Explorar mercados** permite elegir: córners, tiros, tiros a puerta, faltas, amarillas, rojas, goles totales, doble oportunidad, resultado 1X2 y ambos marcan. También tiene filtros por **competición, últimos 30/90/180/365 días, equipo y línea/resultado**.

Las medias, medianas, histogramas y frecuencias se calculan sobre **resultados históricos realmente disputados**, publicados en `output/mercados_historicos.json` (hasta 365 días; información observacional, no pronóstico). El dataset se obtiene del histórico de `football-data.co.uk` y añade estadísticas ESPN solo cuando se contrastaron por marcador y equipos. El periodo y el tamaño de muestra se muestran en pantalla; si falta una estadística, se marca como **no disponible** en vez de cero.

La tasa **Acierto Top 3** procede **exclusivamente** de `output/seguimiento_selecciones.csv`, cuya selección fue archivada antes del partido. Así se distingue la frecuencia histórica de una línea de la calidad real de nuestras predicciones. En faltas la cobertura puede ser muy limitada: football-data.co.uk no publica habitualmente ese campo y solo utilizamos recuentos de ESPN si han sido verificados. Ningún dato de esta pantalla alimenta el entrenamiento del modelo, y no hay apuestas ejecutadas.

Las métricas y filtros se prueban con `site/tests/markets.test.mjs`; la generación del JSON se valida con `tests/test_market_history.py`.

## Pronósticos futuros por mercado (v1.3)

La pestaña **Explorar mercados** prioriza ahora los **partidos futuros**. Al elegir
«Córners», «Tiros», «Doble oportunidad», «1X2», «Goles», «Ambos marcan»,
«Tiros a puerta» o «Tarjetas amarillas» muestra fecha, equipos, selección y
probabilidad **prepartido** para los encuentros aún no empezados. Las líneas
alternativas calculadas aparecen en cada ficha bajo «Otras líneas». El bloque
de histórico y frecuencias reales se mantiene bajo «Estadísticas históricas».

**Origen**: `output/pronosticos_mercados_futuros.json`, generado en la ejecución
diaria por el selector del motor a partir de `goal_candidates` y los mercados
de conteos con auditoría temporal. Se publican como máximo ocho líneas por
categoría y partido, ordenadas por probabilidad. Las líneas de conteos que
superaron backtesting retrospectivo se identifican expresamente como
**no validadas prospectivamente**. Los conteos sin esa comprobación se
muestran como **exploratorios no validados**. Los mercados de resultado
continúan etiquetados como modelo no calibrado.

**Sin modelo**: faltas y rojas se pueden estudiar en el histórico, pero todavía
no reciben pronósticos futuros; no se extrapolan medias como probabilidades
y no se inventan predicciones.

**Protección del Top 3**: este feed de visualización es distinto del registro
congelado `historico_selecciones.csv`; solo ese registro se evalúa como
pronósticos prospectivos. Las líneas adicionales no se suman como aciertos
ni como apuestas realizadas. Las «cuotas justas» son inversiones matemáticas
de la probabilidad estimada, **no ofertas de casas de apuestas**.

Pruebas: `site/tests/future_markets.test.mjs` y
`tests/test_future_markets.py`.

## Fase 4 — Fiabilidad prospectiva

Desde la activación del sistema, todas las líneas publicadas en `output/pronosticos_mercados_futuros.json` se congelan antes de su encuentro en `output/historico_mercados_futuros.csv` (primer snapshot por partido). El seguimiento va en `output/seguimiento_mercados_futuros.csv`, la fiabilidad y calibración por mercado/liga/calidad en `output/fiabilidad_mercados_futuros.json`. El Top 3 mantiene sus ficheros intactos y **no se reconstruyen pronósticos antiguos**.

La pestaña **Explorar mercados** muestra ahora medias y calibración basadas en resultados prospectivos comprobados, número de partidos únicos y advertencias por muestras pequeñas. Se pueden filtrar los futuros por probabilidad y cuota justa teórica mínima; esto no constituye precios reales ni filtra retrospectivamente la auditoría. El histórico estadístico general sigue separado y accesible.

Detalles metodológicos: `docs/FASE_4_AUDITORIA.md`.
