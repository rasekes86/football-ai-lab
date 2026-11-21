/**
 * Results tab V2 · compact mobile readout strictly from the frozen 3+1 ledger.
 * This module does not settle predictions, select bets or calculate new prices.
 */
const fmt=new Intl.NumberFormat("es-ES",{maximumFractionDigits:0});
const percent=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:1});
const decimal=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2});
const oddsFmt=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:3});
const dayFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",day:"2-digit",month:"short",year:"numeric"});
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const date=v=>Number.isFinite(Date.parse(v||""))?dayFmt.format(new Date(v)):"Fecha desconocida";
const result=r=>r?.estado==="FINALIZADO"&&["0","1"].includes(String(r.resultado))?
  (String(r.resultado)==="1"?"win":"loss"):"pending";
// Visual status is independent of the bookmaker quote and of match timing.
const visualState=r=>{
  const confirmed=result(r);
  if(confirmed!=="pending")return confirmed;
  return ["ESTADISTICA_NO_DISPONIBLE","RESULTADO_NO_DISPONIBLE"].includes(r?.estado)?
    "missing":"pending";
};
const stateSymbol=r=>{
  const type=visualState(r);
  return type==="win"?"✓":type==="loss"?"×":type==="missing"?"!":"◷";
};
const statusBadge=(r,base="results-status")=>
  '<span class="'+base+' '+visualState(r)+'"><span class="results-status-icon" aria-hidden="true">'+
  stateSymbol(r)+'</span>'+esc(stateLabel(r))+'</span>';
const stateLabel=r=>{
  const s=result(r);
  if(s==="win")return "Acierto confirmado";
  if(s==="loss")return "Fallo confirmado";
  if(r?.estado==="ESTADISTICA_NO_DISPONIBLE")return "Falta estadística";
  if(r?.estado==="RESULTADO_NO_DISPONIBLE")return "Falta marcador";
  return "Pendiente";
};
const units=n=>n===null||n===undefined?"—":
  (n>0?"+":n<0?"−":"")+decimal.format(Math.abs(n))+" u.";
const accuracy=n=>n===null||n===undefined?"—":percent.format(n);

/** Convert the audited snapshot into one summary per fixture.
 * Only fixtures with >=1 final 3+1 sporting outcome enter Recent.
 */
export function recentResultGroups(info={},matches=[],limit=6){
  const map=new Map();
  for(const row of info.rows||[]){
    if(!row?.id||!row?.fecha_utc)continue;
    if(!map.has(row.id))map.set(row.id,{
      id:row.id,league:row.liga,kickoff:row.fecha_utc,
      home:row.local,away:row.visitante,top:[],extra:null
    });
    const group=map.get(row.id);
    if(row.group==="Top 3"){
      if(group.top.length<3)group.top.push(row);
    }else if(row.group==="Adicional +1,50"&&!group.extra){
      group.extra=row;
    }
  }
  const matchMap=new Map((Array.isArray(matches)?matches:[])
    .filter(m=>m?.id).map(m=>[m.id,m]));
  const recent=[...map.values()].filter(group=>
    [...group.top,...(group.extra?[group.extra]:[])].some(r=>result(r)!=="pending"));
  recent.sort((a,b)=>Date.parse(b.kickoff)-Date.parse(a.kickoff)||
    a.id.localeCompare(b.id,"es"));
  const max=Math.max(1,Math.min(60,Number(limit)||6));
  return {total:recent.length,
    shown:recent.slice(0,max).map(group=>({
      ...group,match:matchMap.get(group.id)||null
    })),
    hasMore:recent.length>max};
}
function meter(label,hits,settled){
  if(!settled)return '<div class="results-v2-meter-empty">Sin resultados suficientes todavía.</div>';
  const winPct=Math.max(0,Math.min(100,100*hits/settled));
  const lossPct=100-winPct;
  return '<div class="results-v2-meter" aria-label="'+esc(label)+': '+
    fmt.format(hits)+' aciertos y '+fmt.format(settled-hits)+' fallos confirmados">'+
    '<span class="results-v2-win" style="width:'+winPct.toFixed(1)+'%"></span>'+
    '<span class="results-v2-loss" style="width:'+lossPct.toFixed(1)+'%"></span></div>'+
    '<div class="results-v2-meter-legend"><span>'+fmt.format(hits)+' aciertos</span>'+
    '<span>'+fmt.format(settled-hits)+' fallos</span></div>';
}
function scoreboard(title,n,kind){
  return '<article class="results-v2-score results-v2-'+kind+'">'+
    '<div class="results-v2-score-title"><span>'+esc(title)+'</span>'+
    '<strong>'+fmt.format(n.hits)+' <small>/ '+fmt.format(n.settled)+'</small></strong></div>'+
    '<div class="results-v2-rate"><strong>'+accuracy(n.accuracy)+'</strong>'+
    '<span>de acierto entre las liquidadas</span></div>'+
    meter(title,n.hits,n.settled)+
    '<div class="results-v2-pending">'+fmt.format(n.unresolved)+
    ' pendientes de liquidar · no son fallos</div></article>';
}
function score(match){
  const x=match?.followup;
  if(x?.estado!=="FINALIZADO")return "";
  const h=String(x.resultado_local??"");
  const a=String(x.resultado_visitante??"");
  return /^\d{1,2}$/.test(h)&&/^\d{1,2}$/.test(a)?h+" – "+a:"";
}
function rowIcon(r){
  return stateSymbol(r);
}
function pickLine(r){
  const s=visualState(r);
  const quoted=r.group==="Top 3"&&r.price!==null&&Number.isFinite(r.price);
  const fairInfo=quoted?'<small class="results-v2-fair-note">Cuota justa simulada '+
    oddsFmt.format(r.price)+(r.return!==null?' · '+esc(units(r.return)):' · sin liquidar')+
    '</small>':"";
  return '<div class="results-v2-pick-line"><span class="results-v2-pick-icon '+s+
    '" aria-hidden="true">'+rowIcon(r)+'</span><span class="results-v2-pick-text">'+
    esc(r.seleccion||"Selección")+fairInfo+'</span>'+statusBadge(r)+'</div>';
}
function fixture(group){
  const resolved=group.top.filter(r=>result(r)!=="pending");
  const wins=resolved.filter(r=>result(r)==="win").length;
  const extra=group.extra;
  const hasExtra=Boolean(extra);
  const scoreText=score(group.match);
  const pricedTop=group.top.filter(r=>r.return!==null);
  const topProfit=pricedTop.reduce((sum,r)=>sum+r.return,0);
  const extraType=extra?.tipo_cuota==="OFRECIDA_API_REGISTRADA"?
    "Cuota API observada":extra?.tipo_cuota==="CUOTA_JUSTA_TEORICA_NO_OFRECIDA"?
    "Cuota justa teórica · NO ofrecida":"Cuota orientativa";
  const odd=hasExtra&&Number.isFinite(Number(extra.price))?
    oddsFmt.format(Number(extra.price)):"";
  return '<article class="results-v2-fixture">'+
    '<div class="results-v2-fixture-meta"><span>'+esc(group.league||"Liga")+'</span>'+
    '<time>'+esc(date(group.kickoff))+'</time></div>'+
    '<div class="results-v2-fixture-title"><strong>'+esc(group.home||"Local")+
    ' – '+esc(group.away||"Visitante")+'</strong>'+
    (scoreText?'<b>'+esc(scoreText)+'</b>':'')+'</div>'+
    '<div class="results-v2-groups"><div><span>'+(extra?.promotedTop?'TOP 2 · COINCIDE CON ADICIONAL':'TOP 3')+'</span>'+
    '<strong>'+fmt.format(wins)+' aciertos / '+fmt.format(resolved.length)+' resueltos</strong>'+
    '<small>'+fmt.format(group.top.length-resolved.length)+' sin liquidar</small>'+
    (pricedTop.length?'<small>Balance cuota justa · '+esc(units(topProfit))+
      ' ('+fmt.format(pricedTop.length)+' verificadas)</small>':"")+'</div>'+
    '<div class="results-v2-fixture-extra '+(extra?visualState(extra):"pending")+'"><span>ADICIONAL +1,50</span>'+
    (hasExtra?
      '<small class="results-v2-fixture-market">'+esc(extra.mercado||"Mercado")+'</small>'+
      '<strong class="results-v2-fixture-selection">'+esc(extra.seleccion||"Selección no publicada")+'</strong>'+
      '<small>'+esc(extraType)+' · cuota '+esc(odd)+'</small>':
      '<strong>Sin selección archivada</strong>')+
    (extra?statusBadge(extra):'<small class="results-v2-no-extra">No hay selección que verificar</small>')+
    '</div></div>'+
    '<details class="results-v2-fixture-details"><summary>Ver selecciones'+
    '<span aria-hidden="true">⌄</span></summary><div>'+
    group.top.map(pickLine).join("")+
    (extra?'<div class="results-v2-detail-label">ADICIONAL</div>'+pickLine(extra):"")+
    '</div></details>'+
    '<button class="results-v2-open" type="button" data-open-id="'+esc(group.id)+
    '">Abrir ficha del partido <span aria-hidden="true">›</span></button></article>';
}

/**
 * Registered +1.50 selections, including games that have not kicked off.
 * Uses only the one-additional-per-fixture rows already audited by
 * performanceSnapshot; does not promote an exploratory market to a pick.
 */
export function archivedAdditionalCards(info={},limit=8,now=new Date()){
  const current=now.getTime();
  const picks=(info.rows||[]).filter(r=>r?.group==="Adicional +1,50"&&r.id);
  const ordered=[...picks].sort((a,b)=>{
    const ak=Date.parse(a.fecha_utc||""),bk=Date.parse(b.fecha_utc||"");
    const af=Number.isFinite(ak)&&ak>current,bf=Number.isFinite(bk)&&bk>current;
    if(af!==bf)return af?-1:1;
    const ap=result(a)==="pending"&&af, bp=result(b)==="pending"&&bf;
    if(ap!==bp)return ap?-1:1;
    return af?(ak-bk):(bk-ak);
  });
  const max=Math.max(1,Math.min(100,Number(limit)||8));
  const html=ordered.slice(0,max).map(row=>{
    const p=Number.isFinite(Number(row.price))&&Number(row.price)>1.5?
      oddsFmt.format(Number(row.price)):"—";
    const isApi=row.tipo_cuota==="OFRECIDA_API_REGISTRADA";
    const isTheoretical=row.tipo_cuota==="CUOTA_JUSTA_TEORICA_NO_OFRECIDA";
    const label=visualState(row);
    return '<article class="results-v2-additional-card '+label+'">'+
      '<div class="results-v2-additional-meta"><span>'+esc(row.liga||"Competición")+
      '</span><time>'+esc(date(row.fecha_utc))+'</time></div>'+
      '<div class="results-v2-additional-teams">'+esc(row.local||"Local")+
      ' – '+esc(row.visitante||"Visitante")+'</div>'+
      '<div class="results-v2-additional-choice"><div><small>'+esc(row.mercado||"Mercado archivado")+
      '</small><strong>'+esc(row.seleccion||"Selección no publicada")+'</strong></div>'+
      '<div class="results-v2-additional-quote"><small>'+(isTheoretical?"CUOTA JUSTA TEÓRICA":isApi?"CUOTA API":"CUOTA INDICATIVA")+
      '</small><b>'+esc(p)+'</b></div></div>'+
      '<div class="results-v2-additional-bottom">'+statusBadge(row,"results-v2-additional-outcome results-status")+
      '<button type="button" data-open-id="'+esc(row.id)+'">Ver ficha <span aria-hidden="true">›</span></button></div>'+
      '</article>';
  }).join("");
  return {
    html:html||'<div class="results-v2-empty">No hay adicionales archivadas con estos filtros. Si no se encontró cuota válida, no se ha creado ninguna selección.</div>',
    total:ordered.length,
    hasMore:ordered.length>max
  };
}

export function renderResultsMobile(info={},matches=[],limit=6,additionalLimit=8,now=new Date()){
  const top=info.top||{hits:0,settled:0,unresolved:0,accuracy:null};
  const extra=info.additional||{hits:0,settled:0,unresolved:0,accuracy:null,
    profit:null,indicativeSettled:0,observedSettled:0};
  const recent=recentResultGroups(info,matches,limit);
  const additionalCards=archivedAdditionalCards(info,additionalLimit,now);
  const combined=info.combined||{profit:null,roi:null,financialCount:0};
  const balance='<div class="results-v2-balance results-v2-balance-3plus1">'+
    '<div class="results-v2-balance-line"><span>TOP 3 · CUOTA JUSTA SIMULADA</span>'+
    '<strong>'+esc(units(top.fairProfit??null))+'</strong>'+
    '<small>ROI: '+esc(accuracy(top.fairRoi??null))+
    ' · '+fmt.format(top.fairCount||0)+' resultados a 1 u.</small></div>'+
    '<div class="results-v2-balance-line"><span>ADICIONALES · CUOTAS ARCHIVADAS</span>'+
    '<strong>'+esc(units(extra.profit))+'</strong>'+
    '<small>ROI: '+esc(accuracy(extra.roi??null))+' · '+
    fmt.format(extra.observedSettled||0)+' cuotas API liquidadas · '+
    fmt.format(extra.indicativeSettled||0)+' cuotas indicativas liquidadas</small></div>'+
    '<div class="results-v2-balance-line combined"><span>CONJUNTO 3+1 / 2+1 · SIN DUPLICADOS</span>'+
    '<strong>'+esc(units(combined.profit))+'</strong>'+
    '<small>ROI simulado: '+esc(accuracy(combined.roi))+
    ' · '+fmt.format(combined.financialCount||0)+' unidades liquidadas</small></div>'+
    '<p class="results-v2-balance-warning">El Top 3 y algunas cuartas selecciones utilizan cuota justa matemática 1/probabilidad NO ofrecida. Las adicionales con precio real se identifican como API. Todos los balances son simulaciones, no rentabilidad demostrada.</p></div>';
  return {
    scorecards:scoreboard("TOP 3 ORIGINAL",top,"top")+
      scoreboard("UNA ADICIONAL +1,50",extra,"extra"),
    balance,
    additionalCards:additionalCards.html,
    additionalCount:additionalCards.total,
    additionalHasMore:additionalCards.hasMore,
    recent:recent.shown.length?recent.shown.map(fixture).join(""):
      '<div class="results-v2-empty">Todavía no hay partidos con selecciones 3+1 liquidadas '+
      'en este periodo. Los pendientes no son fallos.</div>',
    recentCount:recent.total,
    hasMore:recent.hasMore
  };
}
