/** Fase 8 · Comparación segura de precios observados: no modelar cuotas faltantes. */
const MAX_AGE_MS=24*3600*1000;
export const REAL_ODDS_CATEGORIES=Object.freeze([
  {key:"",label:"1X2 y goles"},
  {key:"result",label:"Resultado 1X2"},
  {key:"goals",label:"Total goles"},
  {key:"corners",label:"Córners totales"},
  {key:"yellow",label:"Amarillas totales (solo mercado explícito)"},
  {key:"btts",label:"Ambos marcan"}
]);
const valid = x => typeof x==="number" && Number.isFinite(x);
const fold = s => String(s||"").normalize("NFD")
  .replace(/[\u0300-\u036f]/g,"").toLowerCase();

export function realOddsSnapshot(model,filter={},now=new Date()){
  const source=model?.realOddsRaw||null;
  const payload=model?.realOddsComparison||null;
  const status=source?.estado||"SIN_PUBLICAR";
  const market=String(filter.market||"");
  const league=String(filter.league||"");
  const bookmaker=String(filter.bookmaker||"");
  const team=fold(filter.team||"").trim();
  const minProbability=Number(filter.minProbability||0);
  const minModel=valid(minProbability)?Math.max(0,Math.min(1,minProbability)):0;
  const nowMs=now.getTime();
  const validQuote=(q)=>{
    if(!q||!["The Odds API V4","5DollarFootballAPI","API-Football"].includes(q.proveedor)||
       q.etiqueta!=="COMPARACION_INFORMATIVA_NO_VALIDADA"||
       !["result","goals","corners","yellow","btts"].includes(q.categoria))return false;
    const changed=Date.parse(q.actualizado_utc),kickoff=Date.parse(q.fecha_utc);
    if(!Number.isFinite(changed)||!Number.isFinite(kickoff)||
       changed>nowMs+300000||nowMs-changed>MAX_AGE_MS||kickoff<=nowMs||
       changed>=kickoff)return false;
    if(!valid(q.cuota_real)||q.cuota_real<=1||!valid(q.probabilidad_modelo)||
       q.probabilidad_modelo<=0||q.probabilidad_modelo>=1||
       !valid(q.p_mercado_sin_margen)||q.p_mercado_sin_margen<=0||
       q.p_mercado_sin_margen>=1)return false;
    const expected=(q.probabilidad_modelo*q.cuota_real-1);
    if(!valid(q.ev_teorico_unidad)||Math.abs(q.ev_teorico_unidad-expected)>.003)return false;
    return true;
  };
  const sourced=(payload?.comparaciones||[]).filter(validQuote);
  const books=[...new Set(sourced.map(x=>x.bookmaker).filter(Boolean))]
    .sort((a,b)=>a.localeCompare(b,"es"));
  const filtered=sourced.filter(x=>{
    if(market&&x.categoria!==market)return false;
    if(league&&x.liga!==league)return false;
    if(bookmaker&&x.bookmaker!==bookmaker)return false;
    if(x.probabilidad_modelo<minModel)return false;
    if(team&&!fold(x.local+" "+x.visitante).includes(team))return false;
    return true;
  });
  const groups=new Map();
  for(const q of filtered){
    const key=[q.fixture_id,q.categoria,q.seleccion].join("|");
    let entry=groups.get(key);
    if(!entry){
      entry={
        id:key,fixture_id:q.fixture_id,liga:q.liga,
        local:q.local,visitante:q.visitante,fecha_utc:q.fecha_utc,
        categoria:q.categoria,seleccion:q.seleccion,
        probabilidad_modelo:q.probabilidad_modelo,
        nivel:q.nivel,posicion_top3:q.posicion_top3,
        opciones:[]
      };
      groups.set(key,entry);
    }
    if(!entry.opciones.some(x=>x.bookmaker_id===q.bookmaker_id && x.proveedor===q.proveedor))
      entry.opciones.push(q);
  }
  const cards=[...groups.values()].map(x=>{
    x.opciones.sort((a,b)=>b.cuota_real-a.cuota_real||
      a.bookmaker.localeCompare(b.bookmaker,"es"));
    x.mejor=x.opciones[0];
    return x;
  }).sort((a,b)=>a.fecha_utc.localeCompare(b.fecha_utc)||
    a.liga.localeCompare(b.liga,"es")||
    a.seleccion.localeCompare(b.seleccion,"es"));
  return {
    status,configured:!["SIN_PUBLICAR","SIN_CLAVE","DESACTIVADO"].includes(status),
    sourceUpdated:source?.capturado_utc||null,
    quota:source?.auditoria?.estimacion_creditos_maximos||0,
    providers:books,
    cards,quotes:filtered.length,scanned:sourced.length,
    games:new Set(cards.map(x=>x.fixture_id)).size,
    leagues:new Set(cards.map(x=>x.liga)).size,
    allGames:new Set(sourced.map(x=>x.fixture_id)).size,
    market,league,bookmaker,
    limitations:"Diferencias basadas en probabilidades experimentales no calibradas. La cuota observada puede cambiar o no estar accesible al público; no garantiza rentabilidad.",
  };
}
