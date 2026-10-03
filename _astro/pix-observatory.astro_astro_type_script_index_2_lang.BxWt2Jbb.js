var e=document.body.dataset.baseurl??``;function t(e){let t=Math.abs(e);return t>=1e6?`${(e/1e6).toFixed(1).replace(`.`,`,`)}M`:t>=1e3?`${(e/1e3).toFixed(1).replace(`.`,`,`)}mil`:String(e)}function n(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function r(e){if(!e)return``;let t=new Date(e);return Number.isNaN(t.getTime())?``:t.toLocaleDateString(`pt-BR`,{month:`short`,year:`numeric`})}function i(e){return e.map(e=>`
          <li class="ranking-row${e.rank<=3?` ranking-row--podium`:``}" role="listitem">
            <span class="ranking-row__rank" aria-hidden="true">${e.rank}</span>
            <span class="ranking-row__name" title="${n(e.nome)}">${n(e.nome)}</span>
            <span class="ranking-row__value">
              <span class="ranking-row__value-main">${t(e.chaves)}</span>
            </span>
          </li>`).join(``)}function a(e){return e.map(e=>{let r=e.rank<=3?` ranking-row--podium`:``,i=e.crescimento_absoluto>=0,a=i?``:` ranking-row__value-delta--neg`,o=i?`+`:``;return`
          <li class="ranking-row${r}" role="listitem">
            <span class="ranking-row__rank" aria-hidden="true">${e.rank}</span>
            <span class="ranking-row__name" title="${n(e.nome)}">${n(e.nome)}</span>
            <span class="ranking-row__value">
              <span class="ranking-row__value-main">${o}${t(e.crescimento_absoluto)}</span>
              <span class="ranking-row__value-delta${a}">${o}${e.crescimento_pct.toFixed(1).replace(`.`,`,`)}%</span>
            </span>
          </li>`}).join(``)}async function o(){let t=document.getElementById(`ranking-historico-list`),n=document.getElementById(`ranking-recente-list`),o=document.getElementById(`ranking-footnote`);if(!t||!n)return;let s=new AbortController,c=setTimeout(()=>s.abort(),8e3);try{let l=await fetch(`${e}assets/data/pix_ranking.json`,{cache:`no-cache`,signal:s.signal});if(clearTimeout(c),!l.ok)throw Error(`fetch failed`);let u=await l.json(),d=u.historico??[],f=u.recente??[];if(t.innerHTML=d.length?i(d):`<li class="ranking-error mono-label">sem dados no momento</li>`,n.innerHTML=f.length?a(f):`<li class="ranking-error mono-label">sem dados de comparação disponíveis</li>`,o){let e=r(u.snapshot_recente),t=r(u.snapshot_comparacao);o.textContent=`fonte: BACEN Olinda API · Pix_DadosAbertos / ChavesPix${t&&e?` · ${t} → ${e}`:``}`}}catch{clearTimeout(c);let e=`<li class="ranking-error mono-label">ranking indisponível — tente recarregar</li>`;t.innerHTML=e,n.innerHTML=e}}document.addEventListener(`astro:page-load`,o);