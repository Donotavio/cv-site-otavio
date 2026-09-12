var e=document.body.dataset.baseurl??``;function t(e){if(!e)return``;let t=new Date(e).getTime();if(Number.isNaN(t))return``;let n=Date.now()-t,r=Math.floor(n/864e5);if(r<=0)return`hoje`;if(r===1)return`ontem`;if(r<7)return`há ${r} dias`;let i=Math.floor(r/7);if(i<5)return`há ${i} sem`;let a=Math.floor(r/30);return`há ${a} ${a===1?`mês`:`meses`}`}function n(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}async function r(){let r=document.getElementById(`pix-news-list`),i=document.querySelector(`[data-news-updated]`);if(!r)return;let a=new AbortController,o=setTimeout(()=>a.abort(),8e3);try{let s=await fetch(`${e}assets/data/pix_news.json`,{cache:`no-cache`,signal:a.signal});if(clearTimeout(o),!s.ok)throw Error(`fetch failed`);let c=await s.json(),l=c.items??[];if(!l.length){r.innerHTML=`<li class="pix-news__error mono-label">sem notícias no momento</li>`;return}r.innerHTML=l.map(e=>{let r=t(e.published),i=e.source?n(e.source):`Fonte`,a=r?`<span class="pix-news__time"><span aria-hidden="true">◷</span>${r}</span>`:``;return`
            <li class="pix-news__item" role="listitem">
              <a class="pix-news__link" href="${n(e.url)}"
                 target="_blank" rel="noopener noreferrer"
                 aria-label="${n(e.title)} — ${i}${r?`, `+r:``}">
                <span class="pix-news__index mono-label" aria-hidden="true"></span>
                <span class="pix-news__content">
                  <span class="pix-news__headline">${n(e.title)}</span>
                  <span class="pix-news__meta">
                    <span class="pix-news__source" title="${i}">${i}</span>
                    ${a}
                  </span>
                </span>
              </a>
            </li>`}).join(``),i&&c.updated_at&&(i.textContent=`Google News · ${t(c.updated_at)||`atualizado`}`)}catch{clearTimeout(o),r.innerHTML=`<li class="pix-news__error mono-label">feed indisponível — tente recarregar</li>`}}document.addEventListener(`astro:page-load`,r);