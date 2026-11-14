# Fuentes de datos, derechos y límites de uso

Este repositorio es un **prototipo personal de investigación**, no un producto
comercial de predicción ni una garantía de acceso gratuito a los proveedores.

## Fuentes
- **football-data.co.uk**: resultados, estadísticas de partidos y algunas cuotas históricas. Su sitio indica uso gratuito para particulares, pero limita aplicaciones comerciales, entrenamiento de productos de IA y automatización mediante bots/scrapers. Es necesario revisar sus condiciones y permisos vigentes antes de dar servicio a terceros o aumentar el volumen de consultas. El flujo actual de GitHub es automático y no constituye una licencia concedida por el proveedor. Referencia: https://www.football-data.co.uk/data
- **ESPN públicos no oficiales**: calendario y pequeños lotes de detalles/plantillas de partidos. Endpoint no documentado; puede cambiar, bloquear accesos o no devolver jugadores. No se presupone autorización comercial. Referencia: https://github.com/machina-sports/sports-skills
- **Machina sports-skills / Understat**: adaptador abierto cuya procedencia no concede derechos sobre los datos de origen; el xG real sigue sin cubrir todos los encuentros. El formato canónico Machina puede etiquetar datos como prototype-only, no comerciales. Referencia: https://github.com/machina-sports/sports-skills
- **InferSports**: referencias limitadas y sujetas a disponibilidad; NO son necesariamente precios ofrecidos por casas de apuestas.
- **The Odds API**: desactivada hasta que el propietario aporte clave y habilitación explícita. Puede tener límites y costes.

## Prioridades para operar de forma sostenible
1. **No aumentar automáticamente el scraping** hasta revisar condiciones del proveedor.
2. Preferir fuentes licenciadas explícitamente para cada uso, o datasets abiertos (p. ej. openfootball, verificando su licencia y cobertura).
3. Guardar fecha, fuente, identificador del partido, ausencias y calidad de datos; no inventar cuotas ni estadísticas.
4. Requerir permiso explícito del titular del proyecto antes de contratar APIs de pago o publicar un servicio comercial.
5. Las probabilidades experimentales no demuestran rentabilidad ni sustituyen controles de riesgo.

## Estado práctico
Los análisis diarios de un prototipo personal ya están implementados en GitHub.
Su ejecución con cualquier proveedor depende de los términos vigentes, de la
disponibilidad real de datos y de los límites de acceso del servicio.
