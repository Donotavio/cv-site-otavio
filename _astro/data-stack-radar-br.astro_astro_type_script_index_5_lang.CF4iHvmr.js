function e(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function t(t){let n=document.getElementById(`radar-context-grid`);if(n){if(!t.length){n.innerHTML=`<p class="ranking-error mono-label">contexto indisponível</p>`;return}n.innerHTML=t.map(t=>`
      <div class="card radar-context-item" role="listitem">
        <span class="mono-label radar-context-item__eyebrow">${e(t.titulo)}${t.periodo?` · ${e(t.periodo)}`:``}</span>
        <span class="radar-context-item__value">${e(t.valor)}</span>
        <p class="radar-context-item__desc">${e(t.descricao)}</p>
        <a class="link-underline radar-context-item__source" href="${e(t.fonte_url)}" target="_blank" rel="noopener noreferrer"
           aria-label="Fonte: ${e(t.fonte)} (abre em nova aba)">${e(t.fonte)} ↗</a>
      </div>`).join(``)}}function n(t,n){return t?n.map(t=>`<span class="tag">${e(t)}</span>`).join(``):``}function r(t){let r=document.getElementById(`radar-context-profissoes`);if(!r)return;if(!t){r.innerHTML=`<p class="ranking-error mono-label">indisponível</p>`;return}let i=t.agora??[],a=t.futuro??[];r.innerHTML=`
      <p class="radar-context-card__sub mono-label">agora</p>
      <div class="radar-context-card__tags">${n(r,i)}</div>
      <p class="radar-context-card__sub mono-label">estratégicas para o futuro</p>
      <div class="radar-context-card__tags">${n(r,a)}</div>
      <a class="link-underline radar-context-item__source" href="${e(t.fonte_url)}" target="_blank" rel="noopener noreferrer"
         aria-label="Fonte: ${e(t.fonte)} (abre em nova aba)">${e(t.fonte)} ↗</a>`}function i(t){let r=document.getElementById(`radar-context-competencias`);if(r){if(!t){r.innerHTML=`<p class="ranking-error mono-label">indisponível</p>`;return}r.innerHTML=`
      <div class="radar-context-card__tags">${n(r,t.itens??[])}</div>
      <a class="link-underline radar-context-item__source" href="${e(t.fonte_url)}" target="_blank" rel="noopener noreferrer"
         aria-label="Fonte: ${e(t.fonte)} (abre em nova aba)">${e(t.fonte)} ↗</a>`}}async function a(){let e=document.body.dataset.baseurl??``,n=new AbortController,a=setTimeout(()=>n.abort(),8e3);try{let o=await fetch(`${e}assets/data/radar_contexto.json`,{cache:`no-cache`,signal:n.signal});if(clearTimeout(a),!o.ok)throw Error(`fetch failed`);let s=await o.json();t(s.blocos??[]),r(s.profissoes_mais_demandadas),i(s.competencias_estrategicas)}catch{clearTimeout(a);let e=document.getElementById(`radar-context-grid`);e&&(e.innerHTML=`<p class="ranking-error mono-label">contexto indisponível</p>`),[`radar-context-profissoes`,`radar-context-competencias`].forEach(e=>{let t=document.getElementById(e);t&&(t.innerHTML=`<p class="ranking-error mono-label">indisponível</p>`)})}}document.addEventListener(`astro:page-load`,()=>{document.getElementById(`radar-hero`)&&a()});