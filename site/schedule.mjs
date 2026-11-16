/** Orden prepartido prioritario: el evento que empieza antes aparece primero.
 * En vista "Todos", los finalizados quedan al final (más reciente primero).
 * Orden estable por ID en empates y timestamps malformados al final.
 */
const kickoffMs = row => {
  const t=typeof row?.kickoff==="number" ? row.kickoff : Date.parse(row?.fecha_utc);
  return Number.isFinite(t) ? t : Number.POSITIVE_INFINITY;
};
const byId = (a,b) => String(a?.id??"").localeCompare(String(b?.id??""),"es");

export function orderMatchesByKickoff(rows, now=new Date(), period="all") {
  const cutoff=now instanceof Date?now.getTime():Number(now);
  const boundary=Number.isFinite(cutoff)?cutoff:Date.now();
  return [...rows].sort((a,b)=>{
    const ta=kickoffMs(a),tb=kickoffMs(b);
    if(ta===Number.POSITIVE_INFINITY || tb===Number.POSITIVE_INFINITY){
      if(ta!==tb)return ta===Number.POSITIVE_INFINITY?1:-1;
      return byId(a,b);
    }
    if(period==="past")return tb-ta||byId(a,b);
    if(period==="next")return ta-tb||byId(a,b);
    const af=ta>boundary,bf=tb>boundary;
    if(af!==bf)return af?-1:1;
    return (af?ta-tb:tb-ta)||byId(a,b);
  });
}
