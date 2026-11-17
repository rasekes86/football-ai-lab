import test from "node:test";
import assert from "node:assert/strict";
import {homeSnapshot,renderHomeView} from "../home.mjs";

const NOW=new Date("2026-11-17T16:00:00Z");
const future="2026-11-21T18:00:00Z",past="2026-11-15T18:00:00Z";
function game(id,date=future){
  return {id,liga:"LaLiga",local:"Sevilla",visitante:"Betis",
    fecha_utc:date,kickoff:Date.parse(date),score:"",
    picks:[],odds:[]};
}
function top(m,number=1,resultado="",estado="PENDIENTE"){
  return {id:m.id,clave:m.id+"|top"+number,liga:m.liga,
    fecha_utc:m.fecha_utc,archivado_utc:"2026-11-14T08:00:00Z",
    mercado:"1X2",seleccion:"Sevilla gana",
    probabilidad:"0.67",estado,resultado};
}
function odd(m,price="1.90",estado="PENDIENTE",resultado=""){
  return {id:m.id,clave:m.id+"|extra",liga:m.liga,
    fecha_utc:m.fecha_utc,archivado_utc:"2026-11-14T08:00:00Z",
    mercado:"Total goles",seleccion:"Menos de 2,5 goles",
    cuota_decimal:price,tipo_cuota:"OFRECIDA_API_REGISTRADA",
    estado,resultado};
}
const crest=()=>'<span class="test-crest"></span>';

test("home sorts upcoming chronologically and restricts to four cards",()=>{
  const futures=Array.from({length:7},(_,i)=>game("match-"+i,
    new Date(Date.parse(future)+i*3600*1000).toISOString())).reverse();
  const x=homeSnapshot({futureMatches:futures,matches:futures},NOW);
  assert.equal(x.futureCount,7);
  assert.deepEqual(x.next.map(m=>m.id),["match-0","match-1","match-2","match-3"]);
});
test("home displays only frozen Top3 plus one additional and never exploratory",()=>{
  const m=game("real");
  m.picks=[top(m,1),top(m,2),top(m,3)];
  m.odds=[odd(m)];
  const data={futureMatches:[m],matches:[m],
    archivedPicks:m.picks,allOdds:m.odds,updatedAt:NOW.toISOString()};
  const page=renderHomeView(data,crest,NOW);
  assert.equal(page.counts.future,1);
  assert.equal(page.counts.extraPending,1);
  assert.match(page.upcoming,/Menos de 2,5 goles/);
  assert.match(page.upcoming,/Ver Top 3 archivado \(3\)/);
  assert.match(page.upcoming,/data-open-id="real"/);
  assert.doesNotMatch(page.upcoming,/Explorar mercados/);
  assert.match(page.stats,/ADICIONALES PENDIENTES/);
});
test("future data never uses settled past as future selection",()=>{
  const earlier=game("past",past);
  const upcoming=game("future");
  const x=homeSnapshot({futureMatches:[earlier,upcoming],
    matches:[earlier,upcoming]},NOW);
  assert.deepEqual(x.next.map(m=>m.id),["future"]);
});
test("recent settled cards count hits without marking pending as failure",()=>{
  const m=game("recent",past);
  m.picks=[top(m,1,"1","FINALIZADO"),top(m,2,"0","FINALIZADO"),
           top(m,3,"","ESTADISTICA_NO_DISPONIBLE")];
  m.odds=[odd(m,"2.30","PENDIENTE","")];
  const x=renderHomeView({futureMatches:[],matches:[m],
    archivedPicks:m.picks,allOdds:m.odds},crest,NOW);
  assert.match(x.recent,/1\/2/);
  assert.equal(x.counts.topSettled,2);
  assert.equal(x.counts.extraSettled,0);
});
test("no prices invented when missing: show explicit absence",()=>{
  const m=game("missing");
  const x=renderHomeView({futureMatches:[m],matches:[m]},crest,NOW);
  assert.match(x.upcoming,/Sin adicional archivada/);
  assert.match(x.upcoming,/Top 3 todavía no archivado/);
  assert.doesNotMatch(x.upcoming,/1.90/);
  assert.match(x.stats,/—/);
});
test("untrusted strings escaped within homepage, not executable markup",()=>{
  const m=game('<img src=x onerror=alert(1)>');
  m.local="<script>bad</script>";
  m.odds=[odd(m)];
  const x=renderHomeView({futureMatches:[m],matches:[m],allOdds:m.odds},
    ()=>"",NOW);
  assert.doesNotMatch(x.upcoming,/<script>/);
  assert.doesNotMatch(x.upcoming,/<img src=x/);
  assert.match(x.upcoming,/&lt;script&gt;/);
});
