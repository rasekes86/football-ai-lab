/**
 * Football AI Lab · 3+1 partido · mobile-first, progresivo y verificable.
 *
 * Exclusively renders the TOP THREE frozen picks and the first eligible
 * separately archived additional selection. No recalculated forecasts or
 * odds may become an archived pick, and unknown sporting outcomes stay open.
 */
import {numberOrNull,settled} from "./data.mjs";

const timeMadrid=new Intl.DateTimeFormat("es-ES",{
  timeZone:"Europe/Madrid",day:"2-digit",month:"short",year:"numeric",
  hour:"2-digit",minute:"2-digit"
});
const priceFmt=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:3});
const pctFmt=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:1});
const balanceFmt=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2});

const escape=s=>String(s??"").replace(/[&<>"']/g,ch=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[ch]);
const niceDate=raw=>Number.isFinite(Date.parse(raw||""))?
  timeMadrid.format(new Date(raw)):"Fecha sin publicar";
const isBeforeKickoff=row=>{
  const saved=Date.parse(row?.archivado_utc||"");
  const kickoff=Date.parse(row?.fecha_utc||"");
  return Number.isFinite(saved)&&Number.isFinite(kickoff)&&saved<kickoff;
};
const validPrice=row=>{
  const price=numberOrNull(row?.cuota_decimal);
  return price!==null&&price>1.50&&price<=1000;
};
const ALLOWED_TYPES=new Set(["INDICATIVA_NO_VERIFICADA","OFRECIDA_API_REGISTRADA"]);

export function archivedAdditional(match){
  if(!match?.id)return null;
  const possible=(match.odds||[]).filter(row=>
    row&&row.id===match.id&&row.clave&&isBeforeKickoff(row)&&
    ALLOWED_TYPES.has(row.tipo_cuota)&&validPrice(row));
  // Earliest recorded valid selection is immutable; never rank on postmatch result.
  return possible.sort((a,b)=>Date.parse(a.archivado_utc)-Date.parse(b.archivado_utc)||
    String(a.clave).localeCompare(String(b.clave),"es"))[0]||null;
}

export function detailSnapshot(match,now=new Date()){
  const picks=(Array.isArray(match?.picks)?match.picks:[]).slice(0,3);
  const extra=archivedAdditional(match);
  const done=picks.filter(settled);
  const wins=done.filter(p=>String(p.resultado)==="1").length;
  const future=Date.parse(match?.fecha_utc||"")>now.getTime();
  const follow=match?.followup||{};
  const score=follow.estado==="FINALIZADO"&&
    /^\d{1,2}$/.test(String(follow.resultado_local??""))&&
    /^\d{1,2}$/.test(String(follow.resultado_visitante??""))?
    [String(follow.resultado_local),String(follow.resultado_visitante)]:null;
  return {picks,extra,finished:done.length,wins,notFinished:picks.length-done.length,
    future,score,extraFinished:Boolean(extra&&settled(extra))};
}

function outcome(row){
  if(settled(row))return String(row.resultado)==="1"?
    {label:"Acierto confirmado",style:"win"}:{label:"Fallo confirmado",style:"loss"};
  if(row?.estado==="RESULTADO_NO_DISPONIBLE")return {label:"Marcador sin verificar",style:"missing"};
  if(row?.estado==="ESTADISTICA_NO_DISPONIBLE")return {label:"Estadística sin verificar",style:"missing"};
  return {label:"Pendiente",style:"pending"};
}

function sourceLink(source){
  const text=String(source||"");
  if(/^https:\/\/(site\.api\.espn\.com|www\.laliga\.com|www\.football-data\.co\.uk)\//.test(text)){
    const label=text.includes("espn")?"ESPN":text.includes("laliga")?"LaLiga":"Football-Data";
    return '<a href="'+escape(text)+'" target="_blank" rel="noopener noreferrer">'+label+' · fuente ↗</a>';
  }
  return '<span>'+escape(text)+'</span>';
}
function detailPick(row,i,context){
  const status=outcome(row);
  const probability=numberOrNull(row.probabilidad);
  const fair=numberOrNull(row.cuota_justa);
  const detail=context?.selecciones?.find(x=>x.clave===row.clave)||null;
  const extras=[];
  if(row.nivel||row.origen)extras.push('<p>'+escape(row.nivel||row.origen)+'</p>');
  if(fair!==null)extras.push('<p>Cuota justa del modelo: <strong>'+escape(priceFmt.format(fair))+
    '</strong> · No es una cuota ofrecida por una casa.</p>');
  if(settled(row)&&row.valor_real!==undefined&&row.valor_real!=="")extras.push(
    '<p>Valor final contrastado: <strong>'+escape(row.valor_real)+'</strong></p>');
  if(detail?.explicacion)extras.push('<p class="match-v2-explanation">'+escape(detail.explicacion)+'</p>');
  if(Array.isArray(detail?.fuentes)&&detail.fuentes.length)extras.push(
    '<p class="match-v2-evidence">'+detail.fuentes.map(sourceLink).join(" · ")+'</p>');
  return '<details class="match-v2-pick '+status.style+'">'+
    '<summary><span class="match-v2-pick-index">'+(i+1)+'</span>'+
    '<span class="match-v2-pick-main"><small>'+escape(row.mercado||"Mercado archivado")+'</small>'+
    '<strong>'+escape(row.seleccion||"Sin selección")+'</strong>'+
    '<span class="match-v2-pick-status '+status.style+'">'+escape(status.label)+'</span></span>'+
    '<span class="match-v2-pick-right"><small>ESTIMACIÓN</small><b>'+
    (probability!==null?escape(pctFmt.format(probability)):"—")+
    '</b><span class="match-v2-chevron" aria-hidden="true">⌄</span></span></summary>'+
    '<div class="match-v2-pick-body">'+
    (extras.length?extras.join(""):'<p>Sin información técnica adicional archivada.</p>')+
    '</div></details>';
}

function detailAdditional(row){
  if(!row)return '<div class="match-v2-no-extra"><strong>Sin adicional archivada</strong>'+
    '<span>No se inventa una cuota ni una selección si el filtro +1,50 no encontró una válida.</span></div>';
  const price=numberOrNull(row.cuota_decimal);
  const stat=outcome(row);
  const api=row.tipo_cuota==="OFRECIDA_API_REGISTRADA";
  const captured=row.fecha_cuota_utc&&Number.isFinite(Date.parse(row.fecha_cuota_utc))?
    niceDate(row.fecha_cuota_utc):"Sin hora de captura contrastada";
  const provenance=[
    row.bookmaker?escape(row.bookmaker):"",
    row.proveedor_cuota?escape(row.proveedor_cuota):""
  ].filter(Boolean).join(" · ");
  const simulated=settled(row)?numberOrNull(row.retorno_simulado_unidad):null;
  return '<article class="match-v2-extra">'+
    '<div class="match-v2-extra-label"><span>SELECCIÓN ADICIONAL +1,50</span>'+
    '<span class="match-v2-pick-status '+stat.style+'">'+escape(stat.label)+'</span></div>'+
    '<div class="match-v2-extra-main"><div><small>'+escape(row.mercado||"Mercado")+'</small>'+
    '<strong>'+escape(row.seleccion||"Selección archivada")+'</strong></div>'+
    '<div class="match-v2-price"><small>'+(api?"CUOTA OBSERVADA":"CUOTA INDICATIVA")+
    '</small><b>'+escape(priceFmt.format(price))+'</b></div></div>'+
    '<div class="match-v2-extra-origin">'+(api?
      'Cuota registrada antes del inicio; no implica una apuesta ejecutada.':
      'Referencia no acreditada por bookmaker; solo simulación.')+
    '</div>'+
    '<details class="match-v2-extra-details"><summary>Origen y seguimiento <span aria-hidden="true">⌄</span></summary>'+
    '<div><p>'+ (provenance||"Casa y proveedor no identificados")+'</p>'+
    '<p>Captura: '+escape(captured)+
    (row.marca_tiempo_tipo==="CAPTURA_NO_ACTUALIZACION"?
       ' · No es la hora de cambio en la casa.':"")+'</p>'+
    (simulated!==null?'<p>Balance hipotético de 1 unidad: <strong>'+
       (simulated>0?"+":"")+escape(balanceFmt.format(simulated))+' u.</strong></p>':"")+
    '</div></details></article>';
}

function verifiedStats(detail){
  if(!detail||typeof detail!=="object")return "";
  const metrics=[
    ["shots","Tiros totales"],
    ["on_target","Tiros a puerta"],
    ["corners","Córners"],
    ["yellow","Amarillas"],
    ["red","Rojas"]
  ];
  const body=metrics.map(([key,label])=>{
    const row=detail.estadisticas?.[key];
    if(!row)return "";
    const display=value=>value===null||value===undefined||value===""?"—":escape(value);
    return '<div class="match-v2-stat-row"><strong>'+escape(row.nombre||label)+'</strong>'+
      '<span>'+display(row.local)+'</span><b>'+display(row.total)+'</b>'+
      '<span>'+display(row.visitante)+'</span></div>'+
      (Array.isArray(row.fuentes)&&row.fuentes.length?
        '<div class="match-v2-stat-sources">'+row.fuentes.map(sourceLink).join(" · ")+'</div>':"");
  }).join("");
  if(!body)return "";
  const verify=detail.marcador?
    '<p>Marcador publicado: '+escape(detail.marcador)+
    (detail.fuente_marcador?' · '+sourceLink(detail.fuente_marcador):"")+'</p>':"";
  return '<details class="match-v2-accordion"><summary><span>'+
    '<strong>Estadísticas finales</strong><small>Datos disponibles y fuentes</small>'+
    '</span><span aria-hidden="true">⌄</span></summary>'+
    '<div class="match-v2-stats"><div class="match-v2-stat-head">'+
    '<span>MÉTRICA</span><span>LOCAL</span><span>TOTAL</span><span>VISITANTE</span></div>'+
    body+'</div><p class="match-v2-footnote">«—» significa sin dato, no cero. '+verify+
    '</p></details>';
}
function modelInfo(match){
  const f=match.historicalForecast||match.forecast;
  if(!f)return "";
  const fields=[["Local",f.prob_local],["Empate",f.prob_empate],["Visitante",f.prob_visitante]]
    .filter(([,value])=>numberOrNull(value)!==null);
  if(!fields.length)return "";
  const original=Boolean(match.historicalForecast);
  return '<details class="match-v2-accordion"><summary><span>'+
    '<strong>Pronóstico 1X2 del modelo</strong><small>'+
    (original?"Referencia histórica archivada":"Estimaciones del análisis publicado")+
    '</small></span><span aria-hidden="true">⌄</span></summary>'+
    '<div class="match-v2-model-grid">'+fields.map(([name,p])=>'<div><small>'+
      escape(name)+'</small><b>'+escape(pctFmt.format(Number(p)))+'</b></div>').join("")+'</div>'+
    '<p class="match-v2-footnote">Modelo: '+escape(f.modelo||"Experimental")+
    ' · Son estimaciones, no resultados ni cuotas reales.</p></details>';
}

export function renderMatchDetail(match,crest=()=>"",now=new Date()){
  if(!match?.id)return "";
  const d=detailSnapshot(match,now);
  const mid=d.score?'<b class="match-v2-result">'+d.score.join(" – ")+'</b>':
    '<b class="match-v2-versus">VS</b>';
  const scoreLabel=d.score?"Resultado final publicado":
    d.future?"Pendiente de disputar":"Sin marcador final verificado";
  const kpi=(label,value,note)=>'<div class="match-v2-kpi"><span>'+label+
    '</span><strong>'+value+'</strong><small>'+note+'</small></div>';
  return '<div class="match-v2">'+
    '<header class="match-v2-hero"><div class="match-v2-context"><span>'+
    escape(match.liga||"Competición")+'</span><time>'+escape(niceDate(match.fecha_utc))+'</time></div>'+
    '<div class="match-v2-teams"><div class="match-v2-team">'+
    crest(match.liga,match.local)+'<strong>'+escape(match.local)+'</strong></div>'+
    '<div class="match-v2-center">'+mid+'<small>'+escape(scoreLabel)+'</small></div>'+
    '<div class="match-v2-team">'+crest(match.liga,match.visitante)+
    '<strong>'+escape(match.visitante)+'</strong></div></div></header>'+
    '<div class="match-v2-kpis">'+
    kpi("TOP 3 · ACERTADAS",String(d.wins)+' / '+String(d.finished),
      d.notFinished+' sin liquidar')+
    kpi("ADICIONAL +1,50",d.extra?escape(outcome(d.extra).label):"Sin selección",
      d.extra?(d.extraFinished?"Resultado deportivo confirmado":"Pendiente de verificación"):
        "No archivada")+'</div>'+
    '<section class="match-v2-section"><div class="match-v2-section-heading">'+
    '<div><span>01 · PREDICCIONES CONGELADAS</span><h3>Top 3 del partido</h3></div>'+
    '<small>'+d.picks.length+' seleccionadas</small></div>'+
    (d.picks.length?d.picks.map((p,i)=>detailPick(p,i,match.breakdown)).join(""):
      '<div class="match-v2-empty">Todavía no hay un Top 3 archivado para este partido.</div>')+
    '</section><section class="match-v2-section"><div class="match-v2-section-heading">'+
    '<div><span>02 · CUOTA PREPARTIDO</span><h3>La adicional</h3></div></div>'+
    detailAdditional(d.extra)+'</section>'+
    '<section class="match-v2-section match-v2-advanced">'+
    '<div class="match-v2-section-heading"><div><span>03 · SOLO SI QUIERES PROFUNDIZAR</span>'+
    '<h3>Datos y metodología</h3></div></div>'+
    verifiedStats(match.breakdown)+modelInfo(match)+
    '<details class="match-v2-accordion"><summary><span>'+
    '<strong>Cómo se comprueban los pronósticos</strong>'+
    '<small>Fuentes, aciertos y cuotas</small></span><span aria-hidden="true">⌄</span></summary>'+
    '<div class="match-v2-method"><p>Solo las tres primeras selecciones archivadas y una adicional anterior al partido. '+
    'Un resultado pendiente o sin estadísticas no cuenta como fallo.</p>'+
    '<p>Las cuotas indicativas no son ofertas verificadas. '+
    'El balance de 1 unidad, cuando existe, es una simulación sin dinero apostado.</p>'+
    '<a href="https://github.com/rasekes86/football-ai-lab/tree/main/output" target="_blank" rel="noopener noreferrer">'+
    'Consultar datos publicados ↗</a></div></details>'+
    '</section></div>';
}
