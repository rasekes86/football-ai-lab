import test from 'node:test';
import assert from 'node:assert/strict';
import {modelAudit,renderModelAudit,analysisHealth,renderAnalysisHealth} from '../model_audit.mjs';

const at=new Date('2026-11-22T12:00:00Z');
const base={id:'A',liga:'LaLiga',fecha_utc:'2026-11-21T15:00:00Z',
  origen:'Poisson de goles',estado:'FINALIZADO',resultado:'1',probabilidad:'0.80'};
test('audits exclusively settled original Top 3, no prospective mutation',()=>{
  const model={archivedPicks:[base,{...base,id:'B',resultado:'0',probabilidad:'0.60'},
    {...base,id:'C',estado:'PENDIENTE',resultado:'',probabilidad:'0.99'},
    {...base,id:'D',origen:'XGBoost',liga:'Serie A'}],
    allOdds:[{resultado:'1',cuota_decimal:'90'}]};
  const before=JSON.stringify(model);
  const audit=modelAudit(model,{at,league:'LaLiga',range:30});
  assert.equal(audit.total.n,2);
  assert.equal(audit.total.hits,1);
  assert.ok(Math.abs(audit.total.brier-.20)<1e-9);
  assert.equal(audit.byOrigin.length,1);
  assert.equal(JSON.stringify(model),before);
  assert.match(renderModelAudit(audit).pricing,/sin diagnóstico/);
});
test('does not treat missing, invalid, old, or pending data as losses',()=>{
  const model={archivedPicks:[{...base,probabilidad:'no'},
    {...base,id:'past',fecha_utc:'2025-11-21T00:00:00Z',resultado:'0'},
    {...base,id:'pending',estado:'PENDIENTE',resultado:'0'},
    {...base,id:'future',fecha_utc:'2026-11-23T00:00:00Z',resultado:'0'}]};
  const x=modelAudit(model,{at,range:30});
  assert.equal(x.total.n,0);
  assert.equal(x.skipped,1);
});
test('displays source age separately from actual Github cron runs',()=>{
  const h=analysisHealth('2026-11-20T00:00:00Z',[],at);
  assert.equal(h.status,'STALE');
  assert.match(renderAnalysisHealth(h),/más de 24 horas/);
  assert.match(renderAnalysisHealth(h),/no garantizan ejecución/);
});
