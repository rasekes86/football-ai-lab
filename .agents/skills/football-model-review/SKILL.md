---
name: football-model-review
description: Audita el modelo de fútbol, su calibración y el posible uso de información futura
---
# Revisión de modelos de fútbol
1. Revisa fechas, fuente y esquema de datos.
2. Confirma que el modelo no use información posterior al partido.
3. Reproduce las pruebas unitarias.
4. Inspecciona la calibración, Brier y log loss en una ventana temporal no usada para entrenar.
5. Detecta sesgos de selección de partidos, diferencias de nombres y cambios de liga.
6. Nunca confundas una cuota justa calculada con la cotización real de una casa.
7. No declares rentabilidad si no hay backtest independiente.
