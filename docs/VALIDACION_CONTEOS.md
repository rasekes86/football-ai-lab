# Mercado de conteos · auditoría v0.7

Objetivo: permitir que córners, tiros totales, tiros a puerta de equipo y tarjetas amarillas entren en el selector de Football AI Lab **solo tras pruebas temporales suficientes**.

## Proceso
1. Los datos de football-data.co.uk conservan HS/AS, HST/AST, HC/AC y HY/AY cuando la competición y temporada los proporciona.
2. El modelo de conteos explora umbrales de más/menos usando medias locales, visitantes y dispersión liguera.
3. El backtest walk-forward toma hasta los últimos 180 partidos de cada liga. **Para cada uno**, genera la estimación solo con encuentros de fecha estrictamente anterior; además calcula una frecuencia histórica comparable como referencia.
4. Mide Brier, log loss y error de calibración (ECE), por liga, métrica y línea, con datos ausentes expresamente descartados.
5. Solo se autoriza como **APTO_RETROSPECTIVO**, no como validación prospectiva, si cumple simultáneamente cobertura, tamaño de muestra y mejoras.
6. La búsqueda Top 3 incluye candidatas habilitadas por esa auditoría y conserva el límite de una selección por familia. Las otras siguen en la pestaña exploratoria.

Los umbrales iniciales de activación son: ≥85 evaluaciones, ≥65 % de cobertura respecto a los partidos con resultado de la métrica, mejora Brier ≥0,003, mejora log loss ≥0,005, ECE ≤0,09.

## Precauciones
- La autorización es **retrospectiva**: no equivale a rentabilidad, cuota ofrecida, probabilidad plenamente calibrada o ventaja contrastada prospectivamente. Las mejoras se han elegido como umbrales de calidad, no optimizados para garantizar que haya tres selecciones.
- La comparación aplica múltiples líneas; encontrar mejoras por azar es posible. Debe continuarse con seguimiento prospectivo antes de elevar el grado de confianza.
- Los mercados de tiros individuales de jugadores no están incluidos. Exigen identificación, participación y minutos estimados.
- La coincidencia de varias selecciones del mismo encuentro puede implicar correlación, aunque procedan de familias distintas.
- Las cuotas justas del selector no son precios disponibles para apostar. The Odds API es opcional; InferSports proporciona referencias teóricas y no precios ofrecidos.

## Salidas
- [auditoría de líneas](../output/validacion_conteos.json)
- [selecciones por partido](../output/selecciones.json)
- [informe diario](../output/informe.md)

## Ejemplo de consulta
«Consulta las tres selecciones de Real Madrid–Celta en Football AI Lab, indicando qué mercados de córners, tiros o tarjetas han superado los criterios retrospectivos y cuáles siguen descartados».
