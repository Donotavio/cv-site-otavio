import{c as e}from"./cleanup.D2ntGW1D.js";import{t}from"./reveal-up.C1zAozKf.js";import{t as n}from"./hairline-draw.hqov872z.js";import{t as r}from"./spotlight-reveal.CaJkHZoH.js";var i=document.body.dataset.baseurl??``;function a(e,t){return t?e.replace(/\/+$/,``)+`/`+t.replace(/^\/+/,``):``}var o=null,s=null;function c(e){return e.split(`/`).pop()?.replace(/\.[a-z0-9]+$/i,``)??``}function l(e){return e.replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`)}function u(){let e=document.getElementById(`tech-stack-grid`);if(!e||!o||!s)return;let n=o.categories??[];e.innerHTML=``,n.forEach(t=>{let n=document.createElement(`div`);n.className=`ts-category crop`;let r=(t.technologies??[]).map(e=>{let t=c(e.logo),n=s?.[t]??``,r=window.i18n?.t(`tech_stack.level_${e.level}`)??e.level,o=e.level===`expert`?`tag tag--accent`:`tag`;return`
          <div class="ts-item">
            <div class="ts-item__spot" data-spotlight aria-hidden="true">
              <div class="ts-item__photo" data-spotlight-photo style="background-image:url(${e.logo.startsWith(i)||e.logo.startsWith(`/cv-site-otavio`)?e.logo:a(i,e.logo)})"></div>
              <pre class="ts-item__logo" data-spotlight-ascii>${l(n)}</pre>
            </div>
            <span class="ts-item__name">${l(e.name)}</span>
            <span class="${o}">${l(r)}</span>
          </div>`}).join(``);n.innerHTML=`
        <span class="crop-mark-bl" aria-hidden="true"></span>
        <span class="crop-mark-br" aria-hidden="true"></span>
        <h3 class="ts-category__name">${l(t.name)}</h3>
        <div class="ts-items">${r}</div>`,e.appendChild(n)}),t(e.querySelectorAll(`.ts-category`),e,.08),e.querySelectorAll(`.ts-item__spot`).forEach(e=>{r(e,{radius:40,holdMs:3e3})})}async function d(){try{if(!o){let e=await fetch(`${i}assets/data/tech_stack.json`);e.ok&&(o=await e.json())}if(!s){let e=await fetch(`${i}assets/data/logos-ascii.json`);e.ok&&(s=await e.json())}u()}catch{}}document.addEventListener(`astro:page-load`,()=>{let r=document.getElementById(`tech-stack`);if(!r)return;let i=r.querySelector(`.section-line`),a=r.querySelector(`.section-head`);i&&n(i,r),e&&a&&t([a],r,0)}),d(),window.addEventListener(`languageChanged`,()=>u());