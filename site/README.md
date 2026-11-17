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
La web descarga preferentemente una **copia pública en su propio dominio** (la carpeta `published/` incluida en el despliegue de GitHub Pages), con respaldo de la rama `main/output` del repositorio si esa copia todavía no existe:
- `predicciones.csv` y `historico_predicciones.csv`
- `selecciones.csv`, `historico_selecciones.csv`, `seguimiento_selecciones.csv`
- `seguimiento.csv` y `seguimiento_oportunidades_150.csv`
- `evaluacion_selecciones.json`, `evaluacion_oportunidades_150.json`, `evaluacion_real.json`

Las fuentes se cargan al entrar o pulsar **Actualizar**. El workflow `pages.yml` publica las 17 fuentes públicas a `site/published/` (solo en el artefacto de GitHub Pages, sin duplicarlas en el repositorio) y también se ejecuta tras finalizar satisfactoriamente `Analisis futbol diario` mediante `workflow_run`. Esto mantiene la web sincronizada con la actualización diaria sin depender en Android de un segundo dominio, `raw.githubusercontent.com`. La publicación puede demorarse y no es información en tiempo real. El resultado y el ROI solo cuentan liquidaciones marcadas `FINALIZADO` con resultado 1 o 0; nunca contabilizan los pendientes como fallos. Las selecciones del histórico archivado prevalecen frente a los recálculos actuales.

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

## Fase 5 — Radar inteligente

La vista `#radar` combina el feed de predicciones futuras con `output/radar_contexto_equipos.json`, que contiene estadísticas de encuentros anteriores al partido (sin resultados del día del encuentro). El usuario puede seleccionar 5, 10 o 20 encuentros, local/fuera, mercado, probabilidad, calidad, cobertura de datos, liga y cuota justa teórica. Se muestra fecha, equipos, línea calculada, probabilidad del modelo y datos previos con denominadores reales, sin mezclar estos porcentajes con la precisión prospectiva ni el ROI. Si faltan datos se marca la ausencia. Más detalles: `docs/FASE_5_RADAR.md`.

## Fase 8 — Comparación con cuotas realmente observadas

La nueva pestaña `#realodds` carga
`output/cuotas_reales_verificadas.json` y
`output/comparacion_cuotas_reales.json`. No muestra cuotas si el proveedor
está desactivado, la clave falta, los partidos no coinciden o la captura
está caducada. La fuente opcional se consulta en la ejecución programada,
sin acceder a secretos desde el navegador. Los precios históricos se
conservan exclusivamente como histórico en
`output/historico_cuotas_reales.json`. Detalles y límites:
`docs/FASE_8_CUOTAS_REALES.md`.


## PWA Android — instalación sin Play Store ni servidor adicional

Football AI Lab también funciona como Progressive Web App (PWA). Se sirve desde
la misma URL gratuita de GitHub Pages, por HTTPS, sin cuenta adicional,
sin costes de hosting nuevos y sin modificar el motor de predicciones.

### Instalar en Android

1. Abre https://rasekes86.github.io/football-ai-lab/ con **Chrome**.
2. Pulsa **Instalar app** en la barra superior. Si Chrome permite la instalación
   directa aparecerá su diálogo de confirmación.
3. Si no aparece el diálogo, pulsa **⋮ → Instalar aplicación** o
   **Añadir a pantalla de inicio** en el menú de Chrome.
4. Abre el icono «Football AI» desde la pantalla de inicio; se ejecuta
   en modo independiente sin la barra habitual del navegador.

No se publica en Google Play y no es una APK. Algunos navegadores integrados
en otras aplicaciones no permiten instalar PWAs; abre el enlace en Chrome.

### Arquitectura y datos

- `manifest.webmanifest`: identidad, inicio `./#fixtures`, alcance relativo a
  `/football-ai-lab/`, iconos 192/512 y accesos rápidos.
- `pwa-icon.svg`: icono original con el mismo estilo azul noche y rojo.
- `scripts/build_pwa_icons.py`: genera PNG maskable sin Pillow ni npm;
  GitHub Actions los incorpora al artefacto publicado.
- `pwa.js`: registra el service worker en HTTPS, ofrece instalación
  o instrucciones de Chrome y avisa si se pierde internet.
- `sw.js`: precarga **solo la interfaz y los módulos locales**. Usa
  `network-first` para las actualizaciones y permite abrir la interfaz offline.

**No** se guardan en la caché PWA los CSV/JSON externos, las cuotas de
bookmakers, los pronósticos de GitHub raw, escudos de terceros, secretos ni
respuestas de APIs. Sin conexión, la interfaz se abre pero los datos deben
consultarse online; no se muestran cuotas antiguas como si fueran actuales.
Al reconectar, se reintenta la descarga de las fuentes publicadas.

### Pruebas y publicación

El flujo `.github/workflows/pages.yml` valida `pwa.js` y `sw.js`, ejecuta
`site/tests/pwa.test.mjs`, prueba el generador con
`site/tests/test_pwa_icons.py`, genera los PNG 192/512 en cada despliegue
y verifica su formato antes de subir el artefacto.

### Solución para problemas de carga de datos en la PWA Android

Desde noviembre de 2026, `site/feed_loader.mjs` consulta primero
`./published/<archivo>?v=<instante>`, servido desde **el mismo origen que la
PWA**, y solo usa GitHub raw si el recurso publicado no está disponible.
El despliegue usa `site/scripts/publish_feeds.py`, que incluye únicamente
los 17 CSV/JSON autorizados, los valida antes de copiar y rechaza que falten
archivos. Nunca se publican secretos, tokens ni archivos extra.

El service worker (`sw.js`) cachea la aplicación y sus módulos pero **no**
cachea `published/*` ni cuotas ni pronósticos; los datos no se presentan como
actuales sin una respuesta de red. Si una versión antigua sigue activa en
Android, cierra y vuelve a abrir la app con internet y pulsa **Actualizar**.

Los cambios en `output/**` provocados por GitHub Actions usan el token del
workflow y no disparan por sí mismos otros workflows `push`; por ello
`pages.yml` también escucha la finalización correcta del workflow diario
(`workflow_run`). No hay un servidor permanente ni coste adicional.

## Fase 3+1 — selección adicional automática con precios observados

**Top 3 y adicional son dos seguimientos independientes.** El Top 3 sigue
procediendo del histórico inmutable de `historico_selecciones.csv`.
La adicional usa `comparacion_cuotas_reales.json` generado en **la misma
ejecución autorizada**, después de obtener y emparejar cuotas de 5DollarFootballAPI,
API-Football o The Odds API. No se llama de nuevo a ninguna API por este paso.

El motor `value_watchlist.freeze` sólo incorpora **una adicional por partido**
cuando se cumplen TODOS los requisitos:

- Encuentro todavía no iniciado; identidad y hora exactas coincidentes
  en el pronóstico y la fuente.
- Precio decimal ofrecido superior a **1,50**, cuota ligada a **bookmaker,
  proveedor y evento**, y captura prepartido reciente (máximo seis horas).
- Mismo resultado y misma línea de un mercado liquidable: 1X2, goles,
  ambos marcan o córners/amarillas explícitos con métrica compatible.
  Se rechazan las líneas asiáticas con devolución y los mercados no equivalentes.
- Probabilidad experimental de al menos **50 %** y EV del modelo superior
  a **3 puntos porcentuales por unidad** como filtro orientativo. Esto **no**
  constituye prueba de ventaja o recomendación de apuesta.
- No se repite una selección ya archivada en el Top 3 original del partido.
  Si no hay candidatos seguros, se registra **ninguna** adicional: no se inventa.

Si hay varias casas o mercados elegibles, se elige una opción por partido
mediante un orden determinista. **La primera selección guardada permanece
inmutable:** los recálculos, cambios de cuotas y resultados posteriores no la
sustituyen. Las cinco referencias manuales antiguas siguen señaladas como
`INDICATIVA_NO_VERIFICADA`; nunca se convierten retrospectivamente en
precios API.

En los CSV `historico_oportunidades_150.csv` y
`seguimiento_oportunidades_150.csv` se archivan la cuota, origen, casa,
proveedor, evento, mercado, línea, fecha y tipo de marca temporal. Para
5DollarFootballAPI el campo `CAPTURA_NO_ACTUALIZACION` indica que sabemos
cuándo capturó el programa la cuota, **no** cuándo la modificó la casa.

Después del partido, el evaluador existente verifica el resultado usando
marcador y estadística contrastados y genera acierto/fallo. El nuevo
registro alimenta automáticamente el panel **Rendimiento 3+1** en el próximo
despliegue de GitHub Pages. El retorno de 1 unidad y el ROI son únicamente
**simulaciones**; el programa no ejecuta apuestas.

**Comprobación de integración:** `python -m unittest tests.test_value_watchlist`
y el workflow `Analisis futbol diario`, que prueba la lógica con fixtures
simulados. Para observar la incorporación de nuevas adicionales con las API
reales es necesaria una ejecución programada o manual autorizada (`Run workflow`)
con las variables/secretos que ya estén activos; los eventos `push` de código
no realizan consultas privadas a las APIs.

## Rendimiento 3+1 y adicional automatizada (noviembre de 2026)

El apartado **Rendimiento** muestra dos registros independientes:

- **Top 3**: únicamente las tres selecciones originales congeladas antes del encuentro. Aciertos, fallos y pendientes se determinan con estadísticas finales verificadas. No se inventa una cuota de casa para calcular su ROI.
- **Adicional +1,50**: como máximo una selección prepartido por partido. Usa un precio de bookmaker observado de 5DollarFootballAPI, API-Football o The Odds API cuando se obtiene y se coteja exactamente con el mismo partido, mercado, resultado y línea. Se exige cuota mayor que 1,50, probabilidad del modelo al menos 50 %, EV matemático superior al 3 % y captura reciente (máximo seis horas). Estos filtros son experimentales y no garantizan ventaja. La primera adicional archivada es inmutable.

Los precios de **referencia manual histórica** conservan su etiqueta `INDICATIVA_NO_VERIFICADA`. Los precios observados automáticamente quedan como `OFRECIDA_API_REGISTRADA`, con bookmaker, proveedor, evento, mercado y marca temporal. Ninguno implica que se haya ejecutado una apuesta. Una selección puede estar acertada o fallada y liquidada aunque la cuota de referencia no esté acreditada. El ROI y beneficio de la adicional son **únicamente simulaciones de una unidad**, no dinero ganado.

En `output/evaluacion_oportunidades_150.json` se publica `seleccion_automatica`: nuevas selecciones, partidos con comparaciones, abstenciones, registros anteriores y desglose por liga. La PWA lo muestra en **Rendimiento → Selección automática**. Si ninguna cuota reúne los criterios, no se crea una apuesta ficticia.

Los workflows activados por **cambios de código** no consumen la cuota gratuita de las APIs privadas. El diagnóstico en esos casos dice `FUENTES_NO_CONSULTADAS`, no que se rechazaron apuestas. Para registrar nuevas adicionales con precios reales es necesario que el workflow **Analisis futbol diario** se ejecute por su horario o manualmente, con los secretos y variables de cuotas ya habilitados. El proceso se realiza una sola vez por ejecución y reutiliza las comparaciones obtenidas, sin añadir consultas a proveedores.

Pruebas: `tests/test_value_watchlist.py` y `site/tests/performance*.test.mjs`. Se verifican el límite 3+1, integridad de la evidencia, ausencia de recalculado retroactivo, abstenciones, resultados postpartido y la no confusión entre precio y resultado.
