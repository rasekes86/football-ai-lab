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


// Aggregated public diagnostics only: no API keys, raw match IDs or hidden
// bookmaker responses. A missing quote must never be presented as an offer.
export const ODDS_LEAGUES=Object.freeze([
  "LaLiga","Segunda División","Premier League","Bundesliga","Serie A","Ligue 1"
]);

export function oddsCoverageSnapshot(model,now=new Date()){
  const raw=model?.realOddsRaw||{};
  const audit=raw?.auditoria||{};
  const providers=audit?.fuentes_gratuitas||[];
  const five=providers.find(x=>x.proveedor==="5DollarFootballAPI")||{};
  const api=providers.find(x=>x.proveedor==="API-Football")||{};
  const perLeague=five.cobertura_ligas||{};
  const sourceTime=Date.parse(raw.capturado_utc||"");
  const stale=!Number.isFinite(sourceTime)||now.getTime()-sourceTime>24*3600*1000||
    sourceTime>now.getTime()+5*60*1000;
  const sourced=(raw.cuotas||[]).filter(x=>x&&x.proveedor&&
    typeof x.liga==="string"&&typeof x.fecha_utc==="string");
  const fixturesByLeague=new Map();
  for(const quote of sourced){
    if(!quote.fixture_id)continue;
    if(!fixturesByLeague.has(quote.liga))fixturesByLeague.set(quote.liga,new Set());
    fixturesByLeague.get(quote.liga).add(quote.fixture_id);
  }
  const labelFor={
    CON_CUOTAS:"Con precios observados",
    SIN_PARTIDOS_MODELO:"Sin próximos partidos en la ventana",
    NO_INCLUIDA_EN_FREE:"Requiere Community Access u otra fuente",
    SIN_EVENTOS_PROVEEDOR:"No devolvió eventos compatibles",
    SIN_COINCIDENCIA_VERIFICADA:"Equipos u horarios sin coincidencia segura",
    FUERA_DEL_CUPO_DE_CONSULTAS:"No entró en el cupo de consulta",
    SIN_PRECIOS_VALIDOS:"Partidos coincidentes, pero sin precios completos",
  };
  const rows=ODDS_LEAGUES.map(name=>{
    const diag=perLeague[name]||{};
    const n=fixturesByLeague.get(name)?.size||0;
    const selected=Number.isFinite(diag.partidos_consultados)?diag.partidos_consultados:null;
    return {
      name,
      quotes:sourced.filter(x=>x.liga===name).length,
      games:n,
      model:Number.isFinite(diag.partidos_modelo)?diag.partidos_modelo:null,
      returned:Number.isFinite(diag.eventos_proveedor)?diag.eventos_proveedor:null,
      matched:Number.isFinite(diag.partidos_emparejados)?diag.partidos_emparejados:null,
      requested:selected,
      state:typeof diag.estado==="string"?diag.estado:"AUDITORIA_PENDIENTE",
      description:labelFor[diag.estado]||"Pendiente de ejecutar el análisis con diagnóstico",
      reasons:diag.motivos_descartados||{},
      community:name==="Segunda División"&&five.community_segunda_activada===true
    };
  });
  return {
    rows,
    total:rows.reduce((sum,row)=>sum+row.games,0),
    captured:raw.capturado_utc||null,
    stale,
    hasAudit:Boolean(perLeague&&Object.keys(perLeague).length),
    providerStatus:five.estado||"SIN_DATOS",
    backupStatus:api.estado||"DESACTIVADO",
    published:raw.estado||"SIN_PUBLICAR"
  };
}
