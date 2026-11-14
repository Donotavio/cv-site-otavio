import{c as e,i as t,l as n,r,u as i}from"./cleanup.D2ntGW1D.js";import{t as a}from"./reveal-up.C1zAozKf.js";import{t as o}from"./hairline-draw.hqov872z.js";import{n as s,t as c}from"./scroll-lock.4Qpn9cCd.js";i.registerPlugin(n);var l=[],u=[];function d(){l.forEach(e=>e.kill()),u.forEach(e=>e.kill()),l=[],u=[]}var f=document.body.dataset.baseurl??``;function p(e){let t=e.querySelectorAll(`button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])`),n=t[0],r=t[t.length-1],i=e=>{e.key===`Tab`&&(e.shiftKey?document.activeElement===n&&(e.preventDefault(),r?.focus()):document.activeElement===r&&(e.preventDefault(),n?.focus()))};return e.addEventListener(`keydown`,i),()=>e.removeEventListener(`keydown`,i)}var m=null,h=null;function g(e){let t=document.getElementById(`timeline-modal`);if(!t)return;let n=document.getElementById(`tl-modal-logo`);if(n.innerHTML=``,e.companyLogo){let t=document.createElement(`img`);t.src=e.companyLogo,t.alt=e.company,t.width=56,t.height=56,n.appendChild(t)}document.getElementById(`tl-modal-period`).textContent=e.period??``,document.getElementById(`tl-modal-role`).textContent=e.role??``,document.getElementById(`tl-modal-company`).textContent=e.company??``,document.getElementById(`tl-modal-location`).textContent=e.location??``;let r=document.getElementById(`tl-modal-extra-role`);e.extraRole||e.extraPeriod?(r.innerHTML=`
        <p class="tl-modal__extra-label">${window.i18n?.t(`timeline.extra_experience_title`)??`Experiência adicional na empresa`}</p>
        ${e.extraRole?`<p class="tl-modal__extra-role">${e.extraRole}</p>`:``}
        ${e.extraPeriod?`<p class="tl-modal__extra-period">${e.extraPeriod}</p>`:``}
      `,r.hidden=!1):r.hidden=!0;let i=document.getElementById(`tl-modal-description`);e.description?i.innerHTML=e.description.split(`

`).filter(Boolean).map(e=>`<p>${e.replace(/\n/g,`<br>`)}</p>`).join(``):i.innerHTML=``;let a=document.getElementById(`tl-modal-skills`);e.skills?a.innerHTML=`
        <p class="tl-modal__skills-title">${window.i18n?.t(`timeline.skills_title`)??`Competências`}</p>
        <div class="tl-modal__skills-tags">${e.skills.split(` · `).map(e=>`<span class="tag">${e.trim()}</span>`).join(``)}</div>
      `:a.innerHTML=``,t.hidden=!1,t.setAttribute(`aria-hidden`,`false`),c(),h=document.activeElement,m=p(t),t.querySelector(`button[data-tl-close]`)?.focus()}function _(){let e=document.getElementById(`timeline-modal`);e&&(e.hidden=!0,e.setAttribute(`aria-hidden`,`true`),s(),m?.(),m=null,h?.focus())}async function v(){let e=document.getElementById(`timeline-list`),t=document.getElementById(`timeline-empty`);if(!e)return;let n={};try{let e=await fetch(`${f}assets/data/profile.json`);if(!e.ok)throw Error(`fetch failed`);n=await e.json()}catch{t.hidden=!1;return}let r=n.timeline??[];if(e.innerHTML=``,!r.length){t.hidden=!1;return}t.hidden=!0;let i=window.i18n?.t(`timeline.click_to_expand`)??`Clique para ver detalhes completos`;r.forEach(t=>{let n=(t.highlights??[]).slice(0,3),r=t.skills?t.skills.split(` · `).slice(0,6).map(e=>`<span class="tag">${e.trim()}</span>`).join(``):``,a=t.companyLogo?`<div class="tl-card__logo">
             <img src="${t.companyLogo}" alt="${t.company}" loading="lazy" width="44" height="44">
           </div>`:``,o=!!(t.description||t.skills),s=o?`<p class="tl-card__hint">${i}</p>`:``,c=document.createElement(`li`);c.className=`tl-entry`,c.innerHTML=`
        <div
          class="timeline-card"
          ${o?`tabindex="0" role="button"`:``}
          aria-label="${t.role} · ${t.company}"
        >
          <div class="tl-card__header">
            ${a}
            <div class="tl-card__info">
              <p class="tl-card__period">${t.period??``}</p>
              <h3 class="tl-card__role">${t.role??``}</h3>
              <p class="tl-card__company">${t.company??``}</p>
              ${t.location?`<p class="tl-card__location">${t.location}</p>`:``}
            </div>
          </div>
          ${n.length?`<ul class="tl-card__highlights">${n.map(e=>`<li>${e}</li>`).join(``)}</ul>`:``}
          ${r?`<div class="tl-card__skills">${r}</div>`:``}
          ${s}
        </div>
      `;let l=c.querySelector(`.timeline-card`);if(l&&o){let e=t;l.addEventListener(`click`,()=>g(e)),l.addEventListener(`keydown`,t=>{(t.key===`Enter`||t.key===` `)&&(t.preventDefault(),g(e))})}e.appendChild(c)}),y()}function y(){if(!e)return;d();let a=document.querySelector(`.timeline-track`),o=document.querySelector(`.timeline-progress`),s=Array.from(document.querySelectorAll(`#timeline-list .tl-entry`));if(s.length){if(a&&o){let e=i.fromTo(o,{scaleY:0},{scaleY:1,ease:`none`,scrollTrigger:{trigger:a,start:`top 70%`,end:`bottom 80%`,scrub:!0}});u.push(e),e.scrollTrigger&&l.push(e.scrollTrigger)}s.forEach(e=>{let n=i.from(e,{opacity:0,y:32,duration:r.normal,ease:t.out,scrollTrigger:{trigger:e,start:`top 80%`,once:!0,onEnter:()=>e.classList.add(`is-active`)}});u.push(n),n.scrollTrigger&&l.push(n.scrollTrigger)}),n.refresh()}}document.addEventListener(`click`,e=>{e.target.closest(`[data-tl-close]`)&&_()}),document.addEventListener(`keydown`,e=>{if(e.key===`Escape`){let e=document.getElementById(`timeline-modal`);e&&!e.hidden&&_()}}),document.addEventListener(`astro:page-load`,()=>{let t=document.getElementById(`timeline`);if(!t)return;let n=t.querySelector(`.section-line`),r=t.querySelector(`.section-head`);n&&o(n,t),e&&r&&a([r],t,0)}),window.addEventListener(`languageChanged`,()=>v()),window.i18n?v():window.addEventListener(`languageChanged`,()=>v(),{once:!0});