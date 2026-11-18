# Monitor de salud · Football AI Lab

## Corrección de calendario del proveedor

La ruta general GET /v1/fixtures de 5DollarFootballAPI admite ventanas
de un máximo de 24 horas (86.400 segundos). La versión anterior pedía
28 horas por día para cubrir partidos cerca de medianoche. La
documentación oficial confirma que devuelve invalid_time_window (HTTP 400).

La nueva función _calendar_window() usa estrictamente 24 horas por día.
Si es posible incluir todos los partidos del día del modelo con la
tolerancia ±2 horas, desplaza la ventana. Si no caben los partidos del
principio y final del día en la misma ventana, usa el día UTC original.
No añade peticiones y mantiene el cruce estricto de equipos, localía,
competición y horario. En caso de duda, descarta la cuota.

Documentación:
https://5dollarfootballapi.com/docs/fixtures
https://5dollarfootballapi.com/docs/errors#invalid_time_window

## Vigilancia automática de salud

El workflow «Vigilar salud de Football AI Lab» en
.github/workflows/health-watch.yml:

- Comprueba resultados al completar el análisis diario o el refresco
  de cuotas de la rama main.
- Ejecuta además un control cada cuatro horas, incluso sin nuevos workflows.
- En el primer chequeo manda un único aviso de activación al bot existente.
- Lee exclusivamente informes ya publicados en output/: no consume
  más API de cuotas, no altera el Top 3 ni recalcula pronósticos.
- Escribe su estado deduplicado y sin secretos en
  output/estado_salud.json. Solo avisa de incidencias nuevas, cambios
  y recuperaciones. No vuelve a notificar cada cuatro horas.
- Si Telegram no confirma la entrega, conserva la incidencia pendiente
  y reintenta; jamás registra el token ni la URL de la API de Telegram.

### Umbrales

| Situación | Control |
|---|---|
| Análisis o evaluación caducados | >36 horas |
| Cuotas sin actualizar, proveedor activado, partidos en próximos 5 días | >9 horas |
| Errores recurrentes del calendario | >=2 errores en cada una de 2 capturas nuevas y consecutivas |
| Liquidaciones retrasadas | >=2 encuentros distintos siguen PENDIENTE más de 48 horas |
| Análisis o refresco de cuotas fallidos en GitHub | Avisar hasta que ese workflow específico vuelva a pasar |
| No existe una apuesta adicional viable, hay una pérdida o faltan estadísticas finales | No se considera fallo operativo |

Los errores de calendario de una ronda aislada no generan aviso. El aviso
de recuperación requiere una ejecución posterior satisfactoria o una
captura nueva sin el problema. Las cotizaciones no ofrecidas no cuentan
como fallo ni como precio real.

## Activación y pruebas

Se reutilizan las claves TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID que
ya configuran Telegram y la variable ENABLE_FREE_ODDS. No necesitas
crear otro bot ni instalar servidores de pago.

El control de salud se activa por defecto cuando existen esos secretos.
Para deshabilitar sus notificaciones, establece la variable de GitHub
HEALTH_ALERTS_ENABLED=false. Las alertas habituales del Top 3 y las
adicionales siguen funcionando por separado.

Comprobación sin enviar mensajes ni alterar estado:

    PYTHONPATH=src python -m football_ai_lab.health_monitor --preview

Pruebas sin red ni claves:

    PYTHONPATH=src python -m unittest discover -s tests -p test_health_monitor.py -v

Workflow:
https://github.com/rasekes86/football-ai-lab/actions/workflows/health-watch.yml
