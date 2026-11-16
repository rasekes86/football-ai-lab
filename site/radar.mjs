/** Radar prepartido: datos observados y pronósticos modelados separados. */
import { futureMarketSnapshot } from "./future_markets.mjs";

const METRIC = Object.freeze({
  corners:"corners",shots:"shots",on_target:"on_target",yellow:"yellow",
  red:"red",fouls:"fouls",goals:"goals",double:"goals",
  result:"goals",btts:"goals"
});
export const radarMetric = category => METRIC[category] || null;
const numeric = x => typeof x === "number" && Number.isFinite(x) && x >= 0;
const clamp = (v,min,max) => Math.max(min,Math.min(max,v));

function statFor(team, scope, period, metric) {
  const window = team?.[scope]?.[String(period)];
  const stats = window?.metrics?.[metric];
  if (!window || !stats || !Array.isArray(stats.values)) {
    return {games:0,verified:0,mean:null,values:[],wins:null,draws:null,
      losses:null,bothScored:null,goalsFor:null,goalsAgainst:null,latest:null};
  }
  const values=stats.values.map(v=>numeric(v)?v:null);
  const verified=values.filter(numeric).length;
  const games=Math.max(0,Number(window.matches)||0);
  return {
    games,verified,
    mean:verified?values.reduce((sum,v)=>sum+(numeric(v)?v:0),0)/verified:null,
    values,
    wins:window.wins,draws:window.draws,losses:window.losses,
    bothScored:window.both_scored,goalsFor:window.goals_for,
    goalsAgainst:window.goals_against,latest:window.latest
  };
}
function actualLine(p, market) {
  if(["corners","shots","on_target","yellow","red","fouls"].includes(market)){
    const line=Number(p.linea);
    if(!Number.isFinite(line)||line<=0)return null;
    return {line,direction:p.direccion==="menos"?"under":p.direccion==="mas"?"over":null};
  }
  if(market==="goals"){
    const m=String(p.seleccion||"").match(/^(Más|Menos) de (\d+[,.]\d+) goles$/);
    return m?{line:Number(m[2].replace(",",".")),
      direction:m[1]==="Más"?"over":"under"}:null;
  }
  return null;
}
function historicalLine(stats, forecast, category) {
  const contract=actualLine(forecast,category);
  if(!contract?.direction || !stats.verified)return null;
  const n=stats.values.filter(numeric);
  const matches=n.filter(v=>contract.direction==="over"?
    v>contract.line:v<contract.line).length;
  return {matched:matches,observed:n.length,frequency:matches/n.length,
    direction:contract.direction,line:contract.line};
}
/** Cobertura = proporción observada en los partidos recientes usados,
 * NO confianza del modelo. Datos ausentes no son ceros.
 */
export function radarSnapshot(model,filters={},now=new Date()) {
  const market=filters.market||"corners";
  const period=[5,10,20].includes(Number(filters.window))?
    Number(filters.window):10;
  const scope=filters.scope==="overall"?"overall":"venue_only";
  const minCoverage=clamp(Number(filters.coverage||0)||0,0,1);
  const base=futureMarketSnapshot(model,{
    market,league:filters.league,team:filters.team,
    quality:filters.quality,minProbability:filters.minProbability,
    minFair:filters.minFair,order:filters.order==="confidence"?"confidence":"kickoff"
  },now);
  const indexed=new Map((model?.radarContexts||[])
    .filter(x=>x&&typeof x.id==="string").map(x=>[x.id,x]));
  const metric=radarMetric(market),rows=[];
  let noContext=0,belowCoverage=0,limited=0;
  for(const m of base.fixtures) {
    const source=indexed.get(m.id);
    const home=statFor(source?.equipos?.local,scope,period,metric);
    const away=statFor(source?.equipos?.visitante,scope,period,metric);
    const count=home.games+away.games;
    const verified=home.verified+away.verified;
    const coverage=count?verified/count:null;
    const enough=home.verified>=3 && away.verified>=3;
    if(!source)noContext++;
    if(!enough)limited++;
    if(minCoverage>0 && (coverage===null||coverage<minCoverage)){
      belowCoverage++;continue;
    }
    rows.push({...m,context:source||null,profile:{
      market,metric,period,scope,home,away,coverage,verified,
      sample:count, enough,
      observedHome:historicalLine(home,m.best,market),
      observedAway:historicalLine(away,m.best,market),
    }});
  }
  if(filters.order==="coverage")rows.sort((a,b)=>{
    const ac=a.profile.coverage??-1,bc=b.profile.coverage??-1;
    return bc-ac||b.profile.verified-a.profile.verified||a.kickoff-b.kickoff;
  });
  return {
    ...base,rows,total:rows.length,contextAvailable:indexed.size>0,
    noContext,belowCoverage,limited,
    market,period,scope,minCoverage,metric,
    // The snapshot remains purely descriptive; never compute value/edge.
    descriptiveOnly:true,
  };
}
