# Fase 9 · Telegram interactivo con botones (sin servidor de pago)

## Estado
El código del bot, menús, tests de seguridad y despliegue opcional están
implementados en `telegram-bot/` y `.github/workflows/telegram-bot.yml`.

**No estará conectado a Telegram hasta desplegarlo voluntariamente.**
Las alertas diarias de la Fase 7 siguen enviándose desde GitHub Actions.

## Qué puedes preguntarle

- `/start` o `/menu`: menú con botones: **Próximos partidos**,
  **Ligas**, **Mercados**, **Cuotas >1,50**, **Resultados**, **Ayuda**.
- Próximos partidos **del más cercano al más lejano** (máximo 14 días),
  con botones de navegación y botón individual por encuentro.
- Mercado por partido: goles, córners, tiros, tiros a puerta,
  amarillas, 1X2, doble oportunidad y otros cuando haya predicción.
- Selecciones originales Top 3 (sin crear un ranking nuevo);
  probabilidades y **cuotas justas estimadas**, nunca inventadas.
- Ficha estadística previa: forma, goles, córners históricos disponibles.
- **Cuotas de bookmaker realmente verificadas superiores a 1,50**
  si la Fase 8 dispone de datos recientes. Si está desactivada, lo informa.
  Se puede abrir por separado una lista de **cuotas justas teóricas**
  superiores a 1,50, claramente identificadas como no ofrecidas.
- Resultados y fiabilidad prospectiva exclusivamente cuando hay muestra,
  sin convertir los datos ausentes en derrotas.
- Preguntas sencillas por texto: «Tenerife», «Tenerife Ceuta»,
  «mañana», «goles», «córners», «cuotas 1,50», «resultados».
  No es una IA conversacional universal: para preguntas desconocidas
  devuelve ayuda en vez de inventar una respuesta.

**No realiza apuestas ni consulta cuotas o marcadores durante los partidos.**

## Infraestructura gratuita
GitHub Pages solo publica un sitio estático y no puede recibir mensajes de
Telegram en tiempo real. Para responder al tocar un botón necesitamos un
endpoint HTTPS. La implementación utiliza **Cloudflare Workers Free**
(100.000 solicitudes/día incluidas en el plan gratuito, sujeto a sus límites).
No requiere una suscripción de IA. Cada consulta lee los archivos JSON
públicos y recientes del repositorio a través de GitHub y se procesa
sin una base de datos ni API de LLM.

Documentación de Cloudflare:
https://developers.cloudflare.com/workers/platform/limits/

## Activarlo desde el móvil (una sola vez)

**1. Cuenta Cloudflare gratuita.**
Entra en https://dash.cloudflare.com/ y crea una cuenta Free.
Activa Workers & Pages y tu subdominio `workers.dev` si Cloudflare lo
solicita. No es necesario añadir un dominio propio.

**2. Conseguir el Account ID.**
En Cloudflare, abre Workers & Pages y copia el *Account ID* que aparece
para la cuenta. En algunos diseños se encuentra en la página de
información general de la cuenta.

**3. Crear un API Token de Cloudflare limitado a Workers.**
Abre https://dash.cloudflare.com/profile/api-tokens y pulsa
*Create Token*. Selecciona un token con permisos **Edit Cloudflare Workers**
limitado a tu cuenta (mejor que un token de API global).

**4. Guardar dos secretos nuevos en el repositorio.**
Desde Chrome en el móvil, entra en:
https://github.com/rasekes86/football-ai-lab/settings/secrets/actions

En **Repository secrets**, añade exactamente:
- `CLOUDFLARE_API_TOKEN`: token Cloudflare de permisos Workers.
- `CLOUDFLARE_ACCOUNT_ID`: identificador de la cuenta Cloudflare.

Ya existen `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`: **no hace falta
volver a crearlos ni compartirlos en ChatGPT**. GitHub los pasa al Worker
como secretos cifrados sin incluirlos en los archivos públicos.

**5. Desplegar y registrar el webhook automáticamente.**
Ve a:
https://github.com/rasekes86/football-ai-lab/actions/workflows/telegram-bot.yml

Pulsa **Run workflow** en `main`. Este flujo:
1. Ejecuta las pruebas de seguridad, menús y datos.
2. Publica el Worker en el plan Free de Cloudflare.
3. Carga los dos secretos Telegram al Worker.
4. Comprueba su URL HTTPS y registra el webhook en Telegram con
   el encabezado secreto derivado del token.
5. Configura los comandos visibles en Telegram.

Cuando el flujo termine correctamente, abre tu bot en Telegram,
envíale `/menu` y prueba los botones. No necesitas ejecutar el análisis
diario: el bot lee directamente los últimos datos publicados.

## Seguridad, privacidad y límites

- Solo atiende mensajes de **tu chat privado**: tanto el Chat ID de la
  conversación como el ID del remitente deben coincidir con el secreto.
- Solo acepta solicitudes con el encabezado secreto
  `X-Telegram-Bot-Api-Secret-Token` válido; lo calcula como SHA-256 del
  token del bot (sin publicarlo).
- El código y la web son públicos; las claves no se incorporan al
  repositorio. No envíes tokens por chat ni screenshots con credenciales.
- Los feeds caducados (más de 48 horas) y los partidos iniciados no se
  muestran como pronósticos actuales.
- Los precios deben tener captura y actualización verificables de menos
  de 24 horas antes del inicio.
- El webhook y el envío diario son compatibles: **setWebhook no desactiva
  `sendMessage`** de GitHub Actions. Lo que deshabilita es el polling
  de `getUpdates`, que este proyecto no usa.
- No publicamos cuota indicativa, cuota justa, backtest histórico o media
  de goles como si fueran **cuota real ofrecida**.
- Los mensajes y clicks dependen de la disponibilidad de GitHub,
  Cloudflare y Telegram. El plan gratuito tiene límites de uso.

## Pruebas

```bash
cd telegram-bot
npm test
```

## Desactivar la parte interactiva
En Cloudflare puedes desactivar el Worker; también puedes quitar el
webhook con `deleteWebhook` desde la Bot API de Telegram, usando tu
token en privado. No elimines las credenciales existentes de GitHub
si quieres seguir recibiendo los informes diarios.

## Verificación manual de partidos

El nuevo botón **🔄 Comprobar** y el comando `/comprobar` lanzan
`.github/workflows/verify-results.yml`. Solo se vuelven a comprobar
partidos finalizados con pronósticos archivados antes del inicio. Se
actualizan archivos de seguimiento, no los `historico_*`, ni se recalculan
pronósticos o solicitan cuotas nuevas. El bot envía el balance de los
últimos siete días, con Top 3 y una adicional registrada superior a 1,50,
aunque no haya nuevas liquidaciones. Resultados ausentes nunca son fallos.

La comprobación requiere **un permiso adicional** para llamar GitHub Actions.
Crea un token personal de GitHub de granularidad fina en
https://github.com/settings/personal-access-tokens/new
y limítalo al repositorio `rasekes86/football-ai-lab`, con permiso
**Actions: Read and write**. No envíes el token por chat.

Guárdalo en los secretos de Actions del repositorio como
`FOOTBALL_ACTIONS_TOKEN` en
https://github.com/rasekes86/football-ai-lab/settings/secrets/actions
y después vuelve a ejecutar `telegram-bot.yml` con **Run workflow**.
El despliegue transfiere el token como secreto cifrado al Worker.
Si falta, el botón muestra un aviso y no afirma haber iniciado nada.
El Worker debe estar desplegado y conectado para recibir el botón.

La misma verificación puede iniciarse sin Telegram desde
https://github.com/rasekes86/football-ai-lab/actions/workflows/verify-results.yml
pulsando **Run workflow**, sin token personal adicional.

## Nuevo informe por partido: `/detalle`

Después de `/comprobar`, el mensaje de Telegram identifica **cuántos
partidos con selecciones registradas** se han revisado, cuántos están
liquidados, parcialmente liquidados, pendientes y aún dentro del margen
de dos horas desde el inicio. También muestra los encuentros pendientes
y las nuevas liquidaciones más recientes.

El comando **`/detalle`** y el botón **«📋 Detalle por partido»**
permiten recorrer páginas de cinco encuentros, filtrando por todos,
pendientes y liquidados. Cada uno muestra la fecha de Madrid, nombres,
liga, número de selecciones Top 3/adicional resueltas y motivo de cada
pendiente: sin marcador final verificado, sin estadísticas finales
contrastadas, margen inicial de dos horas, datos inválidos o sin
liquidación concluyente.

El informe íntegro, sin truncarlo por los límites de Telegram, se
guarda en `output/verificacion_resultados_telegram.json` y solo cubre
los **últimos siete días de partidos con selecciones prospectivas**.
Los encuentros sin pronósticos archivados NO forman parte de este
inventario. La etiqueta «revisable» significa que ha pasado el margen
mínimo de dos horas y que se han procesado fuentes históricas,
verificaciones previas o ESPN; no afirma que se haya llamado en tiempo
real a una API para cada partido. Los registros congelados del Top 3,
las adicionales y el histórico de cuotas permanecen intactos.
