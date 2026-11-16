/** Fiabilidad basada SOLO en pronósticos archivados prepartido. */
const LEVELS={
  audited:"BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",
  exploratory:"EXPLORATORIO_NO_VALIDADO",
  uncalibrated:"MODELO_NO_CALIBRADO"
};
const EMPTY=Object.freeze({
  registradas:0,pendientes:0,sin_marcador:0,sin_estadistica:0,
  muestra:0,partidos_unicos:0,aciertos:0,acierto_pct:null,
  probabilidad_media_pct:null,brier:null,logloss:null,ece:null,
  sesgo_pct:null,calibracion:[],evidencia:"SIN_MUESTRA"
});
function pick(report,market,league,quality){
  if(!report)return EMPTY;
  if(quality==="top3"){
    return league
      ?report.por_mercado_liga_registro?.[market]?.[league]?.top3||EMPTY
      :report.por_mercado_registro?.[market]?.top3||EMPTY;
  }
  const label=LEVELS[quality];
  if(label){
    return league
      ?report.por_mercado_liga_calidad?.[market]?.[league]?.[label]||EMPTY
      :report.por_mercado_calidad?.[market]?.[label]||EMPTY;
  }
  return league
    ?report.por_mercado_liga?.[market]?.[league]||EMPTY
    :report.por_mercado?.[market]||EMPTY;
}
export function reliabilitySnapshot(report,filters={}){
  const market=filters.market||"corners",league=filters.league||"",
    quality=filters.quality||"all";
  const metrics=pick(report,market,league,quality);
  const leagues=Object.keys(report?.por_mercado_liga?.[market]||{}).sort((a,b)=>a.localeCompare(b,"es"))
    .filter(name=>!league||name===league)
    .map(name=>({liga:name,...pick(report,market,name,quality)}));
  const recent=(report?.ultimas_evaluaciones||[])
    .filter(x=>{
      if(x.categoria!==market)return false;
      if(league&&x.liga!==league)return false;
      if(quality==="top3")return ["1","2","3"].includes(String(x.posicion_top3));
      if(LEVELS[quality])return x.nivel===LEVELS[quality];
      return true;
    }).slice(0,35);
  return {
    available:Boolean(report?.version),
    metrics:{...EMPTY,...metrics},
    leagues,recent,quality,market,league,
    uniqueEnough:Number(metrics?.partidos_unicos||0)>=30,
    note:"Varias líneas del mismo encuentro están correlacionadas: la muestra de selecciones no equivale a partidos independientes."
  };
}
