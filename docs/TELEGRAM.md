# Telegram · activación opcional sin pagos

El módulo ya existe en \`src/football_ai_lab/telegram_notify.py\` y se invoca
en los análisis **programados** o **iniciados manualmente** de GitHub Actions.
Hasta configurar dos secretos no enviará mensajes y no supondrá costes de API.

## Configuración sin compartir credenciales con ChatGPT
1. Abre Telegram y crea un bot con **@BotFather** mediante el comando \`/newbot\`.
2. Guarda el token en privado y abre el chat con tu bot. Escribe \`/start\`.
3. Obtén tu Chat ID del bot con una herramienta de confianza o con la respuesta de la API
   \`getUpdates\` después del primer mensaje. No publiques el token ni lo pegues en una conversación.
4. En GitHub: \`rasekes86/football-ai-lab\` → **Settings → Secrets and variables → Actions → New repository secret**.
5. Crea exactamente estos secretos: \`TELEGRAM_BOT_TOKEN\` y \`TELEGRAM_CHAT_ID\`.
6. En GitHub Actions, ejecuta manualmente **Analisis futbol diario** para probarlo,
   o espera a la siguiente ejecución programada.

No hay envíos al introducir cambios en el código (\`push\`), para evitar avisos duplicados
mientras desarrollamos.

El mensaje incluye un Top 3 con probabilidades **no calibradas**, cuotas
**justas matemáticas** (NO ofrecidas) y recuento prospectivo. No contiene
instrucciones para apostar, ni anuncios de certeza o de beneficio.
