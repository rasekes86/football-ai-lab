/**
 * Desglose diario y por competición del registro 3+1 ya auditado.
 * No genera pronósticos, no recalcula resultados y no añade mercados exploratorios.
 * Los importes son simulaciones: cuota justa del modelo para Top 3,
 * y cuota archivada (ofrecida, indicativa o teórica) para la adicional.
 */
import { LEAGUES } from "./data.mjs";

const dateParts=new Intl.DateTimeFormat("es-ES",{
  timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"
});
const humanDay=new Intl.DateTimeFormat("es-ES",{
  timeZone:"Europe/Madrid",weekday:"short",day:"numeric",month:"short",year:"numeric"
});
const nfmt=new Intl.NumberFormat("es-ES",{maximumFractionDigits:0});
const rfmt=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:1});
const ufmt=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2});
const escape=value=>String(value??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[c]);

export function madridDay(raw){
  const ms=Date.parse(raw||"");
  if(!Number.isFinite(ms))return null;
  const bits=Object.fromEntries(dateParts.formatToParts(new Date(ms))
    .filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
  return bits.year+"-"+bits.month+"-"+bits.day;
}
function settled(row){
  return row?.estado==="FINALIZADO" && ["0","1"].includes(String(row.resultado));
}
function summary(rows){
  const top={registered:0,settled:0,hits:0,losses:0,pending:0,priced:0,profit:0};
  const extra={registered:0,settled:0,hits:0,losses:0,pending:0,priced:0,profit:0};
  const games=new Set(),verifiedGames=new Set();
  for(const row of rows){
    if(!row||!row.id)continue;
    const target=row.group==="Top 3"?top:row.group==="Adicional +1,50"?extra:null;
    if(!target)continue;
    games.add(row.id);
    target.registered++;
    if(!settled(row)){target.pending++;continue;}
    verifiedGames.add(row.id);
    target.settled++;
    if(String(row.resultado)==="1")target.hits++;
    else target.losses++;
    // A recorded simulated return only exists when the relevant archived price
    // is valid. Do not silently replace missing returns with zero.
    if(row.return!==null&&row.return!==undefined&&Number.isFinite(Number(row.return))){
      target.priced++;
      target.profit+=Number(row.return);
    }
  }
  const finalize=x=>({...x,accuracy:x.settled?x.hits/x.settled:null,
    profit:x.priced?x.profit:null,roi:x.priced?x.profit/x.priced:null});
  const t=finalize(top),e=finalize(extra);
  const priced=t.priced+e.priced;
  const profit=priced?(t.profit??0)+(e.profit??0):null;
  return {top:t,additional:e,games:games.size,verifiedGames:verifiedGames.size,
    total:{registered:t.registered+e.registered,settled:t.settled+e.settled,
      hits:t.hits+e.hits,losses:t.losses+e.losses,
      pending:t.pending+e.pending,priced,profit,roi:priced?profit/priced:null,
      accuracy:t.settled+e.settled?(t.hits+e.hits)/(t.settled+e.settled):null}};
}
function groupBy(rows,keyFn){
  const groups=new Map();
  for(const row of rows){
    const key=keyFn(row);
    if(!key)continue;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(row);
  }
  return groups;
}
export function breakdownSnapshot(snapshot={}){
  const rows=(Array.isArray(snapshot.rows)?snapshot.rows:[])
    .filter(r=>r?.id&&r?.liga&&LEAGUES.includes(r.liga)&&madridDay(r.fecha_utc));
  const days=[...groupBy(rows,r=>madridDay(r.fecha_utc)).entries()]
    .sort(([a],[b])=>b.localeCompare(a))
    .map(([key,group])=>({key,...summary(group),
      leagues:LEAGUES.filter(l=>group.some(r=>r.liga===l))
        .map(name=>({name,...summary(group.filter(r=>r.liga===name))}))}));
  const leagues=LEAGUES.map(name=>{
    const own=rows.filter(r=>r.liga===name);
    return {name,...summary(own),
      days:[...groupBy(own,r=>madridDay(r.fecha_utc)).entries()]
        .sort(([a],[b])=>b.localeCompare(a))
        .map(([key,group])=>({key,...summary(group)}))};
  });
  return {days,leagues};
}
const count=x=>nfmt.format(x||0);
const rate=x=>x===null||x===undefined?"—":rfmt.format(x);
const units=x=>x===null||x===undefined?"—":
  (x>0?"+":x<0?"−":"")+ufmt.format(Math.abs(x))+" u.";
const date=key=>humanDay.format(new Date(key+"T12:00:00Z"));
function groupFigures(label,stat,note){
  return '<div class="breakdown-figure">'+
    '<span class="breakdown-figure-label">'+escape(label)+'</span>'+
    '<strong>'+count(stat.hits)+' / '+count(stat.settled)+
      ' <small>'+escape(rate(stat.accuracy))+'</small></strong>'+
    '<span class="breakdown-progress" aria-hidden="true"><i style="width:'+
      (stat.accuracy===null?0:Math.max(0,Math.min(100,stat.accuracy*100))).toFixed(1)+'%"></i></span>'+
    '<small>'+count(stat.losses)+' fallos · '+count(stat.pending)+' pendientes</small>'+
    '<small>'+escape(note)+' · '+escape(units(stat.profit))+'</small>'+
    '</div>';
}
function compact(group,label){
  return '<div class="breakdown-subrow"><span>'+escape(label)+'</span>'+
    '<span>Top 3 <strong>'+count(group.top.hits)+'/'+count(group.top.settled)+'</strong> · '+
      'Extra <strong>'+count(group.additional.hits)+'/'+count(group.additional.settled)+'</strong></span>'+
    '<b>'+escape(units(group.total.profit))+'</b></div>';
}
function card(title,subtitle,stats,detail){
  return '<article class="breakdown-card">'+
    '<div class="breakdown-card-head"><div><strong>'+escape(title)+'</strong>'+
      '<small>'+escape(subtitle)+'</small></div>'+
      '<span class="breakdown-balance '+(stats.total.profit===null?"neutral":stats.total.profit<0?"negative":"positive")+'">'+
      escape(units(stats.total.profit))+'</span></div>'+
    '<div class="breakdown-card-figures">'+
      groupFigures("TOP 3 ORIGINAL",stats.top,"Cuota justa simulada")+
      groupFigures("ADICIONAL +1,50",stats.additional,"Cuota archivada simulada")+
    '</div><div class="breakdown-card-foot"><span>Conjunto sin duplicados: <strong>'+
      count(stats.total.hits)+' / '+count(stats.total.settled)+'</strong> ('+
      escape(rate(stats.total.accuracy))+')</span><span>ROI simulado: <strong>'+
      escape(rate(stats.total.roi))+'</strong></span></div>'+
    (detail?'<details class="breakdown-details"><summary>'+escape(detail.label)+
      ' <span aria-hidden="true">⌄</span></summary>'+
      '<div class="breakdown-detail-rows">'+detail.html+'</div></details>':"")+
    '</article>';
}
export function renderPerformanceBreakdown(snapshot={},options={}){
  const data=breakdownSnapshot(snapshot);
  const max=Math.max(1,Math.min(365,Number(options.dayLimit)||12));
  const filteredLeagues=data.leagues.filter(x=>!options.league||x.name===options.league);
  const days=data.days.slice(0,max).map(d=>card(
    date(d.key),
    count(d.verifiedGames)+" partidos con pronósticos verificados · "+count(d.games)+" registrados",
    d,
    d.leagues.length?{label:"Ver desglose por liga",html:d.leagues.map(l=>compact(l,l.name)).join("")}:null
  )).join("");
  const leagues=filteredLeagues.map(l=>card(
    l.name,
    count(l.verifiedGames)+" partidos con pronósticos verificados · "+count(l.games)+" registrados",
    l,
    l.days.length?{label:"Ver evolución diaria",html:l.days.slice(0,30)
      .map(d=>compact(d,date(d.key))).join("")}:null
  )).join("");
  return {
    days:days||'<div class="breakdown-empty">No hay selecciones archivadas en este periodo. Los pendientes no se contabilizan como fallos.</div>',
    leagues:leagues||'<div class="breakdown-empty">No hay competiciones para este filtro.</div>',
    dayCount:data.days.length,hasMore:data.days.length>max
  };
}
