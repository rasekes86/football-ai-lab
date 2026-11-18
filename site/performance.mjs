/**
 * Football AI Lab · Scorecard of actually archived selections only.
 *
 * Strict perimeter:
 *  - Top 3: first three original frozen selections per game; never candidates
 *    from exploratory, market forecast, or post-hoc calculations.
 *  - Additional: first unique pre-match frozen selection >1.50 per fixture.
 *  - The Top 3 may have a distinctly labeled FAIR-ODDS SIMULATION based
 *    only on the original, pre-match model probability: 1 / p.
 *    Such prices are NOT bookmaker quotes and cannot prove real-world ROI.
 *  - Original Top 3 selections, their probabilities and results stay fixed.
 *  - No pending/missing outcomes are treated as losing bets.
 *  - Indicative quoted prices remain a separate hypothetical scenario.
 */
import { LEAGUES, numberOrNull, settled } from "./data.mjs";

export const PERFORMANCE_RANGES = Object.freeze([
  {value:"all",label:"Todo el histórico"},
  {value:"30",label:"Últimos 30 días"},
  {value:"90",label:"Últimos 90 días"},
  {value:"365",label:"Últimos 365 días"}
]);

export const PERFORMANCE_GROUPS = Object.freeze([
  {value:"week",label:"Por semana"},
  {value:"month",label:"Por mes"}
]);

const EXPLICIT_TYPES = new Set(["INDICATIVA_NO_VERIFICADA","OFRECIDA_API_REGISTRADA"]);
const zoned = new Intl.DateTimeFormat("es-ES", {
  timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"
});
function parsedDate(raw){
  const ms=Date.parse(raw||"");
  return Number.isFinite(ms)?ms:null;
}
function localDay(raw){
  const ms=typeof raw==="number"?raw:parsedDate(raw);
  if(ms===null)return null;
  const bits=Object.fromEntries(zoned.formatToParts(new Date(ms))
    .filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
  return bits.year+"-"+bits.month+"-"+bits.day;
}
function bucketOf(ms,granularity){
  const day=localDay(ms);
  if(!day)return null;
  if(granularity==="month")return day.slice(0,7);
  const utc=new Date(day+"T00:00:00Z");
  utc.setUTCDate(utc.getUTCDate()-(utc.getUTCDay()+6)%7);
  return utc.toISOString().slice(0,10);
}
function permitted(row){
  if(!row?.id||!row?.clave||!row?.liga||!LEAGUES.includes(row.liga))return false;
  const saved=parsedDate(row.archivado_utc),kick=parsedDate(row.fecha_utc);
  return saved!==null&&kick!==null&&saved<kick;
}
function inScope(row,now,filters){
  if(filters.league&&row.liga!==filters.league)return false;
  const range=String(filters.range||"all");
  if(range==="all")return true;
  const span=Number(range);
  if(![30,90,365].includes(span))return true;
  const kick=parsedDate(row.fecha_utc);
  const anchor=now.getTime();
  return kick!==null&&kick<=anchor&&kick>=anchor-span*86400000;
}
function distinctTop3(rows){
  const byMatch=new Map();
  let invalid=0,duplicates=0,extra=0;
  for(const row of rows||[]){
    if(!permitted(row)){invalid++;continue;}
    if(!byMatch.has(row.id))byMatch.set(row.id,{rows:[],keys:new Set()});
    const group=byMatch.get(row.id);
    if(group.keys.has(row.clave)){duplicates++;continue;}
    group.keys.add(row.clave);
    group.rows.push(row);
  }
  const picks=[];
  for(const group of byMatch.values()){
    // Original CSV registration order, never ranked from recalculated probs.
    picks.push(...group.rows.slice(0,3));
    extra+=Math.max(0,group.rows.length-3);
  }
  return {picks,invalid,duplicates,extra};
}
function distinctAdditional(rows){
  const byMatch=new Map();
  let invalid=0,duplicates=0;
  for(const row of rows||[]){
    const price=numberOrNull(row.cuota_decimal);
    if(!permitted(row)||!EXPLICIT_TYPES.has(row.tipo_cuota)||
        price===null||price<=1.50||price>1000){
      invalid++;continue;
    }
    if(!byMatch.has(row.id))byMatch.set(row.id,[]);
    byMatch.get(row.id).push(row);
  }
  const picks=[];
  for(const choices of byMatch.values()){
    choices.sort((a,b)=>parsedDate(a.archivado_utc)-parsedDate(b.archivado_utc)
      ||String(a.clave).localeCompare(String(b.clave),"es"));
    picks.push(choices[0]);
    duplicates+=choices.length-1;
  }
  return {picks,invalid,duplicates};
}
function returns(row){
  // Never use a stored ROI without a genuinely frozen, pre-match odd.
  if(!settled(row))return null;
  const price=numberOrNull(row.cuota_decimal);
  if(price===null||price<=1.50||price>1000)return null;
  return row.resultado==="1"||row.resultado===1 ? price-1 : -1;
}
/** Pricing a model prediction for an illustrative 1-unit simulation.
 * This does not constitute a real or offered bookmaker quote.
 */
export function fairOdds(row){
  const p=numberOrNull(row?.probabilidad);
  return p!==null&&Number.isFinite(p)&&p>0&&p<=1?1/p:null;
}
export function fairReturn(row){
  if(!settled(row))return null;
  const price=fairOdds(row);
  if(price===null)return null;
  return String(row.resultado)==="1"?price-1:-1;
}
function countOutcomes(rows){
  const done=rows.filter(settled);
  const hits=done.filter(row=>String(row.resultado)==="1").length;
  return {
    registered:rows.length,settled:done.length,hits,
    misses:done.length-hits,
    unresolved:rows.length-done.length,
    accuracy:done.length?hits/done.length:null
  };
}
function summaryTop(rows){
  const basic=countOutcomes(rows);
  const fairDone=rows.filter(x=>fairReturn(x)!==null);
  const fairCount=fairDone.length;
  const fairProfit=fairCount?fairDone.reduce((sum,x)=>sum+fairReturn(x),0):null;
  return {...basic,
    financialCount:0,profit:null,roi:null, // ROI de bookmaker: NO DISPONIBLE
    fairCount,fairProfit,fairStake:fairCount,
    fairRoi:fairCount?fairProfit/fairCount:null,
    fairUnavailable:basic.settled-fairCount,
    financeReason:"Simulación hipotética con cuota justa = 1 / probabilidad originalmente archivada. No son cuotas de bookmaker; no demuestra rentabilidad real."};
}
function summaryCombined(top,additional){
  const count=top.fairCount+additional.financialCount;
  const profit=count?(top.fairProfit??0)+(additional.profit??0):null;
  return {
    financialCount:count,stake:count,profit,
    roi:count?profit/count:null,
    topCount:top.fairCount,additionalCount:additional.financialCount,
    note:"SIMULACIÓN MIXTA. Top 3 a cuota justa del modelo; adicional a cuota archivada (API observada o indicativa). No refleja precios disponibles ni ganancias reales."
  };
}
function summaryExtra(rows){
  const basic=countOutcomes(rows);
  const settledPrices=rows.filter(row=>returns(row)!==null);
  const units=settledPrices.reduce((s,row)=>s+returns(row),0);
  const indicative=rows.filter(x=>x.tipo_cuota==="INDICATIVA_NO_VERIFICADA");
  const observed=rows.filter(x=>x.tipo_cuota==="OFRECIDA_API_REGISTRADA");
  const observedDone=settledPrices.filter(x=>x.tipo_cuota==="OFRECIDA_API_REGISTRADA");
  const observedProfit=observedDone.reduce((s,x)=>s+returns(x),0);
  return {...basic,
    financialCount:settledPrices.length,
    profit:settledPrices.length?units:null,
    roi:settledPrices.length?units/settledPrices.length:null,
    indicativeCount:indicative.length,
    observedCount:observed.length,
    observedSettled:observedDone.length,
    observedProfit:observedDone.length?observedProfit:null,
    observedRoi:observedDone.length?observedProfit/observedDone.length:null,
    indicativeSettled:settledPrices.filter(x=>x.tipo_cuota==="INDICATIVA_NO_VERIFICADA").length,
    financeReason:"Balance exclusivamente hipotético de 1 unidad por selección, con cuotas congeladas antes del partido."
  };
}
function series(topRows,extraRows,grain){
  const groups=new Map();
  function ensure(row){
    const kick=parsedDate(row.fecha_utc);
    const key=kick===null?null:bucketOf(kick,grain);
    if(!key)return null;
    if(!groups.has(key))groups.set(key,{key,top:0,topHits:0,extra:0,extraHits:0,extraProfit:0,priced:0});
    return groups.get(key);
  }
  for(const row of topRows.filter(settled)){
    const item=ensure(row);
    if(!item)continue;
    item.top++;
    if(String(row.resultado)==="1")item.topHits++;
  }
  for(const row of extraRows.filter(settled)){
    const item=ensure(row);
    if(!item)continue;
    item.extra++;
    if(String(row.resultado)==="1")item.extraHits++;
    const profit=returns(row);
    if(profit!==null){item.priced++;item.extraProfit+=profit;}
  }
  let cumulative=0;
  return [...groups.values()].sort((a,b)=>a.key.localeCompare(b.key)).map(x=>{
    cumulative+=x.extraProfit;
    return {...x,
      topAccuracy:x.top?x.topHits/x.top:null,
      extraAccuracy:x.extra?x.extraHits/x.extra:null,
      extraProfit:x.priced?x.extraProfit:null,
      extraCumulative:x.priced?cumulative:null
    };
  });
}
function ledger(topRows,extraRows){
  const combined=[
    ...topRows.map((r)=>({...r,group:"Top 3",price:fairOdds(r),
      return:fairReturn(r),priceKind:"CUOTA_JUSTA_MODELO_NO_OFRECIDA"})),
    ...extraRows.map((r)=>({...r,group:"Adicional +1,50",
      price:numberOrNull(r.cuota_decimal),return:returns(r),
      priceKind:r.tipo_cuota}))
  ];
  return combined.sort((a,b)=>parsedDate(b.fecha_utc)-parsedDate(a.fecha_utc)
    ||String(a.id).localeCompare(String(b.id),"es")
    ||String(a.group).localeCompare(String(b.group),"es"));
}
export function performanceSnapshot(model={},filters={},now=new Date()){
  const archived=Array.isArray(model.archivedPicks)?model.archivedPicks:[];
  const additional=Array.isArray(model.allOdds)?model.allOdds:[];
  const top=distinctTop3(archived);
  const extra=distinctAdditional(additional);
  const topRows=top.picks.filter(r=>inScope(r,now,filters));
  const extraRows=extra.picks.filter(r=>inScope(r,now,filters));
  const grain=filters.granularity==="month"?"month":"week";
  const topSummary=summaryTop(topRows);
  const additionalSummary=summaryExtra(extraRows);
  return {
    top:topSummary,additional:additionalSummary,
    combined:summaryCombined(topSummary,additionalSummary),
    byLeague:LEAGUES.map(league=>({
      name:league,
      top:summaryTop(topRows.filter(x=>x.liga===league)),
      additional:summaryExtra(extraRows.filter(x=>x.liga===league))
    })),
    timeline:series(topRows,extraRows,grain),
    selectionAudit:model.evaluations?.odds?.seleccion_automatica||null,
    granularity:grain,
    rows:ledger(topRows,extraRows),
    safeguards:{
      ignoredTopInvalid:top.invalid,
      ignoredTopDuplicates:top.duplicates,
      ignoredTopBeyondThree:top.extra,
      ignoredAdditionalInvalid:extra.invalid,
      ignoredAdditionalDuplicates:extra.duplicates,
      excludesExploratory:true
    }
  };
}
