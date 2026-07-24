import{c as e,s as t}from"./cleanup.D2ntGW1D.js";import{t as n}from"./reveal-up.C1zAozKf.js";var r=[`Adopt`,`Trial`,`Assess`,`Hold`],i={Adopt:`var(--radar-adopt)`,Trial:`var(--radar-trial)`,Assess:`var(--radar-assess)`,Hold:`var(--radar-hold)`};function a(e){return`<span class="ui-bar"><span class="ui-bar__fill" style="inline-size:${Math.max(0,Math.min(100,e))}%"></span></span>`}function o(e){return e.toFixed(1).replace(`.`,`,`)}function s(e){return Math.round(e).toLocaleString(`pt-BR`)}function c(e){return e>=1e6?`${(e/1e6).toFixed(1).replace(`.`,`,`)}M`:e>=1e3?`${(e/1e3).toFixed(1).replace(`.`,`,`)}mil`:String(e)}function l(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function u(e){let t=document.getElementById(`radar-hero-week`);t&&e.janelas?.jobs_semana&&(t.textContent=e.janelas.jobs_semana)}function d(r){let a=document.getElementById(`radar-dots`);if(!a)return;let o=`http://www.w3.org/2000/svg`,s=[];r.forEach(e=>{let t=56+e.job_score/100*560,n=584-e.github_score/100*560,r=4+e.pypi_score/100*10,c=i[e.quadrant]??`var(--ink-faint)`,l=document.createElementNS(o,`circle`);if(l.setAttribute(`cx`,t.toFixed(1)),l.setAttribute(`cy`,n.toFixed(1)),l.setAttribute(`r`,r.toFixed(1)),l.setAttribute(`data-tool`,e.tool),l.style.fill=c,l.style.stroke=`var(--paper-card)`,l.style.strokeWidth=`1.5`,a.appendChild(l),s.push(l),e.total_score>60){let r=document.createElementNS(o,`text`);r.setAttribute(`x`,(t+8).toFixed(1)),r.setAttribute(`y`,(n-6).toFixed(1)),r.setAttribute(`class`,`radar-dot-label`),r.textContent=e.tool,a.appendChild(r),s.push(r)}}),e&&s.length&&n(s,document.getElementById(`radar-chart-block`)??a,t.tight)}function f(e){let t=document.getElementById(`radar-tier-legend`);if(!t)return;let n={Adopt:0,Trial:0,Assess:0,Hold:0};e.forEach(e=>{e.quadrant in n&&(n[e.quadrant]+=1)}),t.innerHTML=r.map(e=>`<li class="radar-tier-chip" data-tier="${e.toLowerCase()}">${e} · ${n[e]}</li>`).join(``)}function p(i){let s=document.getElementById(`ranking-tools-list`);if(!s)return;let c=[...i].sort((e,t)=>t.total_score-e.total_score);if(s.innerHTML=r.map(e=>{let t=c.filter(t=>t.quadrant===e);if(!t.length)return``;let n=t.map((t,n)=>`
          <li class="radar-tool-row" data-tier="${e.toLowerCase()}">
            <div class="radar-tool-row__top">
              <span class="radar-tool-row__rank mono-label" aria-hidden="true">${String(n+1).padStart(2,`0`)}</span>
              <span class="radar-tool-row__name">${l(t.tool)}</span>
              <span class="tag radar-tool-row__category">${l(t.category)}</span>
              <span class="tag radar-tool-row__tier-badge" data-tier="${e.toLowerCase()}">${e}</span>
            </div>
            <div class="radar-tool-row__meter-row">
              <span class="radar-tool-row__meter" data-tier="${e.toLowerCase()}" aria-hidden="true">${a(t.total_score)}</span>
              <span
                class="radar-tool-row__score"
                role="meter"
                aria-valuenow="${t.total_score}"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-label="${l(t.tool)}: score total ${o(t.total_score)} de 100, quadrante ${e}, categoria ${l(t.category)}"
              >${o(t.total_score)}</span>
            </div>
          </li>`).join(``);return`
        <div class="radar-tier-block" data-tier="${e.toLowerCase()}">
          <h3 class="radar-tier-block__head mono-label" data-tier="${e.toLowerCase()}">${e} · ${t.length}</h3>
          <ol class="radar-tool-list" role="list">${n}</ol>
        </div>`}).join(``),e){let e=s.querySelectorAll(`.radar-tier-block`);e.length&&n(e,s,t.tight)}}function m(r){let i=document.getElementById(`radar-breakdown-grid`);if(i&&(i.innerHTML=[...r].sort((e,t)=>t.total_score-e.total_score).map(e=>{let t=e.quadrant.toLowerCase();return`
        <article class="card radar-breakdown-card" data-tier="${t}">
          <header class="radar-breakdown-card__head">
            <span class="radar-breakdown-card__name">${l(e.tool)}</span>
            <span class="tag radar-breakdown-card__tier" data-tier="${t}">${e.quadrant}</span>
          </header>
          <ul class="radar-breakdown-card__meters">
            <li class="radar-breakdown-meter">
              <span class="radar-breakdown-meter__label mono-label">vagas</span>
              <span class="radar-breakdown-meter__bar" data-tier="${t}" aria-hidden="true">${a(e.job_score)}</span>
              <span class="radar-breakdown-meter__value">${o(e.job_score)} <span class="radar-breakdown-meter__raw">(${o(e.job_mentions)} menções/semana)</span></span>
            </li>
            <li class="radar-breakdown-meter">
              <span class="radar-breakdown-meter__label mono-label">github</span>
              <span class="radar-breakdown-meter__bar" data-tier="${t}" aria-hidden="true">${a(e.github_score)}</span>
              <span class="radar-breakdown-meter__value">${o(e.github_score)} <span class="radar-breakdown-meter__raw">(${s(e.new_repos_ytd)} repos novos/ano)</span></span>
            </li>
            <li class="radar-breakdown-meter">
              <span class="radar-breakdown-meter__label mono-label">pypi</span>
              <span class="radar-breakdown-meter__bar" data-tier="${t}" aria-hidden="true">${a(e.pypi_score)}</span>
              <span class="radar-breakdown-meter__value">${o(e.pypi_score)} <span class="radar-breakdown-meter__raw">(${c(e.downloads_last_month)} downloads/mês)</span></span>
            </li>
          </ul>
        </article>`}).join(``),e)){let e=i.querySelectorAll(`.radar-breakdown-card`);e.length&&n(e,i,t.tight)}}async function h(){let e=document.body.dataset.baseurl??``,t=new AbortController,n=setTimeout(()=>t.abort(),8e3);try{let r=await fetch(`${e}assets/data/radar_scores.json`,{cache:`no-cache`,signal:t.signal});if(clearTimeout(n),!r.ok)throw Error(`fetch failed`);let i=await r.json(),a=i.tools??[];if(!a.length)throw Error(`empty payload`);u(i),d(a),f(a),p(a),m(a)}catch{clearTimeout(n);let e=document.getElementById(`ranking-tools-list`);e&&(e.innerHTML=`<p class="ranking-error mono-label">ranking indisponível — tente recarregar</p>`);let t=document.getElementById(`radar-breakdown-grid`);t&&(t.innerHTML=`<p class="ranking-error mono-label">breakdown indisponível — tente recarregar</p>`);let r=document.getElementById(`radar-tier-legend`);r&&(r.innerHTML=`<li class="ranking-error mono-label">indisponível</li>`)}}document.addEventListener(`astro:page-load`,()=>{document.getElementById(`radar-hero`)&&h()});