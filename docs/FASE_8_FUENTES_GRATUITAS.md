# Fase 8 ampliada — Fuentes automáticas sin suscripción

Se han añadido **dos conectores opcionales** a la integración existente de
The Odds API: **5DollarFootballAPI (fuente preferente)** y **API-Football
(complemento / respaldo)**. No hay scraping de Flashscore ni automatización
del navegador de casas de apuestas.

## Fuentes, planes y limitaciones

**5DollarFootballAPI**
- [Documentación](https://5dollarfootballapi.com/docs),
  [precios](https://5dollarfootballapi.com/pricing),
  [condiciones de uso](https://5dollarfootballapi.com/terms).
- Plan Free: 0 $, sin tarjeta, hasta 60 peticiones/hora,
  las 5 grandes ligas (Premier League, LaLiga, Bundesliga, Serie A,
  Ligue 1) y cuotas Bet365 por encuentro. Segunda División solo si
  accedes a un plan/pack que la cubra (Community Access es gratuito bajo
  sus condiciones; no se garantiza el acceso).
- El plan Free NO permite `include=odds` en listados. La integración usa
  `GET /v1/fixtures` en ventanas de como máximo 24 horas y, para cada
  encuentro identificado, `GET /v1/fixtures/{id}/odds`.
- Límite propio: **5 fechas UTC, 14 partidos por defecto en el análisis diario**, y hasta **35 partidos en las tandas ligeras**.
  El controlador conserva un registro de peticiones entre ejecuciones, deja margen bajo el máximo del plan gratuito (48 de 60/h) y espacia las solicitudes. No presupone cuota disponible en otras aplicaciones que compartan la clave.
  Los partidos con una adicional +1,50 ya archivada quedan excluidos de cualquier recotización. Las cuotas y selecciones archivadas permanecen inmutables aunque la casa cambie su precio. Los partidos no archivados se rotan con prioridad para los nunca consultados, sin repetir precios recientes (hasta 4 h con cuotas, 2 h sin ellas).
  Se consulta el calendario por días (máximo dos páginas por día) y, si no
  se localiza una competición esperada, se busca su ID canónico por país/nombre
  y se consulta su calendario directamente. Las peticiones de descubrimiento
  están limitadas a **13**, más hasta **14** peticiones de cuotas: máximo **27**
  solicitudes en una ejecución. Con dos ejecuciones manuales muy seguidas
  puedes acercarte al límite horario de tu cuenta; compruébalo antes de repetir.
  Se reparten los 14 partidos por rondas entre ligas. No se emparejan por
  similitud dudosa, ni se fabrican precios cuando faltan datos.
- Consume exclusivamente precios del campo `closing` **antes** de empezar
  el partido. En el proveedor `closing` significa «último prepartido
  registrado hasta ese momento», NO cuota de cierre final.
  Como la respuesta no contiene necesariamente el instante del último
  cambio de precio, la web distingue **hora de captura** de «hora de
  actualización por el bookmaker».
- Compara 1X2, goles totales con línea exacta (principal y escalera
  fija), córners totales con línea exacta y BTTS. No confunde una línea
  genérica de tarjetas con **tarjetas amarillas**.
- Las condiciones del plan Free exigen una atribución visible. La web
  incluye **Football data by 5DollarFootballAPI** enlazado al proveedor.
  No se revende una API de cuotas.

**API-Football**
- [Documentación oficial](https://www.api-football.com/documentation_v3),
  [precios](https://www.api-football.com/pricing).
- Plan gratuito (según la oferta vigente): 100 llamadas/día, con
  cobertura de cuotas sujeta a ligas, partidos y bookmakers concretos.
- Búsqueda por fecha `GET /fixtures?date=...`, seguida de
  `GET /odds?fixture=...`, con **4 días** y **6 encuentros** como
  máximo por ejecución (hasta **10** peticiones, si hay coincidencias),
  compatible con la restricción oficial de 10 peticiones/minuto del plan Free.
  Se priorizan Segunda, Premier y Bundesliga cuando todavía no tenemos cuotas
  de 5DollarFootballAPI para esos partidos.
- Solo se reconocen **nombres explícitos** de mercado de tiempo completo:
  resultado 1X2, goles totales, córners totales, BTTS y
  **Total Yellow Cards** (amarillas). `Total Cards` o nombres
  ambiguos se ignoran, al igual que hándicaps asiáticos.
- Los tres resultados del 1X2 y los dos lados de cada línea deben existir
  para estimar el margen; se descartan mercados incompletos.
- Se utilizan la fecha de actualización real si la API la ofrece y
  la hora de captura en cualquier caso.
- La cobertura del plan gratis y los tipos de mercado **no están
  garantizados**: habilitar la integración no implica que existan
  cuotas disponibles para cada categoría o partido.

## Completar las seis ligas: diagnóstico y Community Access

A partir de noviembre de 2026, cada nueva consulta de 5DollarFootballAPI
registra en la auditoría `cobertura_ligas` los seis campeonatos con:
partidos del modelo, eventos devueltos por la API, coincidencias verificadas,
partidos consultados, precios validados y motivos de exclusión por nombres,
orden local/visitante u horario. También expone qué ligas se consultaron
directamente. Se ve en la pestaña **Cuotas reales**, sin publicar secretos.

**Premier y Bundesliga:** están dentro del Free de 5DollarFootballAPI.
Si el calendario general no aporta coincidencias, se consulta su catálogo
por país y nombre y, cuando devuelve un ID único, el calendario de esa liga.
La identificación del partido exige liga, dos clubes correctos, orden de
equipos y horario compatible. Algunos clubes alemanes usan grafías distintas:
las equivalencias están definidas explícitamente en el conector, no en los
IDs del modelo ni en su histórico Top 3.

**Segunda División:** no está garantizada en el Free normal. El proveedor
dispone de [Community Access](https://5dollarfootballapi.com/community),
otro plan a 0 $ para quienes cumplan sus requisitos, con un paquete de
país adicional; incluye la segunda categoría cuando está disponible
en el paquete elegido. **La aceptación y la disponibilidad no están
verificadas para tu cuenta hasta que las compruebes en el proveedor.**

Una vez activado el paquete **España** en Community Access:
1. Abre [Repository variables](https://github.com/rasekes86/football-ai-lab/settings/variables/actions).
2. Crea `ENABLE_FIVE_SEGUNDA` con valor `true`.
3. Ejecuta manualmente el análisis diario, o utiliza el horario programado.
4. Comprueba en **Cuotas reales → Cobertura por liga** si existen coincidencias
   verificadas de Segunda. No es necesario cambiar la API Key si tu cuenta
   conserva la misma.
5. Si el proveedor no devuelve Segunda, el panel lo indica expresamente;
   no se inventan cuotas ni se activa un plan de pago.

Con `ENABLE_FIVE_SEGUNDA=false` no se realizan consultas adicionales de
catálogo para Segunda, aunque los demás partidos siguen disponibles.

**API-Football** está implementada como respaldo, pero solo consulta si
`API_FOOTBALL_KEY` está guardada y `ENABLE_API_FOOTBALL_ODDS=true`.
El plan gratuito ofrece 100 consultas diarias y endpoints de odds con
**temporadas restringidas**, por lo que la disponibilidad de 2026/27 no
se debe presuponer. Puedes dejarlo desactivado si Community Access resuelve
la cobertura; se mantiene en un límite máximo de 10 peticiones por ejecución.

## Activación en GitHub (no compartas claves aquí)

1. Registra una cuenta gratuita en
   [5DollarFootballAPI](https://5dollarfootballapi.com/) y, opcionalmente,
   otra en [API-Football](https://www.api-football.com/).
2. Abre [Secrets and variables / Actions](https://github.com/rasekes86/football-ai-lab/settings/secrets/actions)
   de Football AI Lab.
3. En **Repository secrets**, crea `FIVEDOLLAR_API_KEY` con tu token
   5DollarFootballAPI y, opcionalmente, `API_FOOTBALL_KEY` con el token
   de API-Football. **No pongas ninguno en variables públicas, logs,
   la web, el código ni en este chat**.
4. En **Repository variables**, pon `ENABLE_FREE_ODDS=true`.
   Para activar también el respaldo, pon
   `ENABLE_API_FOOTBALL_ODDS=true`.
5. Opcionales para ahorrar solicitudes: `FREE_ODDS_MAX_FIXTURES=10`
   (máximo 14) y `API_FOOTBALL_MAX_FIXTURES=5` (máximo 8).
6. Ejecuta manualmente
   [Analisis futbol diario](https://github.com/rasekes86/football-ai-lab/actions/workflows/daily.yml)
   mediante **Run workflow**, o utiliza la ejecución diaria programada.
   No se consultan APIs de cuotas durante pushes de código.
7. Accede al [Comparador de cuotas reales](https://rasekes86.github.io/football-ai-lab/#realodds).
   Filtra por mercado, liga o equipo. La documentación de la
   [Fase 8 original](FASE_8_CUOTAS_REALES.md) describe los cálculos.

Puedes conservar The Odds API como tercera fuente, pero no es necesario
activarla para utilizar las dos gratuitas. Sin credenciales ni variables
de activación, todos los proveedores se mantienen en **DESACTIVADO** y
no se realizan llamadas ni se inventan cuotas.

## Verificación y límites de comparación

Las fuentes se mantienen separadas: cada fila registra proveedor,
bookmaker, mercado, línea, precio decimal, origen y fecha de captura.
No se cruzan partidos por similitud difusa: es necesaria coincidencia
inequívoca de liga, equipos local/visitante, fecha y horario. El modelo
solo se compara con la misma línea y sentido del mercado.

No se usan cuotas que puedan conllevar devolución o liquidación
fraccionaria cuando el modelo trata una selección binaria
ganada/perdida; por eso se ignoran líneas enteras y asiáticas.
No se extrapolan cuotas de tiros, faltas o dobles oportunidades.

El precio puede variar entre la captura y la consulta del usuario.
La probabilidad del modelo todavía requiere calibración prospectiva.
**Una diferencia positiva o un EV teórico positivo NO prueban
rentabilidad.** No se realizan apuestas ni se garantiza que un
bookmaker acepte una cuota en España.

### Auditoría

- `output/cuotas_reales_verificadas.json`: última captura real o
  estado de proveedores desactivados; ningún secreto se publica.
- `output/comparacion_cuotas_reales.json`: comparaciones cruzadas.
- `output/historico_cuotas_reales.json`: primeras observaciones reales
  de cada día por proveedor, partido, bookmaker, mercado y línea;
  nunca se rellenan retroactivamente.
- Pruebas Python: `tests/test_free_odds.py`; JavaScript:
  `site/tests/free_odds.test.mjs`. Se ejecutan en GitHub Actions sin
  credenciales con respuestas falsas controladas.

Para detener todo consumo, cambia `ENABLE_FREE_ODDS` y
`ENABLE_API_FOOTBALL_ODDS` a `false`.

## Rondas automáticas de cuotas (noviembre 2026)

El workflow `odds-refresh.yml` ejecuta una actualización ligera cada dos horas. Reutiliza los pronósticos publicados, sin modificar ni recalcular el Top 3. Solo incorpora nuevas adicionales si había una selección exacta y válida antes del inicio del partido. Una vez archivada, no se consulta ese partido de nuevo para buscar otro precio. Conserva el resultado histórico y la hora original del precio.

El estado `output/estado_consultas_cuotas.json` registra horarios e IDs públicos, nunca las claves. El plan Free se limita internamente a 48 solicitudes/hora, siempre teniendo en cuenta que la cuota real del proveedor puede compartirse. Si el proveedor devuelve 429 o falta cobertura, no se simulan cuotas. Community Access requiere habilitación expresa previa en la cuenta y variables de GitHub.

## Selección 3+1 por probabilidad y revisión excepcional (noviembre de 2026)

- Para **nuevas adicionales**, el sistema exige cuota real **estrictamente mayor que 1,50**, probabilidad de modelo >=50 %, EV teórico >3 %, identidad exacta de fixture/mercado/línea, y calidad no exploratoria. Dentro de estas opciones **prioriza la mayor probabilidad estimada**; el EV y la cuota sirven como desempate. No se fuerza diversidad artificial.
- **Advertencia importante:** esas probabilidades no están calibradas prospectivamente de manera suficiente. La auditoría de mercados futuros aporta aún muy pocos partidos independientes con resultados; no puede afirmarse que un 70 % estimado signifique 70 % de acierto real. No se presentan como calibradas.
- Se autorizó una **única revisión** de las adicionales API pendientes, usando únicamente el snapshot de comparaciones prepartido que ya estaba publicado. El proceso no recotiza ni solicita una clave nueva. Solo sustituye una selección si tiene una probabilidad estimada superior y cumple los filtros originales. No se tocan partidos finalizados, selecciones indicativas históricas ni Top 3.
- El archivo `output/historico_revisiones_adicionales_150.json` almacena **cada selección anterior y nueva**, fecha de revisión y fecha real de captura del precio. **Una cotización capturada antes de la revisión no es una cuota actual ni garantiza ejecución**. Se contabiliza exclusivamente la selección revisada en el 3+1 activo; las anteriores quedan como trazabilidad y no como picks simultáneos.
- La revisión se ejecuta **solo una vez** mediante el análisis de GitHub tras actualizar el código. Después vuelven a aplicarse las reglas de archivo inmutable, sin gastar consultas de la API en partidos con adicional asignada.
