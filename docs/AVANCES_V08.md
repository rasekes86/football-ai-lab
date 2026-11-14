# Football AI Lab 0.8 — implantación y límites reales

Fecha de implementación: 14 de noviembre de 2026.

## Lo nuevo ya desarrollado

### 1. Seguimiento real por mercado
La lista de las tres primeras selecciones generadas para un partido queda archivada antes del encuentro. Las reevaluaciones no sustituyen la primera selección. Cuando aparece el resultado oficial en football-data.co.uk, el motor calcula acierto, Brier binario, log loss binario, porcentaje de aciertos y ECE. Los datos de córners, tiros y tarjetas no disponibles se marcan como ausencia, NO fallo.

**Archivos:**
- \`output/historico_selecciones.csv\` — selección original antes del partido.
- \`output/seguimiento_selecciones.csv\` — settlement (real/pending/missing stats).
- \`output/evaluacion_selecciones.json\` — resumen de aciertos por mercado, liga y origen.

El resultado es descriptivo. No compara apuestas monetarias reales ni garantiza retorno. No se confunde la estadística histórica "backtest" con rendimiento prospectivo.

### 2. Informe completo automático
\`output/informes_partidos.md\` y \`output/informes_partidos.json\` reúnen para cada partido pronosticado su forma, descanso, historial, comparativa XGBoost si hay predicción reciente y alineada, Top 3 y advertencias. Las consultas \`[ANALISIS]\` desde GitHub también producen el dossier. Se omiten datos ausentes y no se inventan xG ni lesiones.

### 3. Datos individuales de jugadores
\`src/football_ai_lab/player_data.py\` puede consultar pequeños lotes de boxscores ESPN de partidos YA FINALIZADOS para recopilar identificación, titularidad y estadísticas disponibles. \`output/jugadores_historico.json\` almacena una muestra limitada y deduplicada. Si ESPN no devuelve rosters, declara ausencia. **No promociona selecciones de jugadores** hasta contar con histórico amplio, minutos, probabilidad de titularidad, validación temporal y cobertura suficientemente sólida.

Fuente pública no oficial para investigación/prototipo; cumplimiento de las condiciones de uso corresponde al consumidor.

### 4. Avisos opcionales por Telegram
\`src/football_ai_lab/telegram_notify.py\` prepara un mensaje solo si existen dos secretos \`TELEGRAM_BOT_TOKEN\` y \`TELEGRAM_CHAT_ID\`. El workflow lo llama en ejecución programada o manual, nunca automáticamente por cada push. Las credenciales se conservan en GitHub Secrets; no compartirlas por chat.

## Continúa pendiente
- xG auténtico con fuente verificable y alineada por evento; la conexión de prueba no lo ha recuperado.
- Históricos amplios de tiros por jugador, titularidades y minutos verificables para pronósticos individuales.
- Cuotas **ofrecidas** reales de varios mercados: The Odds API opcional permanece desactivada sin aprobación y clave.
- Alineaciones y lesiones confirmadas integradas en los modelos probabilísticos.
- Suficientes observaciones futuras para calibración prospectiva, pruebas de estabilidad y riesgo por mercado.
- Coordinación LLM/LangGraph real: hoy son procesos Python deterministas y skills para agentes de desarrollo, no múltiples inteligencias generativas haciendo predicciones.
- Vigilancia continua de partidos en directo y alertas intrapartido (requiere datos adecuados y servicio sostenido).
- Google Sheets: conexión de IMPORTDATA a autorizar desde navegador; proyecto dedicado de ChatGPT pendiente a petición del usuario.

## Consulta de uso simple
Abre cualquier conversación con acceso a GitHub y pide:
«Consulta \`rasekes86/football-ai-lab\`, lee \`output/informes_partidos.md\` y \`output/evaluacion_selecciones.json\` y dame el análisis y el Top 3 del próximo partido del Real Madrid; distingue cuotas justas de cuotas ofrecidas.»

Los nuevos informes se publican por GitHub Actions. Si el workflow falla o la fuente devuelve datos incompletos, los resultados previos pueden ser antiguos: comprueba las fechas de generación.
