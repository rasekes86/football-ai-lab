# Fase 8 — Comparador de cuotas prepartido realmente observadas

La nueva pestaña **Cuotas reales** (ruta
[dashboard #realodds](https://rasekes86.github.io/football-ai-lab/#realodds))
distingue expresamente una **cuota ofertada por un bookmaker y observada a
través de API** de la «cuota justa» (1/p) calculada por Football AI Lab.
No sustituye la simulación +1,50 ni modifica el Top 3 original, las
predicciones futuras o el seguimiento prospectivo.

## Proveedor y costes (opcional)

La integración utiliza **The Odds API V4**,
[documentación oficial](https://the-odds-api.com/liveapi/guides/v4/),
host `https://api.the-odds-api.com`. **No confundir** con la empresa distinta
`theoddsapi.com`, cuyos planes y límites son otros.

- Según la [página del proveedor](https://the-odds-api.com/), su plan gratuito
  ofrece **500 créditos/mes** (sujeto a cambios y condiciones).
- El endpoint de cuotas cuesta normalmente **1 crédito por región y mercado**:
  una consulta con `h2h,totals` y `regions=eu` supone hasta 2 créditos
  por liga. Se consultan un máximo de seis ligas = hasta 12 créditos por
  ejecución completa (aproximadamente 360 en 30 días).
- **Si alguna liga o un mercado no están incluidos en tu plan o no hay
  precios publicados, simplemente no hay comparación.** No se infieren
  cotizaciones.
- Las consultas se ejecutan en GitHub Actions **solo con evento `schedule`
  o `workflow_dispatch`**; nunca en los pushes automáticos de código,
  para evitar consumo accidental.
- El endpoint cubre los mercados básicos **1X2 (`h2h`) y total de goles
  (`totals`)** cuando existen. No afirma disponer de cuotas ofrecidas
  para doble oportunidad, tarjetas, córners o tiros. Tampoco extrapola
  mercados combinados de otros precios.

## Activación privada (no envíes tu clave aquí)

1. Crea tu cuenta y clave privada en [The Odds API](https://the-odds-api.com/).
2. Abre [GitHub → Settings → Secrets and variables → Actions](https://github.com/rasekes86/football-ai-lab/settings/secrets/actions).
3. En **Repository secrets** crea `THE_ODDS_API_KEY` con el valor recibido.
   **No la pongas en el código, el chat ni variables públicas.**
4. En **Repository variables** crea `ENABLE_REAL_ODDS` con valor `true`.
   Opcional: `REAL_ODDS_LEAGUES` para ahorrar créditos, por ejemplo
   `SP1,SP2,E0`; si se omite intentará las seis: `SP1,SP2,E0,D1,I1,F1`.
5. Abre [Actions → Analisis futbol diario](https://github.com/rasekes86/football-ai-lab/actions/workflows/daily.yml)
   y usa **Run workflow** (una ejecución manual puede consumir créditos).
   O deja que se ejecute automáticamente a las 07:17 UTC.
6. Visita [Cuotas reales](https://rasekes86.github.io/football-ai-lab/#realodds)
   y pulsa **Actualizar**. Se mostrarán únicamente partidos/líneas
   con datos realmente encontrados.

Para **desactivar** el gasto: cambia `ENABLE_REAL_ODDS` a `false`.
Con conexión desactivada o clave ausente no se consume nada, el comparador
queda vacío con una explicación y se conserva el archivo histórico anterior.

## Cómo se comprueba cada comparación

1. El proveedor debe devolver un **evento futuro** con competición,
   equipo local y visitante inequívocos, y horario UTC que difiera como
   máximo dos horas del encuentro programado en el modelo.
   Nunca se emparejan encuentros con orden de equipos invertido o
   candidatos duplicados.
2. Solo se admiten cuotas decimales válidas, actualizadas antes del inicio
   y con menos de **24 horas de antigüedad**. La captura y la última
   actualización se publican en cada registro.
3. Cada bookmaker debe ofrecer **todos los resultados necesarios** para
   calcular el margen de su propio mercado:
   - 1X2: victoria local, empate y victoria visitante.
   - Total de goles: por encima / por debajo de la **misma línea**
     (0,5, 1,5, 2,5, etc.).
4. Se compara exclusivamente con una selección del modelo que tenga
   **la misma línea y dirección**. No se construyen cuotas «reales»
   combinando otros mercados, ni se utiliza la probabilidad de córners
   para inferir precios.
5. El margen de una casa se calcula como `sum(1/cuota)-1`;
   la probabilidad «sin margen» se estima dividiendo la inversa de cada
   cuota entre la suma de inversas de esa **misma casa y mercado**.
6. La diferencia se muestra en puntos porcentuales
   `(probabilidad_modelo - prob_sin_margen)*100`.
   Se calcula un EV **puramente hipotético**
   `probabilidad_modelo*cuota_real - 1`. **No es una señal fiable de
   beneficio**, porque la probabilidad del modelo puede estar mal calibrada,
   hay comisiones y la oferta puede desaparecer o ser inaccesible.
7. El listado no ordena automáticamente por EV positivo, sino por fecha:
   evita confundir probabilidades altas con oportunidades rentables.

## Archivos y separación histórica

- `output/cuotas_reales_verificadas.json`: **última captura actual**
  de cuotas observadas y auditoría, sin la clave ni URLs de la API que
  contengan secretos. Si falla o falta API, el listado queda vacío.
- `output/comparacion_cuotas_reales.json`: coincidencias reales
  contrastadas con las selecciones FUTURAS del modelo, con la casa,
  margen, probabilidades y marca de tiempo.
- `output/historico_cuotas_reales.json`: primeras observaciones **reales**
  de cada día, bookmaker y mercado, sin backfill ni reescritura al
  consultar de nuevo durante el mismo día. Si falla la API se conserva
  el histórico, pero **no se presenta una cuota antigua como actual**.

El histórico archivado no se usa aún para afirmar ROI ni CLV; eso
requeriría cuotas de cierre válidas y pruebas prospectivas separadas.

No se alteran `output/historico_selecciones.csv`,
`output/historico_mercados_futuros.csv`,
`output/seguimiento_mercados_futuros.csv` ni las estadísticas de
Football-Data. Sus cuotas históricas CSV **no** se etiquetan como
precios actuales.

## Pruebas

```bash
python -m unittest discover -s tests -v
node --test site/tests/*.test.mjs
python -m football_ai_lab.pipeline --demo
```

`tests/test_real_odds.py` utiliza únicamente datos ficticios, verificando
partidos equivocados, casa sin mercado completo, líneas erróneas, cuota
caducada, ausencia de clave, protección de secretos, deduplicación y
conservación histórica. `site/tests/real_odds.test.mjs` verifica que
el panel no inventa precios, filtra ofertas caducadas, coincide por
selección y bookmaker, y mantiene separado el Top 3.

Las restricciones de licencia y redistribución de datos pueden variar
según el plan del proveedor. Comprueba las condiciones de The Odds API
antes de mostrar sus datos en una web pública. La integración no procesa
pagos ni ejecuta apuestas.
