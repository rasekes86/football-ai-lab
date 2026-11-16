/** Explorador de jornadas: cálculos puros, sin API ni dependencias externas. */
export const AGENDA_LEAGUES = [
  {name:"LaLiga", country:"ESPAÑA",flag:"🇪🇸",label:"LaLiga EA Sports"},
  {name:"Segunda División",country:"ESPAÑA",flag:"🇪🇸",label:"LaLiga Hypermotion"},
  {name:"Premier League",country:"INGLATERRA",flag:"🇬🇧",label:"Premier League"},
  {name:"Bundesliga",country:"ALEMANIA",flag:"🇩🇪",label:"Bundesliga"},
  {name:"Serie A",country:"ITALIA",flag:"🇮🇹",label:"Serie A"},
  {name:"Ligue 1",country:"FRANCIA",flag:"🇫🇷",label:"Ligue 1"}
];
const dayParts = new Intl.DateTimeFormat("en-GB",{
  timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"
});
export function madridDateKey(value){
  const time = value instanceof Date ? value.getTime() : typeof value === "number" ? value : Date.parse(value);
  if(!Number.isFinite(time))return "";
  const parts=Object.fromEntries(dayParts.formatToParts(new Date(time)).map(x=>[x.type,x.value]));
  return parts.year+"-"+parts.month+"-"+parts.day;
}
export function agendaDays(now=Date.now(),before=1,after=13){
  const today=madridDateKey(now);
  if(!today)return [];
  const [year,month,day]=today.split("-").map(Number);
  return Array.from({length:before+after+1},(_,i)=>{
    const date=new Date(Date.UTC(year,month-1,day+i-before,12));
    return {
      key:date.toISOString().slice(0,10),
      date,
      today:i===before,
      weekday:new Intl.DateTimeFormat("es-ES",{timeZone:"UTC",weekday:"short"}).format(date).replace(".","").toUpperCase(),
      label:new Intl.DateTimeFormat("es-ES",{timeZone:"UTC",day:"2-digit",month:"2-digit"}).format(date)
    };
  });
}
export function agendaSelection(matches,day="upcoming",query="",now=Date.now()){
  const normalized=String(query).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("es").trim();
  const filtered=(matches||[]).filter(m=>{
    const kickoff=Number(m.kickoff);
    if(!Number.isFinite(kickoff))return false;
    if(day==="upcoming"){
      if(kickoff<=now||kickoff-now>14*86400000)return false;
    }else if(madridDateKey(kickoff)!==day)return false;
    if(normalized){
      const haystack=[m.local,m.visitante,m.liga].join(" ")
        .normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("es");
      if(!haystack.includes(normalized))return false;
    }
    return true;
  });
  return filtered.sort((a,b)=>a.kickoff-b.kickoff||String(a.id).localeCompare(String(b.id),"es"));
}
export function agendaGroups(matches){
  const grouped=new Map();
  for(const m of matches||[]){
    const name=String(m.liga||"Otra competición");
    if(!grouped.has(name))grouped.set(name,[]);
    grouped.get(name).push(m);
  }
  return [...grouped.entries()].sort((a,b)=>{
    const i=AGENDA_LEAGUES.findIndex(l=>l.name===a[0]),j=AGENDA_LEAGUES.findIndex(l=>l.name===b[0]);
    return (i<0?999:i)-(j<0?999:j)||a[0].localeCompare(b[0],"es");
  }).map(([name,games])=>({
    name,games,
    meta:AGENDA_LEAGUES.find(l=>l.name===name)||{name,country:"OTRAS COMPETICIONES",flag:"⚽",label:name}
  }));
}
