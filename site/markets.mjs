/** Explorador estadístico: histórico observado y pronósticos prospectivos separados. */
export const MARKET_OPTIONS = Object.freeze([
  {key:"corners",label:"Córners",kind:"count",metric:"corners",markets:["Córners totales"],lines:[5.5,7.5,8.5,9.5,10.5,11.5,12.5]},
  {key:"shots",label:"Tiros totales",kind:"count",metric:"shots",markets:["Tiros totales"],lines:[12.5,15.5,17.5,19.5,21.5,24.5,27.5]},
  {key:"on_target",label:"Tiros a puerta",kind:"count",metric:"on_target",markets:["Tiros a puerta totales"],lines:[3.5,5.5,6.5,7.5,8.5,9.5,11.5]},
  {key:"fouls",label:"Faltas cometidas",kind:"count",metric:"fouls",markets:["Faltas totales"],lines:[13.5,16.5,19.5,21.5,23.5,25.5,29.5]},
  {key:"yellow",label:"Tarjetas amarillas",kind:"count",metric:"yellow",markets:["Tarjetas amarillas totales"],lines:[1.5,2.5,3.5,4.5,5.5,6.5]},
  {key:"red",label:"Tarjetas rojas",kind:"count",metric:"red",markets:["Tarjetas rojas totales"],lines:[0.5,1.5,2.5]},
  {key:"goals",label:"Goles totales",kind:"goals",markets:["Total goles"],lines:[0.5,1.5,2.5,3.5,4.5]},
  {key:"double",label:"Doble oportunidad",kind:"outcome",markets:["Doble oportunidad"],lines:["1X","X2","12"]},
  {key:"result",label:"Resultado 1X2",kind:"outcome",markets:["1X2"],lines:["1","X","2"]},
  {key:"btts",label:"Ambos marcan",kind:"btts",markets:["Ambos marcan"],lines:["Sí","No"]},
]);

export const optionByKey = key => MARKET_OPTIONS.find(x=>x.key===key) || MARKET_OPTIONS[0];

const integer = val => Number.isInteger(val) && val>=0 && val<=400;
const dateOf = raw => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(raw||""))) return null;
  const day=Date.parse(String(raw)+"T00:00:00Z");
  return Number.isFinite(day)?day:null;
};
const empty = () => ({verified:false,local:null,visitante:null,total:null,fuentes:[]});
const mean = vals => vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null;
const median = vals => {
  if (!vals.length) return null;
  const arr=[...vals].sort((a,b)=>a-b),middle=Math.floor(arr.length/2);
  return arr.length%2?arr[middle]:(arr[middle-1]+arr[middle])/2;
};

function observed(row, market) {
  const h=row.goles_local, a=row.goles_visitante;
  if (!integer(h)||!integer(a)) return empty();
  if (market.kind==="goals") return {
    verified: Boolean(row.fuente_marcador),
    local:h,visitante:a,total:h+a,
    outcome:h>a?"1":h===a?"X":"2",
    fuentes:row.fuente_marcador?[row.fuente_marcador]:[]
  };
  if (market.kind==="outcome"||market.kind==="btts") return {
    verified:Boolean(row.fuente_marcador),
    local:h,visitante:a,total:h+a,
    outcome:h>a?"1":h===a?"X":"2",
    btts:h>0&&a>0?"Sí":"No",
    fuentes:row.fuente_marcador?[row.fuente_marcador]:[]
  };
  const stat=row.estadisticas?.[market.metric]||{};
  const has=integer(stat.local)&&integer(stat.visitante)&&integer(stat.total)&&
    stat.total===stat.local+stat.visitante;
  return {
    verified:has&&Array.isArray(stat.fuentes)&&stat.fuentes.length>0,
    local:has?stat.local:null,visitante:has?stat.visitante:null,
    total:has?stat.total:null,fuentes:stat.fuentes||[]
  };
}
export function isHit(observation,market,line) {
  if(!observation.verified)return null;
  if(market.kind==="count"||market.kind==="goals"){
    const val=Number(line);
    return Number.isFinite(val)?observation.total>val:null;
  }
  if(market.kind==="btts") return observation.btts===line;
  if(market.kind==="outcome"){
    const key=observation.outcome;
    if(line==="1X")return key==="1"||key==="X";
    if(line==="X2")return key==="X"||key==="2";
    if(line==="12")return key==="1"||key==="2";
    return line===key;
  }
  return null;
}

function buckets(rows, market, line) {
  const vals=rows.map(x=>x.observation.total).filter(integer);
  if(!vals.length)return [];
  if(market.kind==="outcome"||market.kind==="btts"){
    const possibilities=market.kind==="btts"
      ?[["Sí",r=>r.observation.btts==="Sí"],["No",r=>r.observation.btts==="No"]]
      :[["Local (1)",r=>r.observation.outcome==="1"],["Empate (X)",r=>r.observation.outcome==="X"],["Visitante (2)",r=>r.observation.outcome==="2"]];
    return possibilities.map(([label,fn])=>({label,count:rows.filter(fn).length}));
  }
  const ceiling=Math.max(1,...vals),step=Math.max(1,Math.ceil((ceiling+1)/6));
  const limits=Math.ceil((ceiling+1)/step);
  return Array.from({length:Math.min(6,limits)},(_,i)=>{
    const lower=i*step,upper=(i+1)*step-1;
    return {label:step===1?String(lower):lower+"–"+upper,
      count:vals.filter(n=>n>=lower&&n<=upper).length};
  });
}

/**
 * Historias observadas NO son selecciones apostadas ni backtest del modelo.
 * Los aciertos se calculan solo sobre la tabla prospectiva archivada.
 */
export function marketSnapshot(model,filter={},now=new Date()) {
  const market=optionByKey(filter.market);
  const line=filter.line===undefined||filter.line===null||filter.line===""
    ?market.lines[Math.floor(market.lines.length/2)]
    :filter.line;
  const league=filter.league||"";
  const q=String(filter.team||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
  const days=filter.days==="all"||!filter.days?365:Number(filter.days);
  const asOf=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
  const cutoff=asOf-Math.max(1,Math.min(365,Number.isFinite(days)?days:365))*86400000;
  const visible=row=>{
    if(league&&row.liga!==league)return false;
    const day=dateOf(row.fecha);
    if(day===null||day<cutoff||day>asOf)return false;
    if(q&&!String(row.local+" "+row.visitante).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().includes(q))return false;
    return true;
  };
  const historical=(model.marketHistory||[]).filter(visible).sort((a,b)=>b.fecha.localeCompare(a.fecha));
  const valid=historical.map(r=>({row:r,observation:observed(r,market)})).filter(x=>x.observation.verified);
  const vals=valid.map(x=>x.observation.total);
  const above=valid.filter(x=>isHit(x.observation,market,line)).length;
  const distribution=buckets(valid,market,line);
  const byLeague=[...new Set(historical.map(x=>x.liga))].sort((a,b)=>a.localeCompare(b,"es"))
    .map(name=>{
      const sample=valid.filter(x=>x.row.liga===name);
      const n=sample.length;
      return {liga:name,partidos:n,media:mean(sample.map(x=>x.observation.total)),
        ratio:n?sample.filter(x=>isHit(x.observation,market,line)).length/n:null};
    });
  const picks=(model.archivedPicks||[]).filter(x=>{
    if(!market.markets.includes(x.mercado))return false;
    if(league&&x.liga!==league)return false;
    const day=dateOf(String(x.fecha_utc||"").slice(0,10));
    if(day===null||day<cutoff||day>asOf)return false;
    return !q||String(x.local+" "+x.visitante).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().includes(q);
  });
  const evaluated=picks.filter(x=>x.estado==="FINALIZADO"&&["0","1"].includes(String(x.resultado)));
  const wins=evaluated.filter(x=>String(x.resultado)==="1").length;
  return {
    market,line,league,days,team:filter.team||"",
    verified:valid.length,missing:historical.length-valid.length,
    historicalCount:historical.length,average:mean(vals),median:median(vals),
    above,aboveRate:valid.length?above/valid.length:null,
    byLeague,distribution,
    picks:{registered:picks.length,evaluated:evaluated.length,hits:wins,
      accuracy:evaluated.length?wins/evaluated.length:null},
    rows:valid,
  };
}
