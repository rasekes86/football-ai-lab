/** Football AI Lab: consultas prepartido desde los datos ya publicados.
 * No consulta marcadores en directo ni inventa cuotas ofrecidas.
 */
export const LEAGUES=[
 ["SP1","LaLiga"],["SP2","Segunda División"],["E0","Premier League"],
 ["D1","Bundesliga"],["I1","Serie A"],["F1","Ligue 1"]
];
export const MARKETS=[
 ["goals","⚽ Goles"],["corners","🚩 Córners"],["shots","🥅 Tiros"],
 ["on_target","🎯 Tiros a puerta"],["yellow","🟨 Amarillas"],
 ["result","🏆 Resultado 1X2"],["double","🔀 Doble oportunidad"],
 ["btts","🤝 Ambos marcan"],["fouls","🛑 Faltas"],["red","🟥 Rojas"]
];
const maxAge=48*3600*1000,period=14*86400000,pageSize=6;
const flat=s=>String(s??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
 .toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const instant=s=>{const n=Date.parse(s||"");return Number.isFinite(n)?n:null;};
const number=v=>typeof v==="number"&&Number.isFinite(v)?v:null;
const bt=(label,action)=>({text:label,callback_data:action});
const kb=(...rows)=>({inline_keyboard:rows});
const output=(text,rows)=>({text:text.slice(0,3950),reply_markup:kb(...rows)});
const base=[bt("🏠 Menú","menu")];
const topMenu=[
 [bt("📅 Próximos partidos","p:0"),bt("🏟️ Ligas","leagues")],
 [bt("📊 Mercados","markets"),bt("💶 Cuotas >1,50","q")],
 [bt("✅ Resultados","results"),bt("❔ Ayuda","help")]
];
export const pct=x=>number(x)!==null?(x*100).toFixed(1).replace(".",",")+" %":"—";
export const dec=x=>number(x)!==null?x.toFixed(2).replace(".",","):"—";
export const showDate=x=>{
 const n=instant(x);
 return n===null?"Sin fecha":new Intl.DateTimeFormat("es-ES",{
  timeZone:"Europe/Madrid",day:"2-digit",month:"2-digit",
  hour:"2-digit",minute:"2-digit",hour12:false
 }).format(new Date(n));
};
export const madridDay=when=>new Intl.DateTimeFormat("en-CA",{
 timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"
}).format(new Date(when));
function nextDay(value){
 const a=value.split("-").map(Number);
 return new Date(Date.UTC(a[0],a[1]-1,a[2]+1)).toISOString().slice(0,10);
}
export function hash(id){
 let a=2166136261;
 for(const ch of String(id??""))a=Math.imul(a^ch.charCodeAt(0),16777619)>>>0;
 return a.toString(36);
}
export function isFresh(data,now){
 const t=instant(data?.calculado_utc);
 return Array.isArray(data?.partidos)&&t!==null&&
  t<=now.getTime()+300000&&now.getTime()-t<=maxAge;
}
export function upcoming(data,now=new Date()){
 if(!isFresh(data,now))return [];
 return data.partidos.filter(m=>{
  const k=instant(m.fecha_utc);
  return Boolean(m.id)&&k!==null&&k>now.getTime()&&
   k-now.getTime()<=period;
 }).sort((a,b)=>instant(a.fecha_utc)-instant(b.fecha_utc)||
   String(a.id).localeCompare(String(b.id),"es"));
}
const short=(s,n=43)=>String(s).length>n?String(s).slice(0,n-1)+"…":String(s);
const title=m=>m.local+" – "+m.visitante;
const leg=k=>LEAGUES.find(l=>l[0]===k)?.[1]??k;
const market=k=>MARKETS.find(m=>m[0]===k)?.[1]??k;
export function menu(){
 return output("⚽ Football AI Lab · Asistente prepartido\n\n"+
  "Elige una opción o pregunta: «Analiza los partidos de Segunda de mañana».\n"+
  "Los pronósticos proceden de los datos publicados; no se analizan partidos en directo.",topMenu);
}
const back=()=>[base];
function paged(all,page=0,prefix="p",heading="Próximos partidos"){
 const last=Math.max(0,Math.ceil(all.length/pageSize)-1);
 const index=Math.min(last,Math.max(0,Number(page)||0));
 const chunk=all.slice(index*pageSize,(index+1)*pageSize);
 const rows=chunk.map(m=>[bt(short("⚽ "+title(m),53),"f:"+hash(m.id))]);
 const nav=[];
 if(index>0)nav.push(bt("◀️ Anteriores",prefix+":"+(index-1)));
 if(index<last)nav.push(bt("Siguientes ▶️",prefix+":"+(index+1)));
 if(nav.length)rows.push(nav);
 rows.push(base);
 if(!all.length)return output("📅 "+heading+"\n\nNo hay partidos futuros publicados para este filtro.",rows);
 return output("📅 "+heading+" · horario de Madrid\n"+
  "Del partido más cercano al más lejano.\n\n"+
  chunk.map((m,i)=>String(index*pageSize+i+1)+". "+showDate(m.fecha_utc)+
   " · "+m.liga+"\n   "+title(m)).join("\n\n")+
  "\n\nPágina "+(index+1)+"/"+(last+1)+". Pulsa cualquier partido.",rows);
}
function leagues(){
 const rows=[];
 for(let i=0;i<LEAGUES.length;i+=2)rows.push(
  LEAGUES.slice(i,i+2).map(x=>bt(short(x[1],23),"l:"+x[0]+":0")));
 return output("🏟️ Selecciona una liga:",[...rows,base]);
}
function markets(){
 const rows=[];
 for(let i=0;i<MARKETS.length;i+=2)rows.push(
  MARKETS.slice(i,i+2).map(x=>bt(x[1],"k:"+x[0]+":0")));
 return output("📊 ¿Qué mercado quieres consultar?\n"+
  "Verás los próximos partidos que tengan pronósticos para ese mercado.",[...rows,base]);
}
function byCode(list,code){
 const found=list.filter(m=>hash(m.id)===code);
 return found.length===1?found[0]:null;
}
function fixtureCard(m){
 const best=Object.values(m.mercados||{}).flat().filter(x=>
   Number.isInteger(x.posicion_top3)&&x.posicion_top3>=1&&x.posicion_top3<=3)
   .sort((a,b)=>a.posicion_top3-b.posicion_top3).slice(0,3);
 const summary=best.map(p=>"• "+p.seleccion+" · "+pct(p.probabilidad)+
   " · cuota justa "+dec(p.cuota_justa)).join("\n");
 const choices=Object.entries(m.mercados||{}).filter(([k,v])=>
    MARKETS.some(x=>x[0]===k)&&Array.isArray(v)&&v.length)
   .map(([key])=>key);
 const rows=[];
 for(let i=0;i<choices.length;i+=2)rows.push(
   choices.slice(i,i+2).map(key=>bt(market(key),"s:"+key+":"+hash(m.id))));
 rows.push([bt("💶 Cuotas reales","q:"+hash(m.id)),
            bt("📈 Estadísticas","c:"+hash(m.id))]);
 rows.push([bt("📅 Próximos","p:0"),bt("🏠 Menú","menu")]);
 return output("🏟️ "+title(m)+"\n"+m.liga+" · "+showDate(m.fecha_utc)+"\n\n"+
   "Selecciones originales Top 3:\n"+(summary||"Sin selecciones Top 3")+"\n\n"+
   "Elige otro mercado para consultar sus líneas. La cuota justa no es un precio real.",rows);
}
function selections(m,key){
 const choices=m.mercados?.[key];
 if(!Array.isArray(choices)||!choices.length)return output("No hay selecciones de este mercado.",[base]);
 return output(market(key)+" · "+title(m)+"\n"+showDate(m.fecha_utc)+"\n\n"+
  choices.slice(0,12).map(p=>"• "+p.seleccion+"\n  Probabilidad "+pct(p.probabilidad)+
   " · justa "+dec(p.cuota_justa)+
   (Number.isInteger(p.posicion_top3)?" · Top3 #"+p.posicion_top3:"")+
   (p.nivel==="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA"?
      " · retrospectivo":"")).join("\n")+
   "\n\nEstimaciones prepartido experimentales. Cuotas justas ≠ precios ofrecidos.",[
     [bt("💶 Precios reales","q:"+hash(m.id)),bt("🏟️ Partido","f:"+hash(m.id))],base
   ]);
}
function context(m,dossier){
 const item=(dossier?.partidos||[]).find(p=>p.id===m.id);
 if(!item)return output("Ficha de estadísticas no disponible para este partido.",[
   [bt("🏟️ Partido","f:"+hash(m.id))],base
 ]);
 function stat(p){
  const r=p?.reciente;
  if(!r)return "Sin forma reciente verificable";
  return String(r.partidos??"?")+" partidos, "+String(r.v??"?")+"V "+
   String(r.e??"?")+"E "+String(r.d??"?")+"D, goles "+
   String(r.goles_favor??"?")+"-"+String(r.goles_contra??"?")+
   (number(r.medias?.corners)!==null?", córners "+dec(r.medias.corners)+"/p":"");
 }
 return output("📈 Forma previa · "+title(m)+"\n"+showDate(m.fecha_utc)+"\n\n"+
  m.local+": "+stat(item.equipos?.local)+"\n"+
  m.visitante+": "+stat(item.equipos?.visitante)+"\n\n"+
  (item.goles_estimados?"Goles esperados del modelo: "+
  item.goles_estimados.local+" – "+item.goles_estimados.visitante+"\n\n":"")+
  "Datos previos, no estadísticas del encuentro en directo.",[
   [bt("🏟️ Pronósticos","f:"+hash(m.id))],base
  ]);
}
function theory(list,fixture){
 const targets=fixture?[fixture]:list.slice(0,6);
 const out=targets.map(m=>{
  const possible=Object.values(m.mercados||{}).flat().filter(p=>
   number(p.cuota_justa)!==null&&p.cuota_justa>1.5&&
   number(p.probabilidad)!==null&&p.probabilidad>0&&p.probabilidad<1).slice(0,4);
  if(!possible.length)return "";
  return showDate(m.fecha_utc)+" "+title(m)+"\n"+
   possible.map(p=>"• "+p.seleccion+" · modelo "+pct(p.probabilidad)+
     " · justa "+dec(p.cuota_justa)).join("\n");
 }).filter(Boolean).join("\n\n");
 return output("📐 Cuotas justas del modelo >1,50\n"+
  "NO son precios de casas. No demuestran rentabilidad.\n\n"+
  (out||"Sin predicciones de cuota justa superior a 1,50."),[
   [bt("💶 Cuotas reales","q")],base
  ]);
}
function odds(quoteSource,now,fixture){
 const stamp=instant(quoteSource?.capturado_utc);
 const available=["CON_CUOTAS","PARCIAL"].includes(quoteSource?.estado)&&
  stamp!==null&&stamp<=now.getTime()+300000&&now.getTime()-stamp<=86400000;
 const verified=available&&Array.isArray(quoteSource.comparaciones)?
  quoteSource.comparaciones.filter(q=>{
   const kick=instant(q.fecha_utc),t=instant(q.actualizado_utc);
   return ["The Odds API V4","5DollarFootballAPI","API-Football"].includes(q.proveedor)&&
    q.etiqueta==="COMPARACION_INFORMATIVA_NO_VALIDADA"&&
    number(q.cuota_real)!==null&&q.cuota_real>1.5&&
    kick!==null&&kick>now.getTime()&&t!==null&&t<kick&&
    t<=now.getTime()+300000&&now.getTime()-t<=86400000&&
    (!fixture||q.fixture_id===fixture.id);
  }).sort((a,b)=>instant(a.fecha_utc)-instant(b.fecha_utc)||
   a.seleccion.localeCompare(b.seleccion,"es")):[];
 const rows=fixture?[
   [bt("📐 Cuotas justas (no reales)","t:"+hash(fixture.id)),
    bt("🏟️ Partido","f:"+hash(fixture.id))],base
  ]:[[bt("📐 Cuotas justas >1,50 (no reales)","theory")],base];
 if(!verified.length)return output("💶 Precios de bookmaker >1,50\n\n"+
  (available?"No hay ofertas verificadas con esos requisitos.":
   "La fuente de cuotas reales no está activada o no contiene datos recientes.")+
  "\n\nPuedes explorar aparte las cuotas justas teóricas del modelo.",rows);
 return output("💶 Cuotas reales observadas >1,50\n"+
  "Captura: "+showDate(quoteSource.capturado_utc)+
  "\nNo garantizamos que sigan disponibles.\n\n"+
  verified.slice(0,8).map(q=>q.local+" – "+q.visitante+"\n"+
   "• "+q.seleccion+" · "+dec(q.cuota_real)+" · "+q.bookmaker+
   " ("+q.proveedor+")").join("\n\n")+
  (verified.length>8?"\n\nMás precios en el dashboard.":""),rows);
}
function results(source){
 const global=source?.global||{},sample=Number(global.muestra)||0;
 return output("✅ Seguimiento prospectivo\n\n"+
  "Selecciones registradas: "+String(source?.registradas??"—")+"\n"+
  "Pendientes: "+String(source?.pendientes??"—")+"\n"+
  "Evaluables: "+sample+"\n"+
  (sample>0?"Acierto observado: "+
    (number(global.acierto_pct)!==null?dec(global.acierto_pct)+" %":"—")+
    "\nBrier: "+dec(global.brier):
   "Todavía no hay muestra prospectiva suficiente para calcular fiabilidad.")+
  "\n\nNo contamos resultados ausentes como fallos.",[base]);
}
function help(){
 return output("❔ Puedes usar los botones o escribir:\n\n"+
  "«próximos», «mañana», «Tenerife», «Tenerife Ceuta», «goles», "+
  "«córners», «cuotas 1,50», «resultados»,\n"+
  "«Analízame los partidos de Segunda de mañana»,\n"+
  "«Goles de Primera hoy».\n\n"+
  "El bot entiende preguntas sencillas sobre los datos publicados. "+
  "No es un chat de IA libre, no consulta cuotas en directo ni ejecuta apuestas.",[base]);
}
// Interpretación local y gratuita de combinaciones habituales de liga, fecha y mercado.
function questionLeague(q){
 if(/\b(segunda|segunda division|2 division|2a division|liga 2|laliga 2|la liga 2|hypermotion)\b/.test(q))return "SP2";
 if(/\b(primera|primera division|laliga|la liga|liga ea sports)\b/.test(q))return "SP1";
 if(/\b(premier|premier league|liga inglesa)\b/.test(q))return "E0";
 if(/\b(bundesliga|liga alemana)\b/.test(q))return "D1";
 if(/\b(serie a|liga italiana)\b/.test(q))return "I1";
 if(/\b(ligue 1|liga francesa)\b/.test(q))return "F1";
 return "all";
}
function questionMarket(q){
 const terms=[
  [/\b(corner|corners|corneres)\b/,"corners"],
  [/\btiros? a puerta\b/,"on_target"],[/\b(tiros|remates)\b/,"shots"],
  [/\b(amarillas|tarjetas amarillas)\b/,"yellow"],
  [/\bdoble oportunidad\b/,"double"],[/\bambos marcan\b/,"btts"],
  [/\b(goles|gol)\b/,"goals"],[/\b(1x2|empate)\b/,"result"],
  [/\bfaltas\b/,"fouls"],[/\b(rojas|tarjetas rojas)\b/,"red"]
 ];
 for(const [re,key] of terms)if(re.test(q))return key;
 return "all";
}
function naturalDigest(list,action,now){
 const p=action.split(":");
 if(p.length!==5)return help();
 const [,league,day,key,rawPage]=p;
 if(!(league==="all"||LEAGUES.some(x=>x[0]===league))||
    !["all","today","tomorrow"].includes(day)||
    !(key==="all"||MARKETS.some(x=>x[0]===key))||
    !/^\d{1,3}$/.test(rawPage))return help();
 const dayCode=day==="today"?madridDay(now):
  day==="tomorrow"?nextDay(madridDay(now)):null;
 const filtered=list.filter(m=>
  (league==="all"||m.liga===leg(league))&&
  (!dayCode||madridDay(instant(m.fecha_utc))===dayCode)&&
  (key==="all"||Array.isArray(m.mercados?.[key])&&m.mercados[key].length>0));
 const perPage=3, last=Math.max(0,Math.ceil(filtered.length/perPage)-1);
 const page=Math.max(0,Math.min(last,Number(rawPage)));
 const shown=filtered.slice(page*perPage,(page+1)*perPage);
 const headline=[
  league==="all"?"Todas las ligas":leg(league),
  day==="all"?"próximos 14 días":day==="today"?"hoy":"mañana",
  key==="all"?null:market(key)
 ].filter(Boolean).join(" · ");
 const rows=shown.map(m=>[bt(short("🏟️ "+title(m),53),"f:"+hash(m.id))]);
 const nav=[];
 const prefix=["nl",league,day,key].join(":");
 if(page>0)nav.push(bt("◀️ Anteriores",prefix+":"+(page-1)));
 if(page<last)nav.push(bt("Siguientes ▶️",prefix+":"+(page+1)));
 if(nav.length)rows.push(nav);
 rows.push(base);
 if(!shown.length)return output("🔎 "+headline+"\n\n"+
  "No hay partidos futuros publicados que cumplan estos filtros. "+
  "Comprueba también que el informe esté actualizado.",rows);
 const summary=shown.map((m,i)=>{
  const values=(key==="all"?Object.values(m.mercados||{}).flat():
   m.mercados?.[key]||[]).filter(x=>Number.isInteger(x.posicion_top3)&&
    x.posicion_top3>=1&&x.posicion_top3<=3)
    .sort((a,b)=>a.posicion_top3-b.posicion_top3).slice(0,3);
  const published=(key==="all"?Object.values(m.mercados||{}).flat():
   m.mercados?.[key]||[]).slice(0,2);
  const lines=values.length?values.map(x=>"   • "+x.seleccion+
   " · "+pct(x.probabilidad)+" · justa "+dec(x.cuota_justa)).join("\n"):
   published.length?"   Selecciones publicadas (sin ranking Top 3):\n"+
    published.map(x=>"   • "+x.seleccion+" · "+pct(x.probabilidad)+
    " · justa "+dec(x.cuota_justa)).join("\n"):
   "   Sin selecciones publicadas para este filtro";
  return (page*perPage+i+1)+". "+showDate(m.fecha_utc)+" · "+
   title(m)+"\n"+lines;
 }).join("\n\n");
 return output("📊 Pronósticos publicados · "+headline+
  "\n\n"+summary+"\n\nPágina "+(page+1)+"/"+(last+1)+
  ". Las cuotas justas son estimaciones, NO ofertas reales. "+
  "Pulsa un partido para ver todos sus mercados.",rows);
}

export function interpret(text){
 const q=flat(text);
 if(!q||["start","menu","hola","inicio","buenas"].includes(q))return "menu";
 // Los comandos anteriores conservan su comportamiento y las consultas
 // compuestas no sustituyen las fuentes de cuotas o fiabilidad.
 if(/cuota|precio|1 50|bookmaker/.test(q))return "q";
 if(/resultado|acierto|calibracion|balance|fiabilidad|fallo/.test(q))return "results";
 const league=questionLeague(q),key=questionMarket(q);
 const day=/\bmanana\b/.test(q)?"tomorrow":/\bhoy\b/.test(q)?"today":"all";
 const wantsAnalysis=/analiz|analisis|pronostic|resumen|recomend|mejor/.test(q);
 if((league!=="all"&&(day!=="all"||key!=="all"||wantsAnalysis||
     /\b(partidos|jornada|segunda|primera|hypermotion)\b/.test(q)))||
    (day!=="all"&&(wantsAnalysis||key!=="all")))
  return ["nl",league,day,key,"0"].join(":");
 if(/ayuda|help/.test(q))return "help";
 if(/\bhoy\b/.test(q))return "today";
 if(/manana/.test(q))return "tomorrow";
 if(/cuota|precio|1 50|bookmaker/.test(q))return "q";
 if(/resultado|acierto|calibracion|balance|fiabilidad|fallo/.test(q))return "results";
 if(q==="ligas")return "leagues";
 if(q==="mercados")return "markets";
 const keys=[
  [/corn|corner/, "corners"],[/tiros a puerta/,"on_target"],
  [/tiros/,"shots"],[/amarilla|tarjeta/,"yellow"],
  [/doble oportunidad/,"double"],[/ambos marcan/,"btts"],
  [/goles|gol/,"goals"],[/empate|1x2/,"result"],
  [/faltas/,"fouls"],[/rojas/,"red"]
 ];
 for(const [regex,key] of keys)if(regex.test(q))return "k:"+key+":0";
 for(const [key,name] of LEAGUES)if(q===flat(name))return "l:"+key+":0";
 if(/partidos|proximos|siguientes|jornada/.test(q))return "p:0";
 return "search:"+q.slice(0,80);
}
function search(list,q){
 const query=flat(q);
 const words=query.split(/\s+/).filter(x=>x.length>=3&&![
  "analiza","analisis","partido","pronosticos","opciones","para","quiero",
  "entre","dame","ver","del","este"].includes(x));
 if(!words.length)return help();
 const found=list.filter(m=>words.every(w=>flat(m.local+" "+m.visitante).includes(w)));
 if(found.length===1)return fixtureCard(found[0]);
 return paged(found,0,"p","Partidos para: "+short(q,45));
}
export function reply(action,feeds={},now=new Date()){
 if(action==="menu")return menu();
 if(action==="help")return help();
 if(action==="leagues")return leagues();
 if(action==="markets")return markets();
 if(action==="results")return results(feeds.reliability||{});
 const source=feeds.forecast||{};
 if(!isFresh(source,now))return output("⚠️ No encuentro un pronóstico prepartido reciente.\n"+
  "Revisa GitHub Actions; no mostraré datos antiguos como actuales.",[base]);
 const list=upcoming(source,now),p=String(action).split(":");
 if(p[0]==="nl")return naturalDigest(list,action,now);
 if(action==="q")return odds(feeds.odds||{},now,null);
 if(action==="theory")return theory(list,null);
 if(action==="today"||action==="tomorrow"){
  const target=action==="today"?madridDay(now):nextDay(madridDay(now));
  return paged(list.filter(m=>madridDay(instant(m.fecha_utc))===target),0,"p",
   action==="today"?"Partidos de hoy":"Partidos de mañana");
 }
 if(p[0]==="p"&&p.length===2)return paged(list,p[1]);
 if(p[0]==="l"&&p.length===3&&LEAGUES.some(x=>x[0]===p[1]))
  return paged(list.filter(x=>x.liga===leg(p[1])),p[2],"l:"+p[1],leg(p[1]));
 if(p[0]==="k"&&p.length===3&&MARKETS.some(x=>x[0]===p[1]))
  return paged(list.filter(x=>Array.isArray(x.mercados?.[p[1]])&&x.mercados[p[1]].length),
   p[2],"k:"+p[1],market(p[1]));
 if(["f","q","c","t"].includes(p[0])&&p.length===2){
  const match=byCode(list,p[1]);
  if(!match)return output("Partido no disponible o ya comenzado.",[
   [bt("📅 Próximos","p:0")],base
  ]);
  if(p[0]==="f")return fixtureCard(match);
  if(p[0]==="q")return odds(feeds.odds||{},now,match);
  if(p[0]==="c")return context(match,feeds.dossier||{});
  return theory(list,match);
 }
 if(p[0]==="s"&&p.length===3&&MARKETS.some(x=>x[0]===p[1])){
  const match=byCode(list,p[2]);
  return match?selections(match,p[1]):output("Partido no disponible.",[base]);
 }
 if(action.startsWith("search:"))return search(list,action.slice(7));
 return help();
}
