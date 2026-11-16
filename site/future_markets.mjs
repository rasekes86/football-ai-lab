/** Pronósticos de los próximos partidos por mercado. Nunca se consideran cuotas ofrecidas. */
import { optionByKey } from "./markets.mjs";

const folded = value => String(value ?? "").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").toLowerCase();

const validProbability = p => typeof p === "number" && Number.isFinite(p) && p > 0 && p < 1;

export function futureMarketSnapshot(model, filters={}, now=new Date()) {
  const market=optionByKey(filters.market);
  const league=String(filters.league||"");
  const query=folded(filters.team||"").trim();
  const quality=String(filters.quality||"all");
  const order=filters.order==="confidence"?"confidence":"kickoff";
  const list=Array.isArray(model?.marketFutures)?model.marketFutures:[];
  const cutoff=now.getTime(),seen=new Set();
  const fixtures=[];
  let futureMatches=0, withoutMarket=0;
  for(const match of list) {
    if(!match?.id||seen.has(match.id))continue;
    seen.add(match.id);
    const kickoff=Date.parse(match.fecha_utc);
    if(!Number.isFinite(kickoff)||kickoff<=cutoff)continue;
    if(league&&match.liga!==league)continue;
    if(query&&!folded(match.local+" "+match.visitante).includes(query))continue;
    futureMatches++;
    const predictions=Array.isArray(match.mercados?.[market.key])?
      match.mercados[market.key].filter(p=>validProbability(p.probabilidad)): [];
    const eligible=predictions.filter(p=>{
      if(quality==="top3")return Number.isInteger(p.posicion_top3) && p.posicion_top3>=1;
      if(quality==="audited")return p.nivel==="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA";
      if(quality==="exploratory")return p.nivel==="EXPLORATORIO_NO_VALIDADO";
      return true;
    });
    if(!eligible.length){withoutMarket++;continue;}
    eligible.sort((a,b)=>(b.probabilidad-a.probabilidad)||
      String(a.seleccion).localeCompare(String(b.seleccion),"es"));
    fixtures.push({...match,kickoff,pronosticos:eligible,
      best:eligible[0]});
  }
  fixtures.sort((a,b)=>order==="confidence"?
    b.best.probabilidad-a.best.probabilidad||a.kickoff-b.kickoff:
    a.kickoff-b.kickoff||b.best.probabilidad-a.best.probabilidad);
  const forecastCount=fixtures.reduce((n,m)=>n+m.pronosticos.length,0);
  const qualityCounts={top3:0,audited:0,exploratory:0,uncalibrated:0};
  for(const m of fixtures){
    for(const p of m.pronosticos){
      if(Number.isInteger(p.posicion_top3))qualityCounts.top3++;
      if(p.nivel==="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA")
        qualityCounts.audited++;
      if(p.nivel==="EXPLORATORIO_NO_VALIDADO")qualityCounts.exploratory++;
      if(p.nivel==="MODELO_NO_CALIBRADO")qualityCounts.uncalibrated++;
    }
  }
  return {market,league,quality,order,fixtures,futureMatches,withoutMarket,
    forecastCount,qualityCounts};
}
