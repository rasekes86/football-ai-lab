# Cobertura real de cuotas y evidencia estadística independiente

Actualización: 18 de noviembre de 2026. Esta mejora optimiza la rotación y los diagnósticos; **no asegura que el proveedor tenga datos ni que las probabilidades estén calibradas**.

## 1. Cobertura de cuotas sin multiplicar llamadas

- Sigue el calendario GitHub de **una ronda cada dos horas** y la cuota interna conservadora de **48 peticiones/hora** (más estricta que el máximo teórico del proveedor).
- Cuando el proveedor responde correctamente a los calendarios pero **no puede vincular un evento único por liga, dos equipos local/visitante y diferencia horaria <=2h**, se registra `SIN_EVENTO_VERIFICADO` y ese partido vuelve a comprobarse **seis horas** después. Si un evento coincide pero no trae cuotas, el reintento original es de **dos horas**; si sí tiene cuotas, cuatro horas. Las adicionales congeladas nunca se recotizan.
- No se marca como partido consultado sin evento si hay errores de red/API, ids ambiguos o no se pudo completar la búsqueda específica de su liga. En esos casos no se finge ausencia de precios.
- Cada consulta de calendario diario abarca también **dos horas antes y después del día UTC** para no perder partidos cercanos a medianoche. **No** se amplía la tolerancia estricta de cruce (dos horas) y no se añade ninguna consulta por esta razón.
- Se aceptan **únicamente equivalencias explícitas** de nombres de competiciones con temporada y ciertos clubes; el Celta principal y el Celta Fortuna siguen siendo equipos distintos, y Bundesliga I nunca equivale a Bundesliga II.
- Nuevo diagnóstico `mismos_equipos_hora_incompatible`: permite distinguir datos de calendario discrepantes de nombres de clubes distintos. **En caso de duda se descarta la cuota** y no se archiva una selección.
- Para cada liga, la auditoría distingue eventos de la API, eventos cruzados, partidos con cuotas y motivos de descarte. No se difunden tokens.

## 2. Calibración prospectiva sin inflar la muestra

Los informes `output/fiabilidad_mercados_futuros.json` siguen contando todos los pronósticos archivados antes del partido, pero distinguen:

- `muestra`: número de predicciones verificadas. Varias pueden salir del mismo encuentro y están correlacionadas.
- `partidos_unicos`: encuentros distintos realmente evaluados. **Una muestra de 16 pronósticos de un solo partido sigue siendo un solo partido independiente**.
- `brier` y `logloss`: promedios por pronóstico, útiles de forma descriptiva pero sesgados hacia partidos con más líneas publicadas.
- `brier_equilibrado_partidos` y `logloss_equilibrado_partidos`: primero promedio dentro de cada partido y después promedio de partidos; cada encuentro tiene **igual peso**, sin inventar datos ni alterar pronósticos.
- `calibracion[].partidos_unicos`: cobertura independiente de cada tramo de probabilidad, no solo número de líneas.
- `estado_calibracion` y `partidos_para_umbral`: menos de **30 partidos distintos** => `INSUFICIENTES_PARTIDOS` (o `NO_EVALUABLE` si no hay resultados); desde 30, `EVALUABLE_DESCRIPTIVO`. El umbral es **un mínimo operativo, no un aval de fiabilidad ni de rentabilidad**.

Estas métricas se agregan sin reescribir selecciones anteriores, resultados verificados, cuotas ni balance 3+1. Hasta reunir muchas observaciones independientes y estudiar su estabilidad por mercado/liga, no se ajustan automáticamente probabilidades sobre esta muestra.

## Verificación

Las pruebas reproducen una fuente con horario incompatible, otra cerca de medianoche, una división distinta, un error de API, el reintento a seis horas y múltiples pronósticos del mismo partido con diferente peso. La CI ejecuta los tests antes de publicar.
