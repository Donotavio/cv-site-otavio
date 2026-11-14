function e(e){return Math.abs(e)>=1e9?`R$ ${(e/1e9).toFixed(2).replace(`.`,`,`)} bi`:Math.abs(e)>=1e6?`R$ ${(e/1e6).toFixed(1).replace(`.`,`,`)} M`:`R$ ${e.toLocaleString(`pt-BR`)}`}function t(e){return Math.abs(e)>=1e6?`${(e/1e6).toFixed(1).replace(`.`,`,`)}M`:Math.abs(e)>=1e3?`${(e/1e3).toFixed(1).replace(`.`,`,`)}mil`:String(e)}function n(e){if(!e||e.length!==6)return``;let t=e.slice(0,4);return`${[`janeiro`,`fevereiro`,`março`,`abril`,`maio`,`junho`,`julho`,`agosto`,`setembro`,`outubro`,`novembro`,`dezembro`][parseInt(e.slice(4,6),10)-1]} de ${t}`}async function r(){let r=document.getElementById(`seguranca-grid`),i=document.getElementById(`seguranca-footnote`);if(!r)return;let a=new AbortController,o=setTimeout(()=>a.abort(),8e3);try{let s=document.body.dataset.baseurl??``,c=await fetch(`${s}assets/data/pix_fraudes.json`,{cache:`no-cache`,signal:a.signal});if(clearTimeout(o),!c.ok)throw Error(`fetch failed`);let l=await c.json(),u=l.contestacoes,d=l.med,f=l.bloqueios_cautelares,p=n(l.anomes);if(!u||!d||!f){r.innerHTML=`<p class="ranking-error mono-label">sem dados no momento</p>`;return}r.innerHTML=`
        <div class="card seguranca-card" role="group" aria-label="Contestações de fraude no mês">
          <span class="mono-label seguranca-card__label">contestações no mês</span>
          <span class="seguranca-card__value">${t(u.total)}</span>
          <p class="seguranca-card__desc">
            ${t(u.aceitas)} aceitas como fraude confirmada
            (${e(u.valor_aceitas)})
          </p>
        </div>

        <div class="card seguranca-card" role="group" aria-label="Valor bloqueado cautelarmente">
          <span class="mono-label seguranca-card__label">bloqueado cautelarmente</span>
          <span class="seguranca-card__value seguranca-card__value--protect">${e(f.liberados_valor)}</span>
          <p class="seguranca-card__desc">
            valores suspeitos de fraude retidos pelo MED em um único mês
          </p>
        </div>

        <div class="card seguranca-card" role="group" aria-label="Percentual de devolução às vítimas">
          <span class="mono-label seguranca-card__label">devolução às vítimas</span>
          <span class="seguranca-card__value seguranca-card__value--protect">${d.percentual_devolucao.toFixed(1).replace(`.`,`,`)}%</span>
          <p class="seguranca-card__desc">
            dos valores contestados foram devolvidos (integral ou parcialmente)
          </p>
        </div>

        <div class="card seguranca-card" role="group" aria-label="Usuários marcados por fraude">
          <span class="mono-label seguranca-card__label">marcados por fraude</span>
          <span class="seguranca-card__value">${t(l.usuarios_marcados_fraude??0)}</span>
          <p class="seguranca-card__desc">
            usuários com registro de fraude no mês, banidos da rede DICT
          </p>
        </div>

        <div class="seguranca-explainer">
          <h3 class="seguranca-explainer__title">O que é o MED?</h3>
          <p class="seguranca-explainer__body">
            O Mecanismo Especial de Devolução (MED) é o protocolo do BACEN para bloquear
            e devolver valores movidos por fraude no PIX. Quando uma vítima contesta uma
            transação, a instituição recebedora pode bloquear cautelarmente o saldo antes
            que o fraudador o retire — ${p?`em ${p}, isso`:`isso`} significou
            ${e(f.liberados_valor)} retidos preventivamente,
            com ${d.percentual_devolucao.toFixed(1).replace(`.`,`,`)}% de devolução efetiva às vítimas.
          </p>
        </div>
      `,i&&p&&(i.textContent=`fonte: BACEN Olinda API · Pix_DadosAbertos / EstatisticasFraudesPix · ${p}`)}catch{clearTimeout(o),r.innerHTML=`<p class="ranking-error mono-label">estatísticas indisponíveis — tente recarregar</p>`}}document.addEventListener(`astro:page-load`,r);