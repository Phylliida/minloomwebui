// Word cloud for loom children
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

  // onProgress(done, total) called periodically, returns a promise
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
      // Yield every 20 texts so the browser can paint
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

  function cropCanvas(canvas, pad) {
    pad = pad || 20;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const img = ctx.getImageData(0, 0, w, h);
    const d = img.data;
    let top = h, left = w, bottom = 0, right = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (d[(y * w + x) * 4 + 3] > 0) {
          if (y < top) top = y;
          if (y > bottom) bottom = y;
          if (x < left) left = x;
          if (x > right) right = x;
        }
      }
    }
    if (bottom <= top || right <= left) return;
    top = Math.max(0, top - pad);
    left = Math.max(0, left - pad);
    bottom = Math.min(h - 1, bottom + pad);
    right = Math.min(w - 1, right + pad);
    const cw = right - left + 1, ch = bottom - top + 1;
    const cropped = ctx.getImageData(left, top, cw, ch);
    canvas.width = cw; canvas.height = ch;
    canvas.style.width = (cw * 2) + 'px'; canvas.style.height = (ch * 2) + 'px';
    ctx.putImageData(cropped, 0, 0);
  }

  function renderCloud(canvas, frequencies, fgColor) {
    if (typeof WordCloud === 'undefined' || !frequencies.length) return;
    const total = frequencies.reduce((s, [, c]) => s + c, 0);
    const list = frequencies.map(([w, c]) => [w, 100 * c / total]);

    // Reset to full size for rendering
    canvas.width = 4200; canvas.height = 2700;
    canvas.style.width = '4200px'; canvas.style.height = '2700px';
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    WordCloud(canvas, {
      list,
      weightFactor: 12,
      minSize: 1,
      gridSize: 8,
      backgroundColor: 'rgba(0,0,0,0)',
      color: () => fgColor || '#c4b5fd',
      rotateRatio: 0,
      shuffle: false,
      origin: [canvas.width / 2, canvas.height / 2],
      drawOutOfBound: false,
      fontFamily: '"Iosevka", "JetBrains Mono", monospace'
    });
    // wordcloud2 is async — listen for completion
    const onDone = () => {
      canvas.removeEventListener('wordcloudstop', onDone);
      cropCanvas(canvas, 24);
    };
    canvas.addEventListener('wordcloudstop', onDone);
  }

  window.LoomWordCloud = { splitWords, buildFrequencies, renderCloud };
})();
