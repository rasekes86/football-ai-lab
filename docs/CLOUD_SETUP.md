# Montaje cloud gratuito
Este repositorio público aloja el código y CSV derivados, no los datos históricos originales.

1. En GitHub abre **Actions → Analisis futbol diario → Run workflow**.
2. Comprueba que los tests estén en verde y revisa los logs de fuentes y pipeline.
3. Abre output/informe.md para conocer hora UTC, modo REAL, descartes y recuentos.
4. Comprueba que output/predicciones.csv se ha actualizado y que no incluye pronósticos DEMO.
5. En el Google Sheet abre desde navegador de escritorio y en **Pronósticos!A4** coloca:
   =IMPORTDATA("https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/predicciones.csv")
6. En **Seguimiento!A4** coloca:
   =IMPORTDATA("https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/seguimiento.csv")
7. Google Sheets puede solicitar autorización de acceso a URL externa. IMPORTDATA no refresca en tiempo real y puede cachear.
8. Si el contador es cero, inspecciona logs y nombres de equipos. El programa nunca inventará encuentros.

Para repositorios privados, IMPORTDATA no podrá leer sin autenticación. Se necesitaría otro puente a Sheets API.
No compartas claves API en commits.


## Avance v0.2
El repositorio ya está publicado. El motor automatizado produce informe, comparación de mercado (desactivada sin API), backtest y bitácora de agentes. La hoja de Google Sheets requiere autorización IMPORTDATA para importación desatendida; desde ChatGPT pueden consultarse los archivos publicados en GitHub.
