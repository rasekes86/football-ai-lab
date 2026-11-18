# Football AI Lab · ROI hipotético del Top 3 a cuota justa

## Objetivo

Medir un escenario de **1 unidad por selección** para los **tres pronósticos originales archivados antes de cada partido** sin consultar cuotas de apuestas de esos mercados.

### Fórmulas

Para una selección originalmente archivada con probabilidad del modelo `p`, siendo `0 < p <= 1`:

- **Cuota justa teórica** (NO ofrecida por ninguna casa): `q = 1 / p`.
- **Si se confirma el acierto:** `retorno = q - 1` unidades netas.
- **Si se confirma el fallo:** `retorno = -1` unidad neta.
- **Si falta marcador o la estadística:** el retorno es `null`, no una pérdida.
- **Balance:** suma de retornos liquidados con probabilidad archivada válida.
- **ROI hipotético:** `balance / número de selecciones liquidadas con cuota justa válida`.

**Nunca** calcular a partir de nuevas estimaciones del modelo, de mercados explorados o del cuarto pronóstico no seleccionado. La cuota justa deriva exclusivamente del porcentaje guardado en el histórico prospectivo.

### Contabilidad independiente

1. **Top 3: simulación a cuota justa**: solo los tres originales por encuentro; no requiere ni intenta recuperar cuotas reales.
2. **Adicional: simulación a cuota archivada**: precio observado por API o referencia indicativa, con el tipo claramente identificado. Si no hay adicional, no hay apuesta adicional.
3. **3+1: simulación mixta**: balance = (Top 3 simulado a cuota justa) + (adicional a cuota archivada); ROI = balance / (número total de unidades liquidadas con cuota disponible para ese escenario).

Nunca se afirma que la cuota justa fue ofertada, que se efectuó una apuesta, ni que hay ventaja comprobada. El valor esperado teórico de apostar a `1/p` usando esa misma probabilidad `p` es **exactamente cero** antes de margen/comisiones: esta métrica describe resultados observados *dentro de una hipótesis*, no puede medir ROI real ni rentabilidad explotable del modelo.

### Integridad y consumo

- No se añaden peticiones de cuotas ni API keys.
- Se respetan el Top 3 inmutable, sus probabilidades anteriores al encuentro, el histórico de resultado confirmado y la única adicional archivada.
- La simulación se calcula en el panel de lectura, sin reescribir archivos de pronósticos ni precios.
- No se redondean cuotas antes del cálculo; la interfaz sí redondea para legibilidad.
