# Montaje cloud gratuito
Este repositorio público aloja el código y CSV derivados, no los datos históricos originales.

1. En GitHub abre **Actions → Analisis futbol diario → Run workflow**.
2. Comprueba que los tests estén en verde y revisa los logs de fuentes y pipeline.
3. Abre output/informe.md para conocer hora UTC, modo REAL, descartes y recuentos.
4. Comprueba que output/predicciones.csv se ha actualizado y que no incluye pronósticos DEMO.
5. Abre Google Sheets en navegador de escritorio: la pestaña **Auto pronósticos** ya contiene la fórmula de importación en A4.
6. La pestaña **Auto seguimiento** ya contiene su fórmula en A4. **No** pegues fórmulas en las pestañas de fotografía fija Pronósticos ni Seguimiento.
7. Google Sheets puede solicitar autorización de acceso a URL externa. IMPORTDATA no refresca en tiempo real y puede cachear.
8. Si el contador es cero, inspecciona logs y nombres de equipos. El programa nunca inventará encuentros.

Para repositorios privados, IMPORTDATA no podrá leer sin autenticación. Se necesitaría otro puente a Sheets API.
No compartas claves API en commits.


## Avance v0.2
El repositorio ya está publicado. El motor automatizado produce informe, comparación de mercado de InferSports keyless (limitada a tres consultas) y The Odds API opcional (desactivada sin clave), backtest y bitácora de agentes. La hoja de Google Sheets requiere autorización IMPORTDATA para importación desatendida; desde ChatGPT pueden consultarse los archivos publicados en GitHub.
