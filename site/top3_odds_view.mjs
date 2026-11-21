/** Presentación separada de precios observados del Top 3.
 * Nunca mezcla ROI a cuota justa teórica con precios de bookmaker.
 */
const fmtNum = new Intl.NumberFormat("es-ES", {maximumFractionDigits:2});
const date = new Intl.DateTimeFormat("es-ES", {
  timeZone:"Europe/Madrid",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"
});
const escape = text => String(text??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));
const percent=n=>n==null?"—":fmtNum.format(Number(n))+" %";
const units=n=>n==null?"—":(Number(n)>0?"+":"")+fmtNum.format(Number(n))+" u.";

export function renderTop3ObservedPrices(model={}, league="") {
  const audit=model.top3QuoteAudit||{};
  const all=Array.isArray(model.top3QuoteRows)?model.top3QuoteRows:[];
  const data=league ? all.filter(r=>r.liga===league):all;
  const report=league?(audit.por_liga?.[league]||null):audit.global;
  const seen=data.length;
  const settled=report?.liquidadas||0;
  const hits=report?.aciertos||0;
  const losses=report?.fallos||0;
  const original=league?
    (model.archivedPicks||[]).filter(r=>r.liga===league).length:
    (audit.selecciones_originales||0);
  const ready=Boolean(audit.calculado_utc);
  const summary=`
    <div class="top3-price-kpis">
      <div><span>Con cuota prepartido</span><strong>${seen} / ${original}</strong></div>
      <div><span>Liquidaciones con precio</span><strong>${settled}</strong></div>
      <div><span>Acierto · solo cotizadas</span><strong>${hits} / ${settled} · ${percent(report?.acierto_pct)}</strong></div>
      <div><span>Balance hipotético · precio observado</span><strong>${units(report?.beneficio_hipotetico_unidades)} · ${percent(report?.roi_hipotetico_pct)}</strong></div>
    </div>
    <p class="top3-price-warning">${ready?
      "Los precios se capturan antes del partido. No se garantizan como apuestas ejecutables. Solo selecciones con coincidencia exacta y resultado confirmado entran en el ROI.":
      "Sin capturas todavía: se completará automáticamente cuando una fuente gratuita ofrezca el mercado exacto."}
      Sin cuota no hay rentabilidad calculada; las coincidencias con la adicional se excluyen del balance Top 3.
    </p>`;
  const visible=[...data].sort((a,b)=>(b.fecha_utc||"").localeCompare(a.fecha_utc||"") ||
      (a.clave||"").localeCompare(b.clave||"")).slice(0,8);
  const rows=visible.length?visible.map(r=>{
    const status=r.estado==="FINALIZADO"?
      r.resultado==="1"?"Acierto confirmado":"Fallo confirmado":
      r.estado==="SOLAPADA_ADICIONAL"?"Contabilizada como adicional":"Pendiente de verificar";
    const dt=Number.isFinite(Date.parse(r.capturado_utc||""))?
      date.format(new Date(r.capturado_utc)):"—";
    return `<article class="top3-price-row">
      <div><strong>${escape(r.local)} – ${escape(r.visitante)}</strong>
      <small>${escape(r.liga)} · ${escape(r.mercado)} · ${escape(r.seleccion)}</small>
      <small>${escape(r.bookmaker)} · Capturada ${escape(dt)}</small></div>
      <div class="top3-price-row-right"><strong>Cuota ${escape(fmtNum.format(Number(r.cuota_decimal||0)))}</strong>
      <small>${escape(status)}</small></div>
    </article>`;
  }).join(""):`<p class="top3-price-empty">Todavía no hay cuotas de bookmaker capturadas para este filtro. El Top 3 original sigue disponible sin cambios.</p>`;
  return {summary,rows};
}
