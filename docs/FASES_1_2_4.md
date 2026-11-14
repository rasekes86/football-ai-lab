# Football AI Lab v0.5 — fases 1, 2 y 4

Revisión implementada el 14 de noviembre de 2026; sin instalar software local y sin activar APIs de pago. El sistema sigue siendo experimental.

## Fase 1 — datos y contexto más ricos
- \`src/football_ai_lab/sources.py\` conserva las columnas que el CSV histórico incluya: tiros, tiros a puerta, córners, amarillas y rojas. Valores no presentes quedan como *desconocidos*, nunca como cero.
- \`src/football_ai_lab/match_context.py\`: información **anterior** a cada encuentro, resumen de los cinco partidos previos, días desde el último, enfrentamientos entre ambos, disponibilidad de estadísticas y motivos de exclusión.
- Archivo \`output/contexto_partidos.json\` con todos los encuentros hallados, incluidos los descartados por el motor.
- \`src/football_ai_lab/context_xg.py\`: busca **una muestra limitada de partidos finalizados** por liga en ESPN y trata de recuperar el xG real de Understat mediante Machina Sports. Máximo cinco consultas xG en una ejecución. Puede devolver cero partidos si no se logra confirmar la identidad, la fuente no responde o no hay partidos en fechas consultadas. Publica \`output/contexto_xg.json\`. No inventa xG y no utiliza esta muestra para modificar estimaciones prepartido.
- Las bajas de Premier League de Machina siguen siendo contexto, no confirmaciones médicas ni alineaciones futuras. Ninguna variable de lesión se introduce en el modelo automáticamente.

## Fase 2 — evaluación prospectiva, diferente al backtest
- \`src/football_ai_lab/prospective.py\` exige un pronóstico **REAL**, timestamp válido y anterior al inicio del partido.
- Si la fuente de resultados aún no publica el marcador, el estado es \`RESULTADO_NO_DISPONIBLE\`, sin puntuarlo.
- Los pronósticos inválidos/posteriores al inicio no cuentan; el primero archivado se mantiene para una comparación honesta.
- \`output/seguimiento.csv\` registra marcador, acierto del favorito, Brier y log loss.
- \`output/evaluacion_real.json\` agrega muestra, medias, comparación por liga y por modelo, y calibración en franjas de probabilidad.
- Hasta que terminen los encuentros, **0 partidos finales** es el resultado correcto. El backtest no se utiliza para inflar esta cifra.
- Precaución: unas decenas de encuentros no bastan para asegurar calibración ni capacidad predictiva sostenida.

## Fase 4 — mejor evaluación y modelos experimentales
- El XGBoost semanal usa estadísticas recientes disponibles (tiros, tiros a puerta y córners) con indicadores que distinguen *dato ausente* de cero real. Mantiene forma reciente y días de descanso.
- Su desarrollo siempre aplica corte temporal estricto: no usa resultados del mismo día para generar features.
- \`output_ml/discrepancias.csv\` compara encuentros idénticos frente a Poisson/Elo, con avisos \`VIGILAR\` (>=8 puntos porcentuales) y \`REVISAR\` (>=15 pp). **No es señal de apuesta.**
- \`src/football_ai_lab/model_research.py\` evalúa varios pesos de Poisson/Elo. Selecciona el candidato con fechas antiguas y contrasta en fechas posteriores; publica \`output_ml/auditoria_pesos.json\`. **No cambia automáticamente** el peso de producción 70/30.
- \`output_ml/validacion.json\` continúa comparando XGBoost vs Poisson/Elo en el mismo holdout, además de la calibración.

## Cómo usarlo desde ChatGPT
1. «Consulta el contexto de Real Madrid–Celta en nuestro Football AI Lab: últimos cinco partidos, tiros, descanso, cara a cara y calidad de datos».
2. «¿Cuántos pronósticos reales han terminado y cuál es nuestro Brier prospectivo?»
3. «¿Qué partidos presentan discrepancias mayores de 15 puntos entre XGBoost y Poisson/Elo?»
4. «¿Ha mejorado algún peso en la prueba posterior sin cambiar el modelo de producción?»

## Límites importantes
- El xG no se extrapola de goles ni de tiros: si no hay fuente auténtica, se marca ausente.
- La disponibilidad de xG histórico por liga no implica xG para todos los partidos futuros.
- El histórico de una división puede carecer de equipos recién ascendidos o de partidos de copa; se explicita la cobertura y nunca se simulan datos.
- No hay cuotas ofrecidas de casas verificadas para todos los encuentros; no hay ventaja financiera probada.
- Google Sheets continúa a la espera de que el usuario autorice IMPORTDATA; los nuevos JSON se pueden consultar inmediatamente en GitHub.
