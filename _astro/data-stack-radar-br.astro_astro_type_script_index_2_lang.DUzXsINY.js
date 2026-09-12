import{c as e,s as t}from"./cleanup.D2ntGW1D.js";import{t as n}from"./reveal-up.C1zAozKf.js";import{t as r}from"./count-up.Co9lLQLb.js";function i(e){return`<span class="ui-bar"><span class="ui-bar__fill" style="inline-size:${Math.max(0,Math.min(100,e))}%"></span></span>`}function a(e){return e.toFixed(1).replace(`.`,`,`)}function o(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function s(e){return e.charAt(0).toUpperCase()+e.slice(1)}function c(e){let t=document.getElementById(`jobs-fonte-badge`);if(t){if(!e.length){t.textContent=`fontes indisponíveis`;return}t.textContent=e.map(e=>`${s(e.fonte)} ${a(e.pct)}%`).join(` · `)}}function l(e){let t=document.getElementById(`jobs-remoto`);if(!t)return;let n=100-e;t.innerHTML=`
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">Remoto</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${i(e)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${e}" aria-valuemin="0" aria-valuemax="100" aria-label="Remoto: ${a(e)}% das vagas">${a(e)}%</span>
      </li>
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">Presencial/híbrido</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${i(n)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${n}" aria-valuemin="0" aria-valuemax="100" aria-label="Presencial ou híbrido: ${a(n)}% das vagas">${a(n)}%</span>
      </li>`}function u(e){let t=document.getElementById(`jobs-senioridade`);t&&(t.innerHTML=e.map(e=>`
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">${o(e.seniority)}</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${i(e.pct)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${e.pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${o(e.seniority)}: ${a(e.pct)}% das vagas, ${e.n} vagas">${a(e.pct)}%</span>
      </li>`).join(``))}function d(e){let t=document.getElementById(`jobs-contrato`);if(t){if(!e.length){t.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`;return}t.innerHTML=e.map(e=>`
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">${o(e.contrato)}</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${i(e.pct)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${e.pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${o(e.contrato)}: ${a(e.pct)}% das vagas, ${e.n} vagas">${a(e.pct)}%</span>
      </li>`).join(``)}}function f(e){let t=document.getElementById(`jobs-cidades`);t&&(t.innerHTML=e.map((e,t)=>`
      <li class="radar-city-row">
        <span class="radar-city-row__rank" aria-hidden="true">${t+1}</span>
        <span class="radar-city-row__name" title="${o(e.city)}, ${o(e.state)}">${o(e.city)}</span>
        <span class="radar-city-row__state">${o(e.state)}</span>
        <span class="radar-city-row__n">${e.n}</span>
      </li>`).join(``))}function p(e){let t=document.getElementById(`jobs-skills`);t&&(t.innerHTML=e.slice(0,15).map(e=>`
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">${o(e.skill)}</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${i(e.pct_of_jobs)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${e.pct_of_jobs}" aria-valuemin="0" aria-valuemax="100" aria-label="${o(e.skill)}: ${a(e.pct_of_jobs)}% das vagas, ${e.n_jobs} vagas">${a(e.pct_of_jobs)}%</span>
      </li>`).join(``))}async function m(){let i=document.body.dataset.baseurl??``,a=new AbortController,o=setTimeout(()=>a.abort(),8e3),s=document.getElementById(`jobs-total-vagas`);try{let m=await fetch(`${i}assets/data/radar_jobs_analysis.json`,{cache:`no-cache`,signal:a.signal});if(clearTimeout(o),!m.ok)throw Error(`fetch failed`);let h=await m.json();if(l(h.remoto_pct??0),c(h.por_fonte??[]),u(h.por_senioridade??[]),d(h.por_contrato??[]),f(h.por_cidade??[]),p(h.skills_mais_mencionadas??[]),s&&h.total_vagas&&(s.dataset.countTo=String(h.total_vagas),r(s,document.getElementById(`jobs-analysis`)??s)),e){let e=document.getElementById(`jobs-analysis`),r=document.querySelectorAll(`.jobs-meter-row, .radar-city-row`);e&&r.length&&n(r,e,t.tight)}}catch{clearTimeout(o),[`jobs-remoto`,`jobs-senioridade`,`jobs-contrato`,`jobs-cidades`,`jobs-skills`].forEach(e=>{let t=document.getElementById(e);t&&(t.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`)});let e=document.getElementById(`jobs-fonte-badge`);e&&(e.textContent=`fontes indisponíveis`)}}document.addEventListener(`astro:page-load`,()=>{document.getElementById(`radar-hero`)&&m()});