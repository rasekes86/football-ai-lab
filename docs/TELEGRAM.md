# Fase 7 · Alertas automáticas en Telegram

La Fase 7 reutiliza el análisis diario y los pronósticos ya archivados en
Football AI Lab. **No requiere una API de pago ni conecta casas de apuestas.**

## Qué recibirás

Un resumen una vez al día cuando se ejecuta GitHub Actions (habitualmente
a las **07:17 UTC: 08:17 en Madrid en invierno, 09:17 en verano**):

- Próximos partidos con una selección por encuentro que cumpla los filtros,
  ordenados por fecha. Se incluye hora de Madrid, competición, mercado,
  selección, probabilidad **estimada del modelo** y categoría de validación.
  Se da prioridad al Top 3 original y a líneas con backtest retrospectivo.
  Es un filtro de información, **no una recomendación de apuesta**.
- Resultados nuevos de selecciones que se archivaron **antes** del inicio y
  se liquidaron con estadísticas verificadas: ✓ acierto / ✗ fallo.
- Si hay resultados sin marcador o sin estadística completa, un aviso los
  distingue explícitamente de los fallos.

Se usa `output/pronosticos_mercados_futuros.json` para próximos partidos
y `output/seguimiento_mercados_futuros.csv` para liquidaciones
prospectivas de la Fase 4. **No se cambia el Top 3 ni se reconstruyen
pronósticos antiguos.** No hay resultados garantizados, apuestas automáticas
ni cuotas comerciales verificadas.

Una ejecución manual en GitHub Actions el mismo día no vuelve a mandar el
resumen diario, salvo que hayan aparecido resultados nuevos. El control
anti-duplicados se guarda en `output/estado_alertas_telegram.json` **solo
si Telegram confirma el envío**. Este archivo contiene fechas y claves
de selecciones (no tokens ni identificadores del chat).

## Cómo activarlo — sin enviar credenciales por ChatGPT

1. Abre [@BotFather](https://t.me/BotFather) en Telegram y envía `/newbot`.
   Elige nombre y usuario para crear el bot.
2. Guarda el token que te proporcione BotFather **en privado**.
   Abre tu nuevo bot y envíale `/start`.
3. Consigue tu identificador numérico del chat (Chat ID) consultando de
   forma privada la respuesta de `getUpdates` del bot, después de mandarle
   un mensaje. En un grupo, el ID puede ser negativo. **No compartas el
   token ni el Chat ID aquí.**
4. Abre el repositorio:
   [GitHub → Settings → Secrets and variables → Actions](https://github.com/rasekes86/football-ai-lab/settings/secrets/actions).
   En **Repository secrets**, crea:
   - `TELEGRAM_BOT_TOKEN`: token del bot.
   - `TELEGRAM_CHAT_ID`: identificador numérico del chat.
5. En **Repository variables** de esa misma pantalla, crea:
   `TELEGRAM_ALERTS_ENABLED` con valor `true`. Esto permite habilitar o
   deshabilitar el envío sin borrar los secretos.
6. Abre [Actions → Analisis futbol diario](https://github.com/rasekes86/football-ai-lab/actions/workflows/daily.yml)
   y utiliza **Run workflow** para enviar el primer resumen y comprobar el
   paso «Alertas Fase 7 por Telegram». La ejecución normal diaria seguirá
   enviando automáticamente cuando haya permiso.

**Sin los dos secretos y la variable de activación, no se envía nada.**
No hay mensajes en los pushes de código. Las llamadas de prueba usan un
transporte ficticio; no envían mensajes reales.

## Filtros configurables (Repository variables)

No necesitas instalar nada. Todas las variables son opcionales salvo
`TELEGRAM_ALERTS_ENABLED=true`.

| Variable | Valor por defecto | Ejemplo |
|---|---|---|
| `TELEGRAM_ALERT_MARKETS` | Todos los mercados con modelo | `corners,double,shots` |
| `TELEGRAM_ALERT_LEAGUES` | Las 6 ligas | `Segunda División,LaLiga` |
| `TELEGRAM_ALERT_MIN_PROBABILITY` | `0.65` | `0.75` |
| `TELEGRAM_ALERT_QUALITY` | `all` | `top3`, `audited`, `exploratory`, `uncalibrated` |
| `TELEGRAM_ALERT_HORIZON_HOURS` | `72` | `48` |
| `TELEGRAM_ALERT_RESULTS_DAYS` | `21` | `14` |
| `TELEGRAM_ALERT_MAX_UPCOMING` | `6` | `4` |
| `TELEGRAM_ALERT_MAX_RESULTS` | `8` | `6` |

Mercados admitidos: `corners`, `shots`, `on_target`, `yellow`,
`goals`, `result`, `double`, `btts`. Si el motor no genera
pronósticos futuros para una categoría, no se inventa ninguno. La
probabilidad mínima **no indica rentabilidad**.

El resumen diario se envía a la hora UTC indicada, no a la misma hora
civil todo el año; la hora en Madrid cambia con el horario de verano.
Los resultados nuevos se notifican en el siguiente análisis programado
o manual, **no necesariamente al minuto de terminar el partido**.
Si faltan resultados verificados, quedan pendientes de aviso.

## Prueba y resolución de problemas

```bash
python -m football_ai_lab.telegram_alerts --preview
python -m unittest discover -s tests -v
```

La opción `--preview` muestra el mensaje generado sin enviar, escribir el
estado ni necesitar credenciales. El job automático usa `sendMessage`
de Telegram con POST y no imprime la URL del token. Si el proveedor
rechaza el mensaje, no se avanza el registro anti-duplicados.

Para desactivar: cambia `TELEGRAM_ALERTS_ENABLED` a `false`.
Para cambiar el chat: edita `TELEGRAM_CHAT_ID` en GitHub Secrets y
comprueba que el nuevo usuario ha iniciado el bot con `/start`.
