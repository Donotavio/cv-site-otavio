import{c as e,s as t}from"./cleanup.D2ntGW1D.js";import{t as n}from"./reveal-up.C1zAozKf.js";import{t as r}from"./count-up.Co9lLQLb.js";var i={gupy:`Gupy`,greenhouse:`Greenhouse`,lever:`Lever`,ashby:`Ashby`,inhire:`InHire`,apibr:`API BR`};function a(e){return i[e.toLowerCase()]??e.charAt(0).toUpperCase()+e.slice(1)}var o=18,s=10,c=10,l={python:`Python`,sql:`SQL`,"power bi":`Power BI`,aws:`AWS`,azure:`Azure`,gcp:`GCP`,databricks:`Databricks`,spark:`Spark`,airflow:`Airflow`,bigquery:`BigQuery`,kafka:`Kafka`,dbt:`dbt`,docker:`Docker`};function u(e){return`<span class="ui-bar"><span class="ui-bar__fill" style="inline-size:${Math.max(0,Math.min(100,e))}%"></span></span>`}function d(e){return e.toFixed(1).replace(`.`,`,`)}function f(e){return String(e).replace(`.`,`,`)}var p=new Intl.NumberFormat(`pt-BR`,{style:`currency`,currency:`BRL`,maximumFractionDigits:0});function m(e,t){return e===t?p.format(e):`${p.format(e)} – ${p.format(t)}`}function h(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function g(e){return e.length?e.charAt(0).toUpperCase()+e.slice(1):e}function _(e){return l[e.toLowerCase()]??g(e)}function v(e){let t=new Date(e).getTime();if(Number.isNaN(t))return``;let n=Math.max(0,Date.now()-t),r=Math.floor(n/6e4);if(r<1)return`agora mesmo`;if(r<60)return`há ${r} min`;let i=Math.floor(r/60);if(i<24)return i===1?`há 1 hora`:`há ${i} horas`;let a=Math.floor(i/24);if(a<30)return a===1?`há 1 dia`:`há ${a} dias`;let o=Math.floor(a/30);if(o<12)return o===1?`há 1 mês`:`há ${o} meses`;let s=Math.floor(o/12);return s===1?`há 1 ano`:`há ${s} anos`}function y(e){if(!e.length)return`<span class="radar-jobs-table__no-skills">—</span>`;let t=e.slice(0,4),n=e.length-t.length;return t.map(e=>`<span class="tag radar-jobs-table__skill-tag">${h(_(e))}</span>`).join(``)+(n>0?`<span class="tag radar-jobs-table__skill-tag radar-jobs-table__skill-tag--more">+${n}</span>`:``)}function b(e){let t=(e.title??``).trim()||`sem título`,n=(e.company??``).trim()||`confidencial`,r=(e.city??``).trim(),i=r||(e.is_remote?`Remoto`:`não informado`),a=e.is_remote&&r?`<span class="tag tag--accent radar-jobs-table__remote-badge">remoto</span>`:``,o=v(e.publishedDate)||`—`;return`
      <tr>
        <td class="radar-jobs-table__title">${h(t)}</td>
        <td class="radar-jobs-table__company">${h(n)}</td>
        <td class="radar-jobs-table__local">
          <span class="radar-jobs-table__city">${h(i)}</span>
          ${a}
        </td>
        <td class="radar-jobs-table__skills">${y(e.skills??[])}</td>
        <td class="radar-jobs-table__time"><time datetime="${h(e.publishedDate??``)}">${h(o)}</time></td>
        <td class="radar-jobs-table__action">
          <a
            class="link-underline radar-jobs-table__link"
            href="${h(e.url??`#`)}"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Ver vaga: ${h(t)} — ${h(n)} (abre em nova aba)"
          >Ver vaga ↗</a>
        </td>
      </tr>`}function x(r){let i=document.getElementById(`radar-jobs-table-body`);if(!i)return;let a=r.slice(0,o);if(!a.length){i.innerHTML=`<tr><td colspan="6" class="ranking-error mono-label">nenhuma vaga disponível</td></tr>`;return}if(i.innerHTML=a.map(b).join(``),e){let e=i.querySelectorAll(`tr`);e.length&&n(e,i,t.tight)}}function S(r){let i=document.getElementById(`radar-company-list`);if(!i)return;let a=r.slice(0,s);if(!a.length){i.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`;return}let o=Math.max(...a.map(e=>e.n_vagas));if(i.innerHTML=a.map((e,t)=>{let n=o?e.n_vagas/o*100:0,r=e.n_vagas?e.n_remoto/e.n_vagas*100:0,i=r>=50,a=(e.company??``).trim()||`confidencial`;return`
        <li class="radar-company-row">
          <span class="radar-company-row__rank mono-label" aria-hidden="true">${String(t+1).padStart(2,`0`)}</span>
          <span class="radar-company-row__name" title="${h(a)}">${h(a)}</span>
          <span class="radar-company-row__bar" aria-hidden="true">${u(n)}</span>
          <span
            class="radar-company-row__n"
            role="meter"
            aria-valuenow="${e.n_vagas}"
            aria-valuemin="0"
            aria-valuemax="${o}"
            aria-label="${h(a)}: ${e.n_vagas} vagas, ${Math.round(r)}% remoto"
          >${e.n_vagas} vagas</span>
          <span class="tag ${i?`tag--accent`:``} radar-company-row__remote">${Math.round(r)}% remoto</span>
        </li>`}).join(``),e){let e=i.querySelectorAll(`.radar-company-row`);e.length&&n(e,i,t.tight)}}function C(r){let i=document.getElementById(`radar-combo-list`);if(!i)return;let a=r.slice(0,c);if(!a.length){i.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`;return}if(i.innerHTML=a.map(e=>{let t=_(e.skill_a),n=_(e.skill_b);return`
        <li class="radar-combo-row">
          <div class="radar-combo-row__top">
            <span class="radar-combo-row__pair">
              <span class="tag">${h(t)}</span>
              <span class="radar-combo-row__plus" aria-hidden="true">+</span>
              <span class="tag">${h(n)}</span>
            </span>
            <span
              class="radar-combo-row__pct"
              role="meter"
              aria-valuenow="${e.pct_of_jobs}"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-label="${h(t)} e ${h(n)} aparecem juntas em ${d(e.pct_of_jobs)}% das vagas, ${e.n_vagas} vagas"
            >${d(e.pct_of_jobs)}%</span>
          </div>
          <span class="radar-combo-row__bar" aria-hidden="true">${u(e.pct_of_jobs)}</span>
          <span class="radar-combo-row__note">${e.n_vagas} vagas com as duas skills juntas</span>
        </li>`}).join(``),e){let e=i.querySelectorAll(`.radar-combo-row`);e.length&&n(e,i,t.tight)}}function w(e,t,n){let i=document.getElementById(`radar-salary-value`);i&&(i.dataset.countTo=String(e),i.setAttribute(`aria-valuenow`,String(e)),r(i,document.getElementById(`radar-salary-callout`)??i));let a=document.getElementById(`radar-salary-text`);a&&(a.textContent=`Praticamente nenhuma vaga coletada informa quanto paga. De ${n} vagas, só ${t} trazem um valor real de remuneração — o resto, quando menciona "R$", é benefício (vale-refeição, auxílio home office), não salário.`)}function T(r){let i=document.getElementById(`radar-salary-sample-list`);if(!i)return;let a=document.getElementById(`radar-salary-sample-label`);if(a&&(a.textContent=r.length===1?`o único valor real que encontramos`:`os ${r.length} valores reais que encontramos`),!r.length){i.innerHTML=`<li class="ranking-error mono-label">nenhuma vaga com valor real informado</li>`;return}if(i.innerHTML=r.map(e=>{let t=(e.title??``).trim()||`sem título`,n=(e.company??``).trim()||`confidencial`,r=g((e.seniority??``).trim()||`não especificado`),i=m(e.salary_min,e.salary_max),a=e.salary_source===`estruturado`?`faixa do ATS`:`extraído da descrição`,o=(e.contract_type??``).trim(),s=[r,o&&o!==`não especificado`?o:null].filter(Boolean).map(e=>`<span class="tag">${h(e)}</span>`).join(``);return`
        <li class="radar-salary-sample__item">
          <div class="radar-salary-sample__item-head">
            <span class="radar-salary-sample__item-title">${h(t)}</span>
            <span class="radar-salary-sample__item-value">${h(i)}</span>
          </div>
          <p class="radar-salary-sample__item-meta">
            <span class="radar-salary-sample__item-company">${h(n)}</span>
            ${s}
            <span class="radar-salary-sample__item-origem">${h(a)}</span>
          </p>
          <a
            class="link-underline radar-salary-sample__item-link"
            href="${h(e.url??`#`)}"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Ver vaga original: ${h(t)} — ${h(n)} (abre em nova aba)"
          >Ver vaga original ↗</a>
        </li>`}).join(``),e){let e=i.querySelectorAll(`.radar-salary-sample__item`);e.length&&n(e,i,t.tight)}}function E(e){let t=document.getElementById(`radar-benchmark-body`);if(!t)return;if(!e){t.innerHTML=`<p class="ranking-error mono-label">dados indisponíveis</p>`;return}let n=f(e.salario_crescimento_2023_2024_pct),r=f(e.inflacao_2024_pct),i=f(e.pct_preferem_100_remoto),a=f(e.pct_preferem_hibrido_flexivel);t.innerHTML=`
      <p class="radar-benchmark-card__source">
        ${h(e.fonte??``)}
        <span class="radar-benchmark-card__sample">${h(e.amostra??``)}</span>
      </p>
      <ul class="radar-benchmark-card__stats">
        <li class="radar-benchmark-card__stat">
          <strong>+${n}%</strong> de crescimento salarial entre 2023 e 2024 —
          acima da inflação do período (<strong>${r}%</strong>)
        </li>
        <li class="radar-benchmark-card__stat">
          <strong>${i}%</strong> preferem trabalho 100% remoto
        </li>
        <li class="radar-benchmark-card__stat">
          <strong>${a}%</strong> preferem híbrido flexível
        </li>
      </ul>
      <p class="radar-benchmark-card__note">${h(e.nota??``)}</p>
      <a
        class="radar-benchmark-card__link"
        href="${h(e.url??`#`)}"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Ver pesquisa completa: ${h(e.fonte??`fonte externa`)} (abre em nova aba)"
      >Ver pesquisa completa ↗</a>`}function D(e){let t=document.getElementById(`radar-cobertura-list`);if(t){if(!e.length){t.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`;return}t.innerHTML=e.map(e=>{let t=e.n_empresas>0?`${e.n_empresas} ${e.n_empresas===1?`empresa`:`empresas`}`:`comunidade`;return`
      <li class="jobs-meter-row">
        <span class="jobs-meter-row__label">${h(a(e.fonte))}</span>
        <span class="jobs-meter-row__bar" aria-hidden="true">${u(e.pct)}</span>
        <span class="jobs-meter-row__val" role="meter" aria-valuenow="${e.pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${h(a(e.fonte))}: ${e.n_vagas} vagas (${d(e.pct)}%), ${t}">${e.n_vagas} · ${d(e.pct)}% · ${t}</span>
      </li>`}).join(``)}}async function O(){let e=document.body.dataset.baseurl??``,t=new AbortController,n=setTimeout(()=>t.abort(),8e3);try{let r=await fetch(`${e}assets/data/radar_insights.json`,{cache:`no-cache`,signal:t.signal});if(clearTimeout(n),!r.ok)throw Error(`fetch failed`);let i=await r.json();x(i.vagas_recentes??[]),S(i.por_empresa??[]),D(i.cobertura_por_fonte??[]),C(i.skill_combos??[]),w(i.salario_transparencia_pct??0,i.n_vagas_com_salario_real??0,i.n_vagas_total??0),T(i.vagas_com_salario_real??[]),E(i.benchmark_externo)}catch{clearTimeout(n);let e=document.getElementById(`radar-jobs-table-body`);e&&(e.innerHTML=`<tr><td colspan="6" class="ranking-error mono-label">vagas indisponíveis — tente recarregar</td></tr>`);let t=document.getElementById(`radar-company-list`);t&&(t.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`);let r=document.getElementById(`radar-cobertura-list`);r&&(r.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`);let i=document.getElementById(`radar-combo-list`);i&&(i.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`);let a=document.getElementById(`radar-salary-value`);a&&(a.textContent=`—`);let o=document.getElementById(`radar-salary-text`);o&&(o.textContent=`dados indisponíveis — tente recarregar`);let s=document.getElementById(`radar-salary-sample-list`);s&&(s.innerHTML=`<li class="ranking-error mono-label">dados indisponíveis</li>`);let c=document.getElementById(`radar-benchmark-body`);c&&(c.innerHTML=`<p class="ranking-error mono-label">dados indisponíveis</p>`)}}document.addEventListener(`astro:page-load`,()=>{document.getElementById(`radar-hero`)&&O()});