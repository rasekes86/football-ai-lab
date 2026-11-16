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
- Límite propio: **5 fechas UTC y 14 partidos** como máximo por ejecución.
  Los 14 partidos se distribuyen por rondas entre las ligas elegibles,
  en lugar de gastarse en las primeras ligas de la respuesta del proveedor.
  Si alguna competición no ofrece encuentros emparejados en esas fechas,
  no se inventan precios para ella. Una ejecución completa consume como
  máximo 5+14=19 solicitudes; el límite por hora puede verse afectado por
  otros usos de tu cuenta.
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
  `GET /odds?fixture=...`, con **4 días** y **8 encuentros** como
  máximo por ejecución (hasta 12 peticiones, si hay coincidencias).
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
