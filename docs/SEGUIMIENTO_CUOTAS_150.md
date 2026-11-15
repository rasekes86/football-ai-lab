# Seguimiento postpartido de cuotas orientativas superiores a 1,50

## Qué se incorpora
- Cuatro selecciones prepartido comentadas en el chat para la jornada de Segunda del 15/11/2026:
  Tenerife–Ceuta **menos de 2,5 goles** (cuota citada 1,93),
  Granada–Las Palmas **X2** (1,80),
  Eibar–Cádiz **menos de 2,5 goles** (2,17),
  Eldense–Sabadell **menos de 2,5 goles** (1,65).
- Las probabilidades quedan vinculadas al informe de Football AI Lab anterior al encuentro.
- Se archivan únicamente **antes del inicio**; una cuota posterior nunca rellena artificialmente el histórico.
- Se califican como **INDICATIVA_NO_VERIFICADA**: las cuotas mencionadas en el chat no tienen comprobación de casa, publicación, hora de observación ni disponibilidad real. El sistema no las presenta como cuota ofrecida.
- Si en el futuro se activa voluntariamente una API de precios ofrecidos con timestamp, la misma capa puede registrar selecciones 1X2 con cuota superior a 1,50 y EV teórico positivo; The Odds API sigue desactivada sin clave y consentimiento.
- Cada día, tras publicarse los marcadores, se calcula el resultado real y se puntúan los pronósticos. Las ausencias de datos no cuentan como pérdidas.

## Salidas automáticas
- \`output/historico_oportunidades_150.csv\`: pronósticos/quotes congelados antes del evento.
- \`output/seguimiento_oportunidades_150.csv\`: veredicto acierto/error/missing y retorno hipotético por unidad.
- \`output/evaluacion_oportunidades_150.json\`: recuento, Brier, resultados por liga, mercado y calidad de la cuota.
- \`output/oportunidades_150.md\`: revisión legible con las cuatro selecciones.
- Fuente de la muestra manual en \`data/watchlist_cuotas_orientativas.json\`.

## Lo que NO significa
- "Retorno simulado de 1 unidad" NO es dinero apostado, ninguna operación se ha realizado.
- Las cuotas anotadas pueden no haber estado disponibles. **No se puede hablar de ganancias reales ni de valor obtenido**.
- La mejora de resultados retrospectivos no prueba rentabilidad prospectiva.
- La cuota matemática justa (1 / p) no es una cotización de ninguna casa.
- Ningún módulo realiza apuestas ni contrata productos de pago.

## Cómo ampliar el sistema
Nuevas muestras con cuotas orientativas pueden añadirse antes del encuentro,
dejando su carácter no verificado visible. Para auditoría de cuotas ofrecidas se
necesita proveedor, book, precio exacto y sello de tiempo verificable.
