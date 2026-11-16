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
