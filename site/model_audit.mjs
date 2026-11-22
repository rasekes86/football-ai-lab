/** Auditoría de selecciones archivadas: lectura pura, sin reentrenar ni recotizar. */
import {settled,numberOrNull} from './data.mjs';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=x=>x===null?'—':(100*x).toLocaleString('es-ES',{maximumFractionDigits:1})+' %';
const zero=()=>({n:0,hits:0,brier:0,expected:0});
function track(obj,p,y){
  obj.n++;obj.hits+=y;obj.brier+=(p-y)**2;obj.expected+=p;
}
const finish=x=>({...x,accuracy:x.n?x.hits/x.n:null,
  avgProbability:x.n?x.expected/x.n:null,brier:x.n?x.brier/x.n:null});
export function modelAudit(model={},opts={}){
  const now=opts.at instanceof Date?opts.at:new Date();
  const range=[30,90,365].includes(Number(opts.range))?Number(opts.range):null;
  const cutoff=range?now.getTime()-range*86400000:0;
  const origin=new Map(),bucket=new Map();
  const all=Array.isArray(model.archivedPicks)?model.archivedPicks:[];
  const valid=all.filter(row=>{
    if(opts.league&&row.liga!==opts.league)return false;
    if(!settled(row))return false;
    const date=Date.parse(row.fecha_utc||'');
    return Number.isFinite(date)&&date<=now.getTime()&&date>=cutoff;
  });
  let skipped=0;
  for(const row of valid){
    const p=numberOrNull(row.probabilidad);
    if(p===null||p<0||p>1){skipped++;continue;}
    const y=row.resultado==='1'?1:0;
    const o=String(row.origen||'Sin origen');
    const b=p<.6?'Menos del 60 %':p<.7?'60–69 %':p<.8?'70–79 %':p<.9?'80–89 %':'90–100 %';
    if(!origin.has(o))origin.set(o,zero());
    if(!bucket.has(b))bucket.set(b,zero());
    track(origin.get(o),p,y);track(bucket.get(b),p,y);
  }
  const sort=m=>[...m].map(([name,m])=>({name,...finish(m)}))
    .sort((a,b)=>b.n-a.n||a.name.localeCompare(b.name));
  const sum=zero();for(const row of origin.values()){
    sum.n+=row.n;sum.hits+=row.hits;sum.brier+=row.brier;sum.expected+=row.expected;
  }
  return {total:finish(sum),byOrigin:sort(origin),byBucket:sort(bucket),
    skipped,range:range||'all',league:opts.league||'',quoteCoverage:model.top3QuoteAudit?.con_cuota_observada??null,
    quoteTotal:model.top3QuoteAudit?.selecciones_originales??null};
}
function detail(row){
  const tentative=row.n<30?'Muestra pequeña · solo descriptivo':'Muestra aún experimental';
  return '<div class="model-audit-row"><span><strong>'+esc(row.name)+'</strong><small>'+
    row.n+' comprobadas · '+esc(tentative)+'</small></span><span><b>'+
    fmt(row.accuracy)+'</b><small>Estimado '+fmt(row.avgProbability)+
    ' · Brier '+(row.brier===null?'—':row.brier.toFixed(3))+'</small></span></div>';
}
export function renderModelAudit(view={}){
  const x=view.total||finish(zero());
  const summary='<div class="model-audit-head"><strong>'+
    x.hits+' / '+x.n+' · '+fmt(x.accuracy)+'</strong><small>Probabilidad media archivada '+
    fmt(x.avgProbability)+' · Brier '+(x.brier===null?'—':x.brier.toFixed(3))+
    ' · '+view.skipped+' descartadas por probabilidad inválida</small></div>';
  const origin=view.byOrigin?.length?view.byOrigin.map(detail).join(''):'<p>Sin muestra verificada.</p>';
  const bands=view.byBucket?.length?view.byBucket.map(detail).join(''):'<p>Sin muestra verificada.</p>';
  const pricing='<p class="fine-print">Cobertura de cuota exacta del Top 3: '+
    (view.quoteCoverage===null?'sin diagnóstico publicado':view.quoteCoverage+' de '+view.quoteTotal)+
    '. No se mezclan cuotas justas con precios de bookmaker. No se añade ninguna selección exploratoria al balance.</p>';
  return {summary,origin,bands,pricing};
}
export function analysisHealth(when,errors=[],at=new Date()){
  const time=Date.parse(when||'');
  const age=Number.isFinite(time)?(at.getTime()-time)/3600000:null;
  return {age,status:age===null?'UNKNOWN':age>24?'STALE':errors.length?'PARTIAL':'OK',
    failed:errors.length,when:when||null};
}
export function renderAnalysisHealth(state){
  const fmtDate=v=>v?new Intl.DateTimeFormat('es-ES',{
    timeZone:'Europe/Madrid',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'
  }).format(new Date(v)):'—';
  return '<div class="football-health '+(state.status==='OK'?'':'football-health-alert')+
    '" role="status"><strong>'+(state.status==='STALE'?'Datos con más de 24 horas':
    state.status==='PARTIAL'?'Fuentes incompletas':state.status==='UNKNOWN'?'Fecha sin verificar':
    'Datos publicados')+'</strong><span>Análisis: '+esc(fmtDate(state.when))+
    ' · '+state.failed+' fuentes sin respuesta. Los horarios previstos de GitHub no garantizan ejecución.</span></div>';
}
