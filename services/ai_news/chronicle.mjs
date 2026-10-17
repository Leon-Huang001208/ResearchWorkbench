// Local, traceable topic chronology through the original module contract; no generated history.
const iso=value=>value instanceof Date && Number.isFinite(value.getTime()) ? value.toISOString() : null;
export function chroniclePart(members,current,discovered=new Map(),topicSlug=null) {
  const chronicle=[];
  for(const member of members.slice(0,80)) {
    const row=current.get(member.id);
    if(!row || topicSlug && !row.topics?.includes(topicSlug))continue;
    const publishedAt=iso(row.publishedAt), occurredAt=row.scope==='composite' ? null : iso(row.factOccurredAt), collectedAt=iso(discovered.get(row.id));
    const at=occurredAt || publishedAt || collectedAt;
    if(!at)continue;
    chronicle.push({id:row.id,title:row.title,href:`/items/${encodeURIComponent(row.id)}`,at,publishedAt,occurredAt,collectedAt,timeKind:occurredAt?'event':publishedAt?'publication':'collection',provenance:{articleId:row.id,revision:row.revision,factId:row.factId ?? null},summary:occurredAt?'事件日期由当前报道的结构化事实提供。':'事件发生时间未确认，按已知报道时间列示。'});
  }
  chronicle.sort((a,b)=>Date.parse(b.at)-Date.parse(a.at)||a.id.localeCompare(b.id));
  return {status:'local_evidence',chronicle,limit:80,scope:'当前自主库中最近80条可公开精选报道；不是原站历史或模型生成的大事记。'};
}
export function chronologyModule(sql) {
  return {name:'chronicle',topics:{page:{
    async index(members) {
      const discovered=new Map();
      for(let offset=0;offset<members.length;offset+=500) {
        const ids=members.slice(offset,offset+500).map(row=>row.id);
        const rows=await sql`SELECT id, discovered_at FROM articles WHERE id = ANY(${ids}::text[])`;
        for(const row of rows)discovered.set(row.id,row.discovered_at);
      }
      return discovered;
    },
    read({members,index,topic}) {return {recheck:members.slice(0,80).map(row=>row.id),part:current=>chroniclePart(members,current,index,topic.slug)};},
  }}};
}
