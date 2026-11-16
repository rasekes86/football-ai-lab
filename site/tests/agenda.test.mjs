import test from "node:test";
import assert from "node:assert/strict";
import {AGENDA_LEAGUES,agendaDays,madridDateKey,agendaSelection,agendaGroups} from "../agenda.mjs";

const matches=[
 {id:"two",kickoff:Date.parse("2026-11-17T20:00:00Z"),liga:"Segunda División",local:"Tenerife",visitante:"Ceuta"},
 {id:"one",kickoff:Date.parse("2026-11-17T12:00:00Z"),liga:"LaLiga",local:"Betis",visitante:"Getafe"},
 {id:"next",kickoff:Date.parse("2026-11-18T18:00:00Z"),liga:"Premier League",local:"Arsenal",visitante:"Chelsea"},
 {id:"old",kickoff:Date.parse("2026-11-16T12:00:00Z"),liga:"Bundesliga",local:"Bayern",visitante:"Dortmund"}
];
const now=Date.parse("2026-11-17T09:00:00Z");

test("Madrid days have stable keys, today and sorted dates",()=>{
 const days=agendaDays(now,1,13);
 assert.equal(days.length,15);
 assert.equal(days[1].key,"2026-11-17");
 assert.equal(days[1].today,true);
 assert.equal(days[2].key,"2026-11-18");
 assert.equal(days[0].key,"2026-11-16");
});
test("Spain time zone day keys handle winter and summer midnight boundaries",()=>{
 assert.equal(madridDateKey("2026-11-16T23:30:00Z"),"2026-11-17");
 assert.equal(madridDateKey("2026-07-01T22:30:00Z"),"2026-07-02");
 assert.equal(madridDateKey("nonsense"),"");
});
test("upcoming filters old games and sorts by kickoff",()=>{
 assert.deepEqual(agendaSelection(matches,"upcoming","",now).map(x=>x.id),["one","two","next"]);
 assert.deepEqual(agendaSelection(matches,"2026-11-17","",now).map(x=>x.id),["one","two"]);
});
test("free-text search is accent insensitive and does not invent fixtures",()=>{
 assert.deepEqual(agendaSelection(matches,"upcoming","segunda",now).map(x=>x.id),["two"]);
 assert.deepEqual(agendaSelection(matches,"upcoming","arSENAL",now).map(x=>x.id),["next"]);
 assert.equal(agendaSelection(matches,"upcoming","Madrid",now).length,0);
});
test("group labels and ordering are grounded in the six configured leagues",()=>{
 const grouped=agendaGroups(matches.slice(0,3));
 assert.deepEqual(grouped.map(x=>x.name),["LaLiga","Segunda División","Premier League"]);
 assert.equal(grouped[1].meta.label,"LaLiga Hypermotion");
 assert.equal(AGENDA_LEAGUES.length,6);
});
