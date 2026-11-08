function paragraphRows(source) {
  const paragraphs=String(source).replace(/\r\n?/g,'\n').split(/\n[\t ]*\n(?:[\t ]*\n)*/).map(p=>p.trim()).filter(Boolean);
  if(!paragraphs.length)throw new Error('Paste at least one paragraph first.');
  if(paragraphs.length>100)throw new Error('This batch supports up to 100 clips. Split the source into smaller batches; your text has not been changed.');
  let ticks=500;
  return paragraphs.map((text,index)=>{
    const count=Array.from(text).length;
    if(count>2000)throw new Error(`Paragraph ${index+1} exceeds the 2,000-character clip limit. Add a blank line to split it; your text has not been changed.`);
    const seconds=Math.round(ticks/100);
    const result={minutes:Math.floor(seconds/60),seconds:seconds%60,text};
    ticks+=count*8;
    return result;
  });
}
