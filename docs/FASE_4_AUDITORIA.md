# Fase 4 — Seguimiento prospectivo por mercado

## Alcance

La vista **Explorar mercados** sigue mostrando los pronósticos prepartido de
las seis ligas y sus filtros. La Fase 4 congela las líneas publicadas por el
selector en una **segunda serie**, completamente independiente de:

- `output/historico_selecciones.csv` (las tres primeras selecciones Top 3);
- `output/seguimiento_selecciones.csv` (liquidación Top 3);
- `output/historico_oportunidades_150.csv` (cuotas orientativas/ejecutables);
- backtest retrospectivo, entrenamiento, pronóstico Poisson/Elo.

Los registros nuevos son:

| Archivo | Contenido |
|---|---|
| `output/historico_mercados_futuros.csv` | **Snapshot inmutable** de cada selección publicada antes del inicio |
| `output/seguimiento_mercados_futuros.csv` | Esas selecciones con resultado, estadística, estado, Brier/logloss individual |
| `output/fiabilidad_mercados_futuros.json` | Agrupaciones por mercado, liga, mercado×liga, nivel, Top 3 frente a adicional, calibración |
| `output/pronosticos_mercados_futuros.json` | Pronósticos que se muestran hoy para partidos aún futuros; pueden cambiar en nuevas ejecuciones |

**Importante:** el feed de consulta futuro puede cambiar de un día a otro;
el primer snapshot válido de un partido **no**. Las probabilidades que se
evalúan son siempre las archivadas, nunca las recalculadas posteriormente.

## Controles de archivo

1. Se exige ID de partido, equipos, liga, fecha futura con zona horaria,
   timestamp del modelo anterior al inicio y no posterior a la ejecución.
2. Se exige `0 < probabilidad < 1` y una cuota **justa teórica** finita
   coherente (aproximadamente (1/p)); no es una oferta real.
3. Se valida el contrato semántico original de cada mercado, incluyendo
   sentido y línea de córners/tiros/amarillas.
4. El ID de partido solo se congela la **primera vez**; nunca se anexan nuevas
   líneas a ese mismo partido ni se sobrescriben probabilidades históricas.
5. No hay backfill de partidos comenzados antes de activar el sistema.
6. Se conserva el origen y calidad original:
   `MODELO_NO_CALIBRADO`,
   `BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA` o
   `EXPLORATORIO_NO_VALIDADO`.
7. Se marca si una línea coincide con una de las tres selecciones originales,
   pero el **Top 3 sigue liquidándose por su cuenta**.

El selector publica como máximo ocho líneas por categoría y partido. Si
faltas o tarjetas rojas todavía carecen de modelo prepartido fiable,
**no se genera una predicción** por extrapolar su media histórica.

## Liquidación

Se utiliza el mismo evaluador semántico que para el Top 3, sobre un histórico
separado de marcadores y métricas verificadas. Si un partido todavía no ha
terminado, queda `PENDIENTE`; si falta resultado verificado,
`RESULTADO_NO_DISPONIBLE`; si faltan conteos completos y contrastables,
`ESTADISTICA_NO_DISPONIBLE`. Esas categorías **no cuentan como fallos**.

La recuperación comprende resultados oficiales revisados, CSV
football-data.co.uk y ESPN scoreboard + summary, con identificación de
equipos, fecha local, estado final y marcador concordante antes de usar
estadísticas faltantes. Hay límites de consulta para servicios gratuitos.
No se modifica el histórico del entrenamiento ni se inventan estadísticas
faltantes.

## Fiabilidad y calibración

En cada categoría del dashboard aparecen:

- Selecciones archivadas vs. evaluadas; cobertura por **partidos distintos**.
- Tasa de acierto observada y probabilidad media emitida.
- **Brier:** media de ((p-y)^2), donde `y=1` indica acierto y `y=0` fallo.
- **Logloss:** media de `-log(p)` en aciertos y `-log(1-p)` en fallos.
- **ECE:** error de calibración ponderado por franjas de probabilidad
  (0–20%, 20–40%, 40–60%, 60–80%, 80–100%).
- Desglose por mercado, liga, nivel de validación y registro Top 3 / adicional.
- Últimas 240 evaluaciones con estado, y CSV íntegro conservado en GitHub.

**Advertencia estadística:** varias líneas del mismo encuentro están
correlacionadas y no equivalen a observaciones independientes. Con menos
de 30 partidos distintos la interfaz advierte de muestra insuficiente; 30–99
siguen siendo preliminares. Ninguna mejora en Brier, acierto o ECE demuestra
ventaja económica. No se estima ROI sin cuotas reales verificadas.

El panel ofrece filtros adicionales de probabilidad mínima (55%–85%) y
**cuota justa teórica mínima** (1,25–2,00) para el listado FUTURO.
Estos umbrales no reescriben el seguimiento archivado: los indicadores de
fiabilidad respetan el mercado, liga y tipo de pronóstico, pero no rehacen
un historial filtrado a posteriori por cuota o confianza.

## Validación

```bash
python -m unittest discover -s tests -v
node --test site/tests/*.test.mjs
python -m football_ai_lab.pipeline --days 14 --backtest-games 120
```

El workflow `Analisis futbol diario` ejecuta estas pruebas, genera los
archivos de la Fase 4 y los confirma en `main`. Pages publica la nueva interfaz
y la aplicación consume la evaluación JSON desde `output/`.

La primera ejecución válida arranca con **cero partidos evaluados**, porque
no se deben reconstruir ex post resultados de encuentros anteriores al
primer archivo.
