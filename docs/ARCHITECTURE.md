# Arquitectura y fases — Football AI Lab 0.4

## Ejecutado de verdad

| Fase | Estado | Componente |
|---|---|---|
| Cloud gratuito | Operativo | GitHub Actions, 3 workflows y archivos públicos |
| Cinco ligas | Operativo | Calendario ESPN + histórico football-data.co.uk |
| Modelos base | Operativo | Poisson/Elo (70/30) |
| XGBoost | Experimental validado temporalmente | Workflow semanal, salida output_ml/ |
| Auditoría | Parcial | Walk-forward y holdout; pendiente calibración prospectiva continuada |
| Machina Sports | Operativo para contexto | Cinco clasificaciones, bajas Premier, sin alterar probabilidades |
| InferSports | Limitado | Consulta de referencia 1X2 fair, máximo 3/ejecución |
| The Odds API | Desactivado | Requiere clave y ENABLE_ODDS=1 |
| Codex/Claude skills | Disponibles | Machina, Match Predictor, InferSports, auditoría Claude Quant adaptada |
| Preguntas desde ChatGPT | Probado | Issue [ANALISIS], comentario del bot |
| Directo desde ChatGPT | Desarrollado y con pruebas unitarias | Issue [DIRECTO], lectura puntual InferSports; no monitor continuo |
| Google Sheets | Fotografías visibles, sincronización pendiente | IMPORTDATA necesita autorización |
| LangGraph / agentes LLM | No desplegado | De momento no aporta valor proporcional al coste |
| In-play a escala | No desplegado | Requeriría mayor frecuencia, datos y servidor continuo |

## Flujo diario
GitHub Actions -> fuentes -> contexto Machina -> Poisson/Elo -> referencia InferSports opcional -> auditoría -> seguimiento -> CSV/JSON/Markdown.

## Flujo semanal de entrenamiento
Históricos -> features calculadas con observaciones anteriores al partido -> corte cronológico -> entrenamiento XGBoost -> holdout -> evaluación -> métricas y predicciones experimentales.

NO mezclar resultados de validación de entrenamiento con señales para apostar. XGBoost se mantiene en un canal separado mientras no se contraste suficiente contra Poisson/Elo en el mismo holdout y contra mercados reales.

## Consultas a demanda
El propietario crea un Issue en GitHub. Un workflow verifica el título, consulta calendario e históricos y publica respuesta en un comentario. El título [DIRECTO] consulta InferSports y rechaza resultados con más de 5 minutos de antigüedad o marcador/partidos ambiguos. El funcionamiento en directo se ha probado con fixtures ficticios; no se ha comprobado una consulta durante un partido en marcha.

## Riesgos y transparencia
Los "agentes" son módulos de Python; no afirmamos tener siete modelos generativos autónomos. El calendario es no oficial; las bajas de Machina pueden incluir dudas o indisponibilidad por causas variadas; las probabilidades del mercado solo se usan con fecha y fuente; ninguna parte hace apuestas reales.
