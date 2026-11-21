/**
 * Football AI Lab · mobile-first home.
 * Only prospective archived Top3 and at most one frozen additional per fixture.
 * Never uses exploratory candidates or interprets an unresolved pick as a loss.
 */
import {numberOrNull, settled} from "./data.mjs";
import {performanceSnapshot} from "./performance.mjs";
import {additionalStatus} from "./additional_status.mjs";

const madrid=new Intl.DateTimeFormat("es-ES",{
  timeZone:"Europe/Madrid",day:"2-digit",month:"short",
  hour:"2-digit",minute:"2-digit"
});
const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));
const number=new Intl.NumberFormat("es-ES",{maximumFractionDigits:0});
const oddsFmt=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:3});
const pctFmt=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:0});
const date=s=>Number.isFinite(Date.parse(s||""))?
  madrid.format(new Date(s)):"Fecha sin confirmar";
const outcome=r=>settled(r)?String(r.resultado)==="1"?"Acierto":"Fallo":"Pendiente";

function additional(match){
  // Already-associated frozen rows; never pick an exploratory alternative.
  return (match.odds||[]).find(r=>{
    const p=numberOrNull(r.cuota_decimal);
    return r.id===match.id &&
      ["INDICATIVA_NO_VERIFICADA","OFRECIDA_API_REGISTRADA"].includes(r.tipo_cuota) &&
      p!==null && p>1.50 && p<=1000 &&
      Date.parse(r.archivado_utc||"")<Date.parse(r.fecha_utc||"");
  })||null;
}

export function homeSnapshot(model={},now=new Date()){
  const current=now.getTime();
  const future=(Array.isArray(model.futureMatches)?model.futureMatches:[])
    .filter(m=>m&&Number.isFinite(m.kickoff)&&m.kickoff>current)
    .sort((a,b)=>a.kickoff-b.kickoff);
  const recent=(Array.isArray(model.matches)?model.matches:[])
    .filter(m=>m&&Number.isFinite(m.kickoff)&&m.kickoff<=current &&
      [...(m.picks||[]),...(m.odds||[])].some(settled))
    .sort((a,b)=>b.kickoff-a.kickoff);
  const performance=performanceSnapshot(model,{},now);
  return {
    futureCount:future.length,
    next:future.slice(0,4),
    recent:recent.slice(0,3),
    top:performance.top,
    extra:performance.additional,
    updatedAt:model.updatedAt||null
  };
}

function matchCard(m,crest,now){
  const picks=(m.picks||[]).slice(0,3);
  const extra=additional(m);
  const price=extra?oddsFmt.format(Number(extra.cuota_decimal)):"";
  const allPicks=picks.length?picks.map((p,i)=>
    '<div class="home-pick"><span>'+(i+1)+'. '+escape(p.seleccion)+
    '</span><strong>'+ (numberOrNull(p.probabilidad)===null?"—":
      pctFmt.format(Number(p.probabilidad)))+'</strong></div>'
  ).join(""):'<p class="home-muted">Top 3 todavía no archivado.</p>';
  const status=extra?null:additionalStatus(m,now);
  const extraRow=extra?
    '<div class="home-extra"><div><span class="home-label">ADICIONAL +1,50</span>'+
    '<strong>'+escape(extra.seleccion)+'</strong></div>'+
    '<span class="home-odds"><small>CUOTA REGISTRADA</small><b>'+escape(price)+'</b></span></div>':
    '<div class="home-extra home-extra-empty '+escape(status?.style||"pending")+'">'+
    '<span><strong>'+escape(status?.label||"Sin adicional archivada")+'</strong>'+
    '<small>'+escape(status?.explanation||"No consta una cuota verificada.")+'</small></span></div>';
  return '<article class="home-fixture">'+
    '<div class="home-match-head"><span>'+escape(m.liga)+'</span>'+
    '<time>'+escape(date(m.fecha_utc))+'</time></div>'+
    '<div class="home-teams"><span>'+crest(m.liga,m.local,true)+
    '<strong>'+escape(m.local)+'</strong></span><b>VS</b><span>'+
    crest(m.liga,m.visitante,true)+'<strong>'+escape(m.visitante)+'</strong></span></div>'+
    extraRow+
    '<details class="home-pick-details"><summary>Ver Top 3 archivado ('+
    picks.length+')</summary><div>'+allPicks+'</div></details>'+
    '<button type="button" class="home-open" data-open-id="'+escape(m.id)+
    '">Abrir ficha del partido <span aria-hidden="true">›</span></button>'+
    '</article>';
}

function recentCard(m){
  const rows=[...(m.picks||[]).slice(0,3),...((additional(m)?[additional(m)]:[]))];
  const done=rows.filter(settled);
  const hits=done.filter(r=>String(r.resultado)==="1").length;
  return '<button type="button" class="home-recent-row" data-open-id="'+escape(m.id)+'">'+
    '<span><strong>'+escape(m.local)+' – '+escape(m.visitante)+'</strong>'+
    '<small>'+escape(m.liga)+' · '+escape(date(m.fecha_utc))+'</small></span>'+
    '<span class="home-recent-right"><b>'+hits+'/'+done.length+'</b>'+
    '<small>aciertos / resueltos</small></span></button>';
}

export function renderHomeView(model={},crest=()=>"",now=new Date()){
  const data=homeSnapshot(model,now);
  const top=data.top,extra=data.extra;
  const extraRate=extra.settled?pctFmt.format(extra.accuracy):"—";
  const stats=
    '<div class="home-stat"><span>PRÓXIMOS PARTIDOS</span><strong>'+number.format(data.futureCount)+'</strong><small>de las 6 ligas</small></div>'+
    '<div class="home-stat"><span>ADICIONALES PENDIENTES</span><strong>'+number.format(extra.unresolved)+'</strong><small>cuotas ya archivadas</small></div>'+
    '<div class="home-stat"><span>ACIERTOS ADICIONALES</span><strong>'+extraRate+'</strong><small>'+top.hits+'/'+top.settled+' aciertos Top 3</small></div>';
  return {
    stats,
    upcoming:data.next.length?data.next.map(m=>matchCard(m,crest,now)).join(""):
      '<p class="home-empty">No hay encuentros próximos publicados. Consulta Partidos o actualiza los datos.</p>',
    recent:data.recent.length?data.recent.map(recentCard).join(""):
      '<p class="home-empty">Todavía no hay resultados finales suficientes.</p>',
    updated:data.updatedAt?'Datos publicados: '+date(data.updatedAt):
      "Datos publicados: fecha no disponible",
    counts:{future:data.futureCount,extraPending:extra.unresolved,
      topSettled:top.settled,extraSettled:extra.settled}
  };
}
