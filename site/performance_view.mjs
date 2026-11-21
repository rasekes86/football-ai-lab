/** Render-only scoreboard: only archived Top 3 and single additional >1.50. */
import {performanceSnapshot} from "./performance.mjs";

const num=new Intl.NumberFormat("es-ES",{maximumFractionDigits:0});
const pct=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:1});
const decimal=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2});
const dateFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",day:"2-digit",month:"short",year:"numeric"});
const quoteFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rate=x=>x===null||x===undefined?"—":pct.format(x);
const units=x=>x===null||x===undefined?"—":(x>0?"+":x<0?"−":"")+decimal.format(Math.abs(x))+" u.";
const count=x=>num.format(x||0);
const day=x=>Number.isFinite(Date.parse(x||""))?dateFmt.format(new Date(x)):"—";

export function confirmedOutcome(row){
  if(row.estado!=="FINALIZADO"||!["0","1"].includes(String(row.resultado))){
    const unavailable=row.estado==="ESTADISTICA_NO_DISPONIBLE"||
      row.estado==="RESULTADO_NO_DISPONIBLE";
    const status=row.estado==="ESTADISTICA_NO_DISPONIBLE"?"Estadística sin verificar":
      row.estado==="RESULTADO_NO_DISPONIBLE"?"Resultado sin verificar":"Pendiente";
    return '<span class="status-pill '+(unavailable?"missing":"pending")+'">'+escape(status)+'</span>';
  }
  const won=String(row.resultado)==="1";
  return '<span class="status-pill '+(won?"final":"loss")+'">'+
    (won?"ACIERTO CONFIRMADO":"FALLO CONFIRMADO")+'</span>';
}
function metric(label,value,foot,emph=false){
  return '<div class="kpi'+(emph?' highlight':'')+'"><div class="kpi-label">'+escape(label)+
    '</div><div class="kpi-value">'+escape(value)+'</div><div class="kpi-footer">'+
    escape(foot)+'</div></div>';
}
function topGraph(rows){
  const selected=rows.filter(x=>x.top>0).slice(-14);
  if(!selected.length)return '<div class="empty">No hay Top 3 liquidados para este periodo.</div>';
  return selected.map(row=>{
    const percent=Math.round(100*(row.topAccuracy||0));
    return '<div class="performance-period-row"><span class="performance-period-date">'+escape(row.key)+
      '</span><div class="performance-period-track" aria-label="'+percent+' por ciento de aciertos">'+
      '<div style="width:'+percent+'%"></div></div><strong>'+rate(row.topAccuracy)+
      '</strong><small>'+count(row.topHits)+'/'+count(row.top)+'</small></div>';
  }).join("");
}
function profitGraph(rows){
  const valid=rows.filter(x=>x.extraCumulative!==null);
  if(!valid.length)return '<div class="empty">No hay adicionales liquidadas con cuota archivada en el periodo.</div>';
  const vals=valid.map(x=>x.extraCumulative);
  const hi=Math.max(.25,...vals),lo=Math.min(-.25,...vals);
  const sx=i=>valid.length===1?180:22+316*i/(valid.length-1);
  const sy=value=>135-(value-lo)/(hi-lo)*113;
  const points=valid.map((x,i)=>sx(i).toFixed(1)+','+sy(x.extraCumulative).toFixed(1)).join(' ');
  const dots=valid.map((x,i)=>'<circle cx="'+sx(i).toFixed(1)+'" cy="'+sy(x.extraCumulative).toFixed(1)+'" r="3.5"></circle>').join('');
  const zero=sy(0).toFixed(1);
  const label=valid.length>1?valid[0].key+" — "+valid[valid.length-1].key:valid[0].key;
  const latest=valid[valid.length-1].extraCumulative;
  return '<svg class="performance-profit-svg" viewBox="0 0 360 160" role="img" aria-label="Balance hipotético acumulado '+escape(units(latest))+
    '" preserveAspectRatio="xMidYMid meet"><line x1="12" y1="'+zero+'" x2="346" y2="'+zero+
    '" class="performance-zero"></line><polyline points="'+points+
    '" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'+
    '<g fill="currentColor">'+dots+'</g></svg><div class="performance-chart-footer"><span>'+
    escape(label)+'</span><strong>'+escape(units(latest))+'</strong></div>';
}
function leagueTable(leagues,filter){
  return leagues.filter(x=>!filter||x.name===filter).map(x=>
    '<article class="performance-league-card"><div class="performance-league-title"><strong>'+
    escape(x.name)+'</strong></div><div class="performance-league-metrics">'+
    '<div><span>Top 3 · acertadas / verificadas</span><strong>'+count(x.top.hits)+' / '+count(x.top.settled)+
    '</strong><small>'+rate(x.top.accuracy)+'</small></div>'+
    '<div><span>Adicional · acertadas / verificadas</span><strong>'+count(x.additional.hits)+' / '+count(x.additional.settled)+
    '</strong><small>'+rate(x.additional.accuracy)+'</small></div></div></article>'
  ).join("");
}
function ledger(rows){
  if(!rows.length)return '<tr><td class="empty" colspan="5">Sin selecciones archivadas para este filtro.</td></tr>';
  return rows.map(row=>{
    const additional=row.group!=="Top 3";
    const source=additional?(row.tipo_cuota==="INDICATIVA_NO_VERIFICADA"?
      "Precio orientativo, no acreditado":row.tipo_cuota==="OFRECIDA_API_REGISTRADA"?
      "Cuota API registrada":row.tipo_cuota==="CUOTA_JUSTA_TEORICA_NO_OFRECIDA"?
      "Cuota justa teórica del modelo; NO ofrecida por bookmaker":"Sin origen de cuota"):
      "Cuota justa del modelo (= 1 / probabilidad archivada), NO ofertada por una casa";
    // Timestamp is the published OBSERVATION time, never a claimed bet placement.
    const observed=Number.isFinite(Date.parse(row.fecha_cuota_utc||""))?
      quoteFmt.format(new Date(row.fecha_cuota_utc)):"";
    const evidence=additional&&row.tipo_cuota==="OFRECIDA_API_REGISTRADA"?
      [row.bookmaker,row.proveedor_cuota,observed?"captura "+observed:"",
       row.marca_tiempo_tipo==="CAPTURA_NO_ACTUALIZACION"?"sin hora de cambio del bookmaker":""]
        .filter(Boolean).join(" · "):"";
    const price=row.price!==null&&Number.isFinite(row.price)?
      decimal.format(row.price):"—";
    const balance=row.return!==null?units(row.return):"—";
    return '<tr><td><div class="main-cell">'+escape(row.local)+' – '+escape(row.visitante)+
      '</div><div class="sub-cell">'+escape(day(row.fecha_utc))+' · '+escape(row.liga)+
      '</div></td><td class="pick-cell"><div class="main-cell">'+escape(row.seleccion)+
      '</div><div class="sub-cell">'+escape(row.group)+
      (price!=="—"?' · '+(additional&&row.tipo_cuota!=="CUOTA_JUSTA_TEORICA_NO_OFRECIDA"?'cuota archivada ':'cuota justa teórica ')+price:'')+
      ' · '+escape(source)+(evidence?' · '+escape(evidence):'')+'</div></td><td>'+confirmedOutcome(row)+
      '</td><td class="performance-return">'+escape(balance)+
      '</td><td><button type="button" class="row-link" data-open-id="'+escape(row.id)+
      '" aria-label="Abrir ficha del partido">↗</button></td></tr>';
  }).join("");
}
function automatedAudit(model,league){
  const audit=model?.evaluations?.odds?.seleccion_automatica;
  if(!audit||!audit.por_liga){
    return '<div class="performance-auto-title">SELECCIÓN AUTOMÁTICA · 3+1</div>'+
      '<p>El diagnóstico de la selección automática aparecerá cuando finalice el siguiente análisis diario con esta versión. El histórico de resultados ya es válido.</p>';
  }
  if(audit.estado==="FUENTES_NO_CONSULTADAS"){
    return '<div class="performance-auto-title">SELECCIÓN AUTOMÁTICA · FUENTES NO CONSULTADAS</div>'+
      '<p>La última ejecución se inició por un cambio de código y no utilizó las APIs privadas de cuotas. '+
      'No se consideran apuestas descartadas: es necesario un análisis programado o manual autorizado para evaluar las próximas adicionales. '+
      'El Top 3 y las selecciones históricas siguen guardados.</p>';
  }
  const selected=league?[ [league,audit.por_liga[league]] ]:
    Object.entries(audit.por_liga);
  const overview=selected.filter(([name,stats])=>name&&stats);
  const newPicks=overview.reduce((a,[,x])=>a+(x.archivadas_automaticas||0),0);
  const noOption=overview.reduce((a,[,x])=>a+(x.sin_opcion_valida||0),0);
  const already=overview.reduce((a,[,x])=>a+(x.ya_archivadas||0),0);
  const matched=overview.reduce((a,[,x])=>a+(x.partidos_con_comparaciones||0),0);
  const details=overview.map(([name,stats])=>
    '<div class="performance-auto-league"><strong>'+escape(name)+'</strong>'+
    '<span>'+count(stats.archivadas_automaticas)+' nuevas · '+
      count(stats.ya_archivadas)+' ya archivadas · '+
      count(stats.sin_opcion_valida)+' sin opción válida</span></div>'
  ).join('');
  return '<div class="performance-auto-title">SELECCIÓN AUTOMÁTICA · ÚLTIMO ANÁLISIS</div>'+
    '<div class="performance-auto-metrics">'+
    '<div><strong>'+count(newPicks)+'</strong><small>nuevas adicionales</small></div>'+
    '<div><strong>'+count(matched)+'</strong><small>partidos con precios comparados</small></div>'+
    '<div><strong>'+count(noOption)+'</strong><small>sin opción válida</small></div>'+
    '<div><strong>'+count(already)+'</strong><small>ya archivados</small></div></div>'+
    '<div class="performance-auto-leagues">'+details+'</div>'+
    '<p>Si no hay una cuota observada que cumpla los criterios antes del inicio, el sistema se abstiene. No inventa una apuesta ni modifica el Top 3.</p>';
}

export function renderPerformanceView(model,filters={},limit=36,now=new Date()){
  const info=performanceSnapshot(model,filters,now);
  const top=info.top,additional=info.additional,combined=info.combined;
  return {
    topKpis:
      metric("Aciertos confirmados",count(top.hits)+" / "+count(top.settled),"Solo Top 3 congelado",true)+
      metric("Tasa de acierto",rate(top.accuracy),"Sin contar los pendientes")+
      metric("Balance cuota justa",units(top.fairProfit),count(top.fairCount)+" selecciones liquidadas · 1 u.")+
      metric("ROI cuota justa",rate(top.fairRoi),"Hipótesis del modelo, no cuota real"),
    extraKpis:
      metric("Aciertos confirmados",count(additional.hits)+" / "+count(additional.settled),"Una adicional por partido",true)+
      metric("Tasa de acierto",rate(additional.accuracy),"Solo resultados finales")+
      metric("Balance simulado",units(additional.profit),"1 u. por selección liquidada")+
      metric("ROI simulado",rate(additional.roi),"No equivale a dinero ganado"),
    topChart:topGraph(info.timeline),
    extraChart:profitGraph(info.timeline),
    topFairEvidence:"Top 3: "+count(top.registered)+" archivadas, "+
      count(top.unresolved)+" pendientes, "+count(top.fairCount)+
      " simulaciones liquidadas. Precio hipotético = 1 / probabilidad original, "+
      "sin margen de bookmaker: la rentabilidad real sería desconocida.",
    combinedEvidence:"SIMULACIÓN MIXTA 3+1 · "+count(combined.financialCount)+
      " unidades simuladas ("+count(combined.topCount)+" Top 3 a cuota justa y "+
      count(combined.additionalCount)+" adicionales a cuota archivada). "+
      "Balance: "+units(combined.profit)+" · ROI: "+rate(combined.roi)+
      ". No equivale a un ROI real ni se compraron estas cuotas.",
    extraEvidence:"Resultados liquidados: "+count(additional.settled)+
      " · Cuotas orientativas sin prueba histórica: "+count(additional.indicativeCount)+
      " · Cuotas registradas por API: "+count(additional.observedCount)+
      " (liquidadas: "+count(additional.observedSettled)+"). "+
      "Balance de las cuotas API liquidadas: "+units(additional.observedProfit)+
      " · ROI hipotético solo API: "+rate(additional.observedRoi)+
      ". La liquidación deportiva es independiente de la acreditación del precio; no son apuestas ejecutadas.",
    autoAudit:automatedAudit(model,filters.league),
    leagueTable:leagueTable(info.byLeague,filters.league),
    ledger:ledger(info.rows.slice(0,limit)),
    count:count(info.rows.length)+" selecciones entre Top 3 y adicionales",
    hasMore:info.rows.length>limit,
    snapshot:info
  };
}
