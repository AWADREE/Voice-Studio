// Plan with integer audio frames; decimals only transport the resulting starts.
function sequentialClipRows(rows, timing){
  if(timing?.error)throw Error(timing.error);
  const clips=timing?.clips;
  if(!Array.isArray(rows)||!rows.length||!Array.isArray(clips)||clips.length!==rows.length)
    throw Error('Generate every current paragraph before setting timestamps. Previous clips must match the editor.');
  const byId=new Map(clips.map(clip=>[clip.id,clip]));
  if(byId.size!==clips.length||new Set(rows.map(row=>row.id)).size!==rows.length)
    throw Error('The generated clips no longer match the editor. Generate them again.');
  const rate=clips[0].sample_rate;
  if(!Number.isSafeInteger(rate)||rate<=0)throw Error('The generated sample rate is unavailable.');
  for(const row of rows){
    const clip=byId.get(row.id);
    if(!row.id||!clip||typeof row.text!=='string'||clip.text!==row.text.trim())
      throw Error('A paragraph was changed, added or removed. Generate the current clips before setting timestamps.');
    if(clip.sample_rate!==rate)throw Error('All clips must have the same sample rate.');
    if(!Number.isSafeInteger(clip.frames)||clip.frames<=0)throw Error('A generated audio duration is unavailable.');
  }
  const first=rows[0];
  if(!Number.isInteger(first.minutes)||first.minutes<0||first.minutes>9999||!Number.isFinite(first.seconds)||first.seconds<0||first.seconds>=60)
    throw Error('Enter a valid timestamp for the first paragraph.');
  let frame=Math.round((first.minutes*60+first.seconds)*rate);
  const result=rows.map((row,index)=>{
    const next={...row};
    if(index){next.minutes=Math.floor(frame/(60*rate));next.seconds=(frame-next.minutes*60*rate)/rate;}
    frame+=byId.get(row.id).frames;
    if(!Number.isSafeInteger(frame)||frame>24*60*60*rate)throw Error('The clips exceed the 24-hour timeline limit.');
    return next;
  });
  return result;
}
