// Word cloud for loom children — d3-cloud SVG version
(() => {
  const STOP_WORDS = new Set(
    'i,me,my,myself,we,our,ours,ourselves,you,your,yours,yourself,yourselves,he,him,his,himself,she,her,hers,herself,it,its,itself,they,them,their,theirs,themselves,what,which,who,whom,this,that,these,those,am,is,are,was,were,be,been,being,have,has,had,having,do,does,did,doing,a,an,the,and,but,if,or,because,as,until,while,of,at,by,for,with,about,against,between,into,through,during,before,after,above,below,to,from,up,down,in,out,on,off,over,under,again,further,then,once,here,there,when,where,why,how,all,any,both,each,few,more,most,other,some,such,no,nor,not,only,own,same,so,than,too,very,s,t,can,will,just,don,should,now,d,ll,m,o,re,ve,y,ain,aren,couldn,didn,doesn,hadn,hasn,haven,isn,ma,mightn,mustn,needn,shan,shouldn,wasn,weren,won,wouldn,also,would,could,said,like,one,know,get,go,well,way,got,much,even,make,say,think,see,come,take,want,give,use,find,tell,ask,seem,try,leave,call,keep,let,begin,show,hear,play,run,move,live,believe,hold,bring,happen,write,provide,sit,stand,lose,pay,meet,include,continue,set,learn,change,lead,understand,watch,follow,stop,create,speak,read,allow,add,spend,grow,open,walk,win,offer,remember,love,consider,appear,buy,wait,serve,die,send,expect,build,stay,fall,cut,reach,kill,remain,oh,im,thats,dont,ill,its,cant,didnt,hes,shes,youre,theyre,wont,isnt,ive,youve,id,heres,theres,whats,lets,whos,theyve,doesnt,wasnt,werent,havent,hasnt,hadnt,arent,couldnt,wouldnt,shouldnt,mustnt'
      .split(',')
  );

  const WORD_RE = /[a-zA-Z\u00C0-\u024F\u0400-\u04FF]+/g;

  function splitWords(text) {
    const words = [];
    let m;
    while ((m = WORD_RE.exec(text)) !== null) {
      const w = m[0].toLowerCase();
      if (w.length > 1 && !STOP_WORDS.has(w)) words.push(w);
    }
    WORD_RE.lastIndex = 0;
    return words;
  }

  async function buildFrequencies(texts, baseText, onProgress) {
    const freq = new Map();
    const baseWords = new Set(splitWords(baseText || ''));

    for (let i = 0; i < texts.length; i++) {
      const text = texts[i];
      const suffix = text.startsWith(baseText) ? text.slice(baseText.length) : text;
      for (const word of splitWords(suffix)) {
        if (baseWords.has(word)) continue;
        freq.set(word, (freq.get(word) || 0) + 1);
      }
      if (i % 20 === 19) {
        if (onProgress) onProgress(i + 1, texts.length);
        await new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));
      }
    }
    if (onProgress) onProgress(texts.length, texts.length);

    return [...freq.entries()]
      .filter(([, c]) => c > 1)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 150);
  }

  function renderCloud(container, frequencies, fgColor) {
    if (typeof d3 === 'undefined' || typeof d3.layout === 'undefined' || !frequencies.length) return;

    container.innerHTML = '';

    const maxCount = frequencies[0][1];
    const minCount = frequencies[frequencies.length - 1][1];
    const fontScale = d3.scaleSqrt()
      .domain([minCount, maxCount])
      .range([12, 72]);

    const words = frequencies.map(([text, count]) => ({
      text, count, size: fontScale(count)
    }));

    const W = 900, H = 600;

    const layout = d3.layout.cloud()
      .size([W, H])
      .words(words)
      .padding(4)
      .rotate(0)
      .font('"Iosevka", "JetBrains Mono", monospace')
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(placed) {
      // Compute tight bounding box
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const w of placed) {
        // Rough bounds: x,y is center of word, size is font size
        const halfW = w.text.length * w.size * 0.35;
        const halfH = w.size * 0.6;
        if (w.x - halfW < x0) x0 = w.x - halfW;
        if (w.x + halfW > x1) x1 = w.x + halfW;
        if (w.y - halfH < y0) y0 = w.y - halfH;
        if (w.y + halfH > y1) y1 = w.y + halfH;
      }
      const pad = 20;
      x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
      const vw = x1 - x0, vh = y1 - y0;

      const svg = d3.select(container).append('svg')
        .attr('viewBox', `${x0} ${y0} ${vw} ${vh}`)
        .style('width', '100%')
        .style('height', '100%');

      svg.append('g')
        .selectAll('text')
        .data(placed)
        .enter().append('text')
        .style('font-size', d => d.size + 'px')
        .style('font-family', d => d.font)
        .style('fill', fgColor || '#c4b5fd')
        .attr('text-anchor', 'middle')
        .attr('transform', d => `translate(${d.x},${d.y}) rotate(${d.rotate})`)
        .text(d => d.text);
    }
  }

  window.LoomWordCloud = { splitWords, buildFrequencies, renderCloud };
})();
