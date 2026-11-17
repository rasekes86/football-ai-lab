/** Estados reales de la adicional 3+1: nunca confundir no consultado con descarte. */
export function additionalStatus(match, now = new Date()) {
  if (!match?.id) return null;
  const kick = Date.parse(match.fecha_utc || "");
  const frozen = (match.odds || []).some(row =>
    row?.id === match.id &&
    ["OFRECIDA_API_REGISTRADA","INDICATIVA_NO_VERIFICADA"].includes(row.tipo_cuota) &&
    Number(row.cuota_decimal) > 1.50 &&
    Date.parse(row.archivado_utc || "") < kick);
  if (frozen) return {
    code:"ASSIGNED", style:"assigned", label:"Adicional asignada",
    explanation:"Selección y cuota archivadas; no se vuelven a consultar."
  };
  if (!Number.isFinite(kick) || kick <= now.getTime()) return null;
  switch (match.additionalAudit) {
    case "NO_SUPERA_FILTROS":
      return {
        code:"NO_VIABLE", style:"unviable", label:"Sin adicional viable",
        explanation:"Cuotas comparadas, pero ninguna cumple todos los filtros: cuota mayor que 1,50, probabilidad mínima del 50 %, EV teórico mayor que 3 % y calidad del modelo."
      };
    case "SIN_CUOTAS_COMPATIBLES":
      return {
        code:"NO_COMPATIBLE", style:"unviable", label:"Sin adicional viable",
        explanation:"Se consultó el proveedor, pero no se obtuvo una cuota compatible para un mercado y una selección verificables."
      };
    case "SELECCIONABLE":
      return {
        code:"PENDING", style:"pending", label:"Pendiente de archivar",
        explanation:"Se identificó una opción apta; la publicación todavía no tiene una adicional archivada."
      };
    default:
      return {
        code:"NOT_QUERIED", style:"pending", label:"Pendiente de consulta",
        explanation:"Todavía no consta una consulta de cuotas para este partido. La falta de una adicional no implica que se haya descartado."
      };
  }
}
