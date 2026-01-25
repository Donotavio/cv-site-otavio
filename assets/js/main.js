const baseUrl = document.body?.dataset?.baseurl || "";

const fetchJson = async (path) => {
  const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return response.json();
};

const getTranslation = (key, fallback = "") => {
  const translator = window.i18n?.t;
  if (translator) {
    return translator(key) ?? fallback;
  }
  return fallback;
};

const formatTemplate = (template, values) => {
  if (!template) return "";
  return template.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
};

// Extrair ano do período (ex: "Jan 2025 - Presente" -> 2025)
const extractYear = (period) => {
  if (!period) return new Date().getFullYear();
  const match = period.match(/\d{4}/);
  return match ? parseInt(match[0]) : new Date().getFullYear();
};

const renderTimeline = (items = []) => {
  const container = document.getElementById("timeline-container");
  const emptyState = document.getElementById("timeline-empty");
  const template = document.getElementById("timeline-item-template");

  if (!container || !template) {
    return;
  }

  container.innerHTML = "";
  if (!items.length) {
    if (emptyState) {
      emptyState.classList.add("visible");
    }
    return;
  }
  if (emptyState) {
    emptyState.classList.remove("visible");
  }

  const years = new Set();

  items.forEach((item) => {
    const node = template.content.cloneNode(true);
    
    // Extrair ano e adicionar ao timeline-item
    const year = extractYear(item.period);
    years.add(year);
    
    const timelineItem = node.querySelector(".timeline-item");
    if (timelineItem) {
      timelineItem.classList.add("is-active");
      timelineItem.dataset.year = year;
    }
    
    // Logo da empresa
    const logoWrapper = node.querySelector(".company-logo-wrapper");
    if (item.companyLogo) {
      if (item.companyUrl) {
        const link = document.createElement("a");
        link.href = item.companyUrl;
        link.target = "_blank";
        link.rel = "noopener";
        link.className = "company-logo-link";
        const linkTitle = window.i18n?.t('timeline.view_company_page') || 'Ver página da empresa';
        link.title = `${linkTitle}: ${item.company}`;
        
        const img = document.createElement("img");
        img.src = item.companyLogo;
        img.alt = item.company;
        img.className = "company-logo";
        
        link.appendChild(img);
        logoWrapper.appendChild(link);
      } else {
        const img = document.createElement("img");
        img.src = item.companyLogo;
        img.alt = item.company;
        img.className = "company-logo";
        logoWrapper.appendChild(img);
      }
    }
    
    node.querySelector(".timeline-role").textContent = item.role || "";
    node.querySelector(".timeline-company").textContent = item.company || "";
    node.querySelector(".timeline-period").textContent = item.period || "";
    node.querySelector(".timeline-location").textContent = item.location || "";

    const highlightsEl = node.querySelector(".timeline-highlights");
    highlightsEl.innerHTML = "";
    (item.highlights || []).forEach((highlight) => {
      const li = document.createElement("li");
      li.textContent = highlight;
      highlightsEl.appendChild(li);
    });

    // Adicionar evento de clique para abrir modal com detalhes
    const card = node.querySelector(".timeline-card");
    if (card && (item.description || item.skills)) {
      card.style.cursor = "pointer";
      card.addEventListener("click", () => openExperienceModal(item));
      card.addEventListener("keypress", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openExperienceModal(item);
        }
      });
    }

    container.appendChild(node);
  });

  // Criar botões de filtro por ano
  createYearButtons(Array.from(years).sort((a, b) => b - a));
};

// Função para abrir modal com detalhes da experiência
const openExperienceModal = (experience) => {
  const modal = document.getElementById("experience-modal");
  if (!modal) return;

  // Preencher dados do modal
  const logoContainer = modal.querySelector(".modal-company-logo");
  logoContainer.innerHTML = "";
  if (experience.companyLogo) {
    const img = document.createElement("img");
    img.src = experience.companyLogo;
    img.alt = experience.company;
    logoContainer.appendChild(img);
  }

  modal.querySelector(".modal-role").textContent = experience.role || "";
  modal.querySelector(".modal-company").textContent = experience.company || "";
  modal.querySelector(".modal-period").textContent = experience.period || "";
  modal.querySelector(".modal-location").textContent = experience.location || "";

  // Descrição completa
  const descriptionEl = modal.querySelector(".modal-description");
  if (experience.description) {
    descriptionEl.innerHTML = `<h3>Sobre a posição</h3><p>${experience.description.replace(/\n/g, '</p><p>')}</p>`;
    descriptionEl.style.display = "block";
  } else {
    descriptionEl.style.display = "none";
  }

  // Competências
  const skillsEl = modal.querySelector(".modal-skills");
  if (experience.skills) {
    const skillsTitle = window.i18n?.t('timeline.skills_title') || 'Skills';
    const skillsList = experience.skills.split(" · ").map(skill => `<span class="skill-tag">${skill.trim()}</span>`).join("");
    skillsEl.innerHTML = `<h3>${skillsTitle}</h3><div class="skills-grid">${skillsList}</div>`;
    skillsEl.style.display = "block";
  } else {
    skillsEl.style.display = "none";
  }

  // Highlights
  const extraEl = modal.querySelector(".modal-extra");
  if (experience.highlights && experience.highlights.length > 0) {
    const highlightsList = experience.highlights.map(h => `<li>${h}</li>`).join("");
    extraEl.innerHTML = `<h3>Destaques</h3><ul class="modal-highlights">${highlightsList}</ul>`;
    extraEl.style.display = "block";
  } else {
    extraEl.style.display = "none";
  }

  // Abrir modal
  modal.classList.add("active");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";

  // Fechar modal
  const closeButtons = modal.querySelectorAll("[data-modal-close]");
  closeButtons.forEach(btn => {
    btn.onclick = () => closeExperienceModal();
  });

  // Fechar com ESC
  const handleEsc = (e) => {
    if (e.key === "Escape") {
      closeExperienceModal();
      document.removeEventListener("keydown", handleEsc);
    }
  };
  document.addEventListener("keydown", handleEsc);
};

const closeExperienceModal = () => {
  const modal = document.getElementById("experience-modal");
  if (!modal) return;
  
  modal.classList.remove("active");
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
};

// Variável para rastrear o ano anterior selecionado
let currentSelectedYear = null;

// Criar botões de navegação por ano
const createYearButtons = (years) => {
  const yearsContainer = document.getElementById("timeline-years");
  if (!yearsContainer || !years.length) return;

  // Adicionar botão "Todos" + botões de anos
  const allButtonLabel = window.i18n?.t('timeline.all_years') || 'Todos';
  yearsContainer.innerHTML = `
    <button class="year-button active" data-year="all">
      <span>${allButtonLabel}</span>
    </button>
    ${years.map(year => `
      <button class="year-button" data-year="${year}">
        <span>${year}</span>
      </button>
    `).join("")}
  `;

  const buttons = yearsContainer.querySelectorAll(".year-button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const yearValue = btn.dataset.year;
      const year = yearValue === "all" ? null : parseInt(yearValue);
      filterByYear(year);
      
      // Atualizar botões ativos
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentSelectedYear = year;
    });
  });

  // Mostrar todos os anos por padrão
  currentSelectedYear = null;
  filterByYear(null, true);
};

// Filtrar timeline por ano com scroll agressivo
const filterByYear = (year, skipAnimation = false) => {
  const items = document.querySelectorAll(".timeline-item");
  const container = document.querySelector(".timeline");
  
  if (!items.length || !container) return;

  // Trocar visibilidade imediatamente
  let firstVisibleItem = null;
  
  items.forEach((item) => {
    const itemYear = parseInt(item.dataset.year);
    // Se year é null, mostrar todos os itens
    if (year === null || itemYear === year) {
      item.style.display = "";
      item.style.opacity = "1";
      item.style.transform = "translateY(0)";
      if (!firstVisibleItem) {
        firstVisibleItem = item;
      }
    } else {
      item.style.display = "none";
    }
  });

  // Scroll MUITO visível até o primeiro item do ano selecionado
  if (firstVisibleItem && !skipAnimation) {
    const itemTop = firstVisibleItem.getBoundingClientRect().top + window.scrollY;
    const offset = 120; // Offset do topo
    
    // Desabilitar reveal observer durante scroll para evitar conflito de animações
    if (window.revealObserver) {
      window.revealObserver.disconnect();
    }
    
    // Scroll com duração maior e mais visível
    const startPosition = window.scrollY;
    const targetPosition = itemTop - offset;
    const distance = targetPosition - startPosition;
    const duration = 800; // 800ms para scroll bem visível
    let start = null;

    const animation = (currentTime) => {
      if (start === null) start = currentTime;
      const timeElapsed = currentTime - start;
      const progress = Math.min(timeElapsed / duration, 1);
      
      // Easing function para movimento suave mas visível
      const ease = progress < 0.5 
        ? 4 * progress * progress * progress 
        : 1 - Math.pow(-2 * progress + 2, 3) / 2;
      
      window.scrollTo(0, startPosition + (distance * ease));
      
      if (timeElapsed < duration) {
        requestAnimationFrame(animation);
      } else {
        // Reconectar reveal observer após scroll completar
        if (window.revealObserver) {
          const reveals = document.querySelectorAll('.reveal');
          reveals.forEach((el) => window.revealObserver.observe(el));
        }
      }
    };

    requestAnimationFrame(animation);
  }

  currentSelectedYear = year;
};

// Atualizar botão de ano ativo
const updateActiveYear = (year, buttons) => {
  buttons.forEach((btn) => {
    if (parseInt(btn.dataset.year) === year) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
};

const renderProjects = (projects = []) => {
  const grid = document.getElementById("projects-grid");
  const emptyState = document.getElementById("projects-empty");
  if (!grid) return;

  grid.innerHTML = "";
  if (!projects.length) {
    emptyState?.classList.add("visible");
    return;
  }
  emptyState?.classList.remove("visible");

  const ctaLabel = getTranslation("projects.cta", "Ver repositório");
  projects.forEach((project) => {
    const translationKey = `projects.descriptions.${project.name}`;
    const translatedDescription = getTranslation(translationKey, "");
    const description = translatedDescription || project.description || "";
    
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <div class="card-header-with-icon">
        <h3 class="card-title">${project.name || ""}</h3>
        <svg class="github-icon" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
      </div>
      <p>${description}</p>
      <div class="card-meta">
        <span>${project.language || ""}</span>
        <span>★ ${project.stars ?? 0}</span>
      </div>
      <a class="btn ghost" href="${project.url || "#"}" target="_blank" rel="noopener">
        ${project.cta || ctaLabel}
      </a>
    `;
    grid.appendChild(card);
  });
};

const renderRecommendations = (items = []) => {
  const track = document.getElementById("recommendations-track");
  const emptyState = document.getElementById("recommendations-empty");
  if (!track) return;

  track.innerHTML = "";
  if (!items.length) {
    emptyState?.classList.add("visible");
    return;
  }
  emptyState?.classList.remove("visible");

  items.forEach((rec) => {
    const card = document.createElement("article");
    card.className = "card recommendation-card";
    
    // Buscar traduções do i18n usando o ID da recomendação
    const translationKey = `recommendations.items.${rec.id}`;
    const translatedText = window.i18n?.t(`${translationKey}.text`) || rec.text || "";
    const translatedDate = window.i18n?.t(`${translationKey}.date`) || rec.date || "";
    const translatedRelationship = window.i18n?.t(`${translationKey}.relationship`) || rec.relationship || "";
    
    const photoSrc = rec.photo ? `${baseUrl}${rec.photo}` : '';
    const photoHtml = photoSrc ? `<img src="${photoSrc}" alt="${rec.author}" class="recommendation-photo">` : '';
    const linkedinLink = rec.linkedin ? `<a href="${rec.linkedin}" target="_blank" rel="noopener" class="linkedin-link" title="Ver perfil no LinkedIn">
      <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
    </a>` : '';
    
    card.innerHTML = `
      <div class="recommendation-quote">
        <p>"${translatedText}"</p>
      </div>
      <div class="recommendation-author">
        ${photoHtml}
        <div class="author-info">
          <div class="author-header">
            <strong>${rec.author || ""}</strong>
            ${linkedinLink}
          </div>
          <div class="card-meta">${rec.role || ""} · ${translatedDate}</div>
        </div>
      </div>
    `;
    track.appendChild(card);
  });
};

const calculateFreshness = (timestamp) => {
  if (!timestamp) return { text: "Data unavailable", isStale: true };
  
  const now = new Date();
  const updated = new Date(timestamp);
  const hours = Math.floor((now - updated) / (1000 * 60 * 60));
  
  if (hours < 1) {
    return { text: getTranslation("stats.freshness.just_now", "Atualizado agora"), isStale: false };
  }
  if (hours < 24) {
    const msg = formatTemplate(getTranslation("stats.freshness.hours_ago", "Atualizado há {hours}h"), { hours });
    return { text: msg, isStale: false };
  }
  const days = Math.floor(hours / 24);
  const msg = formatTemplate(getTranslation("stats.freshness.days_ago", "Atualizado há {days} dia{plural}"), { 
    days, 
    plural: days > 1 ? "s" : "" 
  });
  return { text: msg, isStale: days > 2 };
};

const renderStats = (github = {}) => {
  const grid = document.getElementById("github-stats");
  if (!grid) return;

  const summary = github.summary || {};
  const breakdown = github.activity_breakdown || {};
  const recentActivity = github.recent_activity || {};
  const languages = (github.top_languages || [])
    .slice(0, 3)
    .map((lang) => lang.name)
    .join(", ");
  
  const freshness = calculateFreshness(github.generated_at);

  // Cards principais
  const stats = [
    { 
      label: getTranslation("stats.labels.contributions", "Contribuições"),
      value: summary.contributions_last_year?.toLocaleString() ?? "0",
      subtitle: getTranslation("stats.labels.last_year", "último ano")
    },
    { 
      label: getTranslation("stats.labels.repos", "Repositórios"), 
      value: summary.public_repos ?? 0 
    },
    { 
      label: getTranslation("stats.labels.stars", "Stars"), 
      value: summary.total_stars ?? 0 
    },
    {
      label: getTranslation("stats.labels.languages", "Linguagens"),
      value: languages || "-",
    }
  ];

  // Activity breakdown
  const breakdownStats = [
    { 
      label: "Commits", 
      value: `${breakdown.commits || 0}%`,
      color: "#22c55e"
    },
    { 
      label: "Code Review", 
      value: `${breakdown.code_review || 0}%`,
      color: "#3b82f6"
    },
    { 
      label: "Pull Requests", 
      value: `${breakdown.pull_requests || 0}%`,
      color: "#a855f7"
    },
    { 
      label: "Issues", 
      value: `${breakdown.issues || 0}%`,
      color: "#ef4444"
    }
  ];

  grid.innerHTML = "";
  
  // Adicionar indicador de frescor
  if (github.generated_at) {
    const freshnessIndicator = document.createElement("div");
    freshnessIndicator.className = `stats-freshness ${freshness.isStale ? 'stale' : ''}`;
    freshnessIndicator.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <polyline points="12 6 12 12 16 14"></polyline>
      </svg>
      <span>${freshness.text}</span>
      ${freshness.isStale ? '<span class="freshness-warning">⚠️ ' + getTranslation("stats.freshness.stale_warning", "Dados podem estar desatualizados") + '</span>' : ''}
    `;
    grid.appendChild(freshnessIndicator);
  }
  
  // Renderizar cards principais
  stats.forEach((stat) => {
    const card = document.createElement("div");
    card.className = "stat-card reveal";
    card.innerHTML = `
      <div class="stat-value">${stat.value}</div>
      <div class="stat-label">${stat.label}</div>
      ${stat.subtitle ? `<div class="stat-subtitle">${stat.subtitle}</div>` : ''}
    `;
    grid.appendChild(card);
  });

  // Renderizar breakdown de atividade
  if (breakdown.commits || breakdown.code_review || breakdown.pull_requests || breakdown.issues) {
    const breakdownCard = document.createElement("div");
    breakdownCard.className = "stat-card stat-card-wide reveal";
    const breakdownTitle = getTranslation("stats.labels.activity_breakdown", "Activity Breakdown");
    breakdownCard.innerHTML = `
      <div class="stat-label" style="margin-bottom: 1rem;">${breakdownTitle}</div>
      <div class="activity-breakdown">
        ${breakdownStats.map(stat => `
          <div class="breakdown-item">
            <div class="breakdown-bar" style="background: ${stat.color}; width: ${stat.value};"></div>
            <div class="breakdown-label">${stat.label}: <strong>${stat.value}</strong></div>
          </div>
        `).join('')}
      </div>
    `;
    grid.appendChild(breakdownCard);
  }

  // Atividade recente - sempre mostrar se houver dados de recent_activity
  if (Object.keys(recentActivity).length > 0) {
    const recentCard = document.createElement("div");
    recentCard.className = "stat-card stat-card-wide reveal";
    recentCard.innerHTML = `
      <div class="stat-label" style="margin-bottom: 1rem;">${getTranslation("stats.labels.recent_activity", "Atividade Recente")}</div>
      <div class="recent-activity">
        <div class="recent-item">
          <span class="recent-value">${recentActivity.commits_this_month || 0}</span>
          <span class="recent-label">${getTranslation("stats.labels.commits_month", "commits este mês")}</span>
        </div>
        <div class="recent-item">
          <span class="recent-value">${recentActivity.repos_contributed || 0}</span>
          <span class="recent-label">${getTranslation("stats.labels.repos_contributed", "repositórios")}</span>
        </div>
        <div class="recent-item">
          <span class="recent-value">${recentActivity.pull_requests_opened || 0}</span>
          <span class="recent-label">${getTranslation("stats.labels.prs_opened", "PRs abertos")}</span>
        </div>
        <div class="recent-item">
          <span class="recent-value">${recentActivity.pull_requests_reviewed || 0}</span>
          <span class="recent-label">${getTranslation("stats.labels.prs_reviewed", "PRs revisados")}</span>
        </div>
      </div>
    `;
    grid.appendChild(recentCard);
  }
  
  // renderContributionsHeatmap já chama renderActivityRadar internamente
  renderContributionsHeatmap(cachedGithub);
};

const renderContributionsHeatmap = (github = {}) => {
  const container = document.getElementById("contributions-heatmap");
  const filterContainer = document.getElementById("contributions-year-filter");
  
  if (!container || !filterContainer) return;
  
  const calendar = github.contributions_calendar || {};
  const years = Object.keys(calendar).sort((a, b) => b - a);
  
  if (years.length === 0) {
    container.innerHTML = '<p class="empty-state">Dados de contribuições não disponíveis</p>';
    return;
  }
  
  const currentYear = years[0];
  let selectedYear = null; // Começa sem filtro para mostrar radar
  
  // Calcular total de contribuições de todos os anos
  const totalAllYears = Object.values(calendar).reduce((sum, data) => sum + (data.total || 0), 0);
  
  // Adicionar botão "Todos" + botões de anos
  const allYearsLabel = window.i18n?.t('stats.all_years') || 'Todos';
  filterContainer.innerHTML = `
    <button class="year-btn active" data-year="all">${allYearsLabel} (${totalAllYears})</button>
    ${years.map(year => {
      const data = calendar[year];
      return `<button class="year-btn" data-year="${year}">${year} (${data.total || 0})</button>`;
    }).join('')}
  `;
  
  const renderYear = (year) => {
    // Se year é 'all', mostrar o ano mais recente mas manter selectedYear como null para o radar
    const displayYear = year === 'all' ? currentYear : year;
    const data = calendar[displayYear];
    if (!data || !data.days) return;
    
    const days = data.days;
    const maxCount = Math.max(...days.map(d => d.count), 1);
    
    const monthLabels = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    const weekdayLabels = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    
    const weeks = [];
    let currentWeek = [];
    
    days.forEach((day, index) => {
      const date = new Date(day.date);
      const weekday = date.getDay();
      
      if (index === 0 && weekday > 0) {
        for (let i = 0; i < weekday; i++) {
          currentWeek.push(null);
        }
      }
      
      currentWeek.push(day);
      
      if (weekday === 6 || index === days.length - 1) {
        weeks.push([...currentWeek]);
        currentWeek = [];
      }
    });
    
    const getLevel = (count) => {
      if (count === 0) return 0;
      const quartile = maxCount / 4;
      if (count <= quartile) return 1;
      if (count <= quartile * 2) return 2;
      if (count <= quartile * 3) return 3;
      return 4;
    };
    
    container.innerHTML = `
      <div class="heatmap-grid">
        <div class="heatmap-months">
          ${monthLabels.map((m, i) => `<span style="grid-column: ${Math.floor(i * 4.3) + 1}">${m}</span>`).join('')}
        </div>
        <div class="heatmap-days">
          <div class="weekday-labels">
            ${weekdayLabels.map(w => `<span>${w}</span>`).join('')}
          </div>
          <div class="heatmap-weeks">
            ${weeks.map(week => `
              <div class="heatmap-week">
                ${week.map(day => {
                  if (!day) return '<span class="heatmap-day empty"></span>';
                  const level = getLevel(day.count);
                  const date = new Date(day.date).toLocaleDateString('pt-BR');
                  return `<span class="heatmap-day level-${level}" 
                            title="${day.count} contribuições em ${date}" 
                            data-count="${day.count}"
                            data-date="${day.date}"></span>`;
                }).join('')}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  };
  
  // Renderizar ano atual e radar agregado inicialmente
  renderYear('all');
  renderActivityRadar(github, null);
  
  filterContainer.querySelectorAll('.year-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      filterContainer.querySelectorAll('.year-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const yearValue = e.target.dataset.year;
      
      if (yearValue === 'all') {
        selectedYear = null;
        renderYear('all');
        renderActivityRadar(github, null); // Mostrar radar agregado
      } else {
        selectedYear = yearValue;
        renderYear(yearValue);
        renderActivityRadar(github, yearValue); // Mostrar radar do ano específico
      }
    });
  });
};

const renderActivityRadar = (github = {}, selectedYear = null) => {
  const radarSection = document.querySelector(".radar-section");
  const svg = document.getElementById("activity-radar-svg");
  if (!svg || !radarSection) return;
  
  radarSection.style.display = '';
  
  // Se um ano foi selecionado, usar breakdown daquele ano
  // Caso contrário, usar breakdown agregado
  let breakdown;
  let yearLabel = '';
  
  if (selectedYear && github.activity_breakdown_by_year && github.activity_breakdown_by_year[selectedYear]) {
    breakdown = github.activity_breakdown_by_year[selectedYear];
    yearLabel = selectedYear;
  } else {
    breakdown = github.activity_breakdown || {};
    yearLabel = window.i18n?.t('stats.all_years') || 'Todos os anos';
  }
  
  const activities = [
    { label: "Commits", value: breakdown.commits || 0, color: "#22c55e", angle: 0 },
    { label: "Code review", value: breakdown.code_review || 0, color: "#3b82f6", angle: 90 },
    { label: "Issues", value: breakdown.issues || 0, color: "#ef4444", angle: 180 },
    { label: "Pull requests", value: breakdown.pull_requests || 0, color: "#a855f7", angle: 270 }
  ];
  
  const centerX = 150;
  const centerY = 150;
  const maxRadius = 100;
  
  const polarToCartesian = (angle, radius) => {
    const rad = (angle - 90) * Math.PI / 180;
    return {
      x: centerX + radius * Math.cos(rad),
      y: centerY + radius * Math.sin(rad)
    };
  };
  
  const createPath = () => {
    const points = activities.map(act => {
      const radius = (act.value / 100) * maxRadius;
      return polarToCartesian(act.angle, radius);
    });
    
    const pathData = points.map((p, i) => 
      `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
    ).join(' ') + ' Z';
    
    return pathData;
  };
  
  svg.innerHTML = `
    ${[20, 40, 60, 80, 100].map(percent => {
      const r = (percent / 100) * maxRadius;
      return `<circle cx="${centerX}" cy="${centerY}" r="${r}" fill="none" 
                stroke="rgba(255,255,255,0.1)" stroke-width="1"/>`;
    }).join('')}
    
    ${activities.map(act => {
      const end = polarToCartesian(act.angle, maxRadius);
      return `<line x1="${centerX}" y1="${centerY}" 
                x2="${end.x}" y2="${end.y}" 
                stroke="rgba(255,255,255,0.2)" stroke-width="1"/>`;
    }).join('')}
    
    <path d="${createPath()}" fill="rgba(59, 130, 246, 0.2)" stroke="rgba(59, 130, 246, 0.8)" stroke-width="2"/>
    
    ${activities.map(act => {
      const radius = (act.value / 100) * maxRadius;
      const point = polarToCartesian(act.angle, radius);
      return `<circle cx="${point.x}" cy="${point.y}" r="4" fill="${act.color}"/>`;
    }).join('')}
    
    ${activities.map(act => {
      const labelRadius = maxRadius + 32;
      const labelPoint = polarToCartesian(act.angle, labelRadius);
      const textAnchor = act.angle >= 45 && act.angle <= 225 ? 'end' : 'start';
      return `
        <text x="${labelPoint.x}" y="${labelPoint.y - 2}" 
          text-anchor="${textAnchor}" 
          fill="currentColor" 
          font-size="13" 
          font-weight="600">${act.value}%</text>
        <text x="${labelPoint.x}" y="${labelPoint.y + 12}" 
          text-anchor="${textAnchor}" 
          fill="rgba(255,255,255,0.65)" 
          font-size="9">${act.label}</text>
      `;
    }).join('')}
  `;
};

const setupSlider = () => {
  // Slider removido - agora usando grid layout
};

const setupNavToggle = () => {
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", () => {
    nav.classList.toggle("open");
  });
  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => nav.classList.remove("open"));
  });
};

const setupSkillBars = () => {
  const skills = document.querySelectorAll(".skill-card");
  if (!skills.length) return;

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const card = entry.target;
          const level = card.dataset.level || 0;
          const bar = card.querySelector(".skill-bar span");
          if (bar) {
            bar.style.width = `${level}%`;
          }
          obs.unobserve(card);
        }
      });
    },
    { threshold: 0.4 }
  );

  skills.forEach((card) => observer.observe(card));
};

let cachedProfile = {};
let cachedGithub = {};

const init = async () => {
  setupNavToggle();
  setupSlider();
  setupSkillBars();
  
  try {
    const [profileData, githubData] = await Promise.all([
      fetchJson("/assets/data/profile.json"),
      fetchJson("/assets/data/github_activity.json"),
    ]);
    
    cachedProfile = profileData || {};
    cachedGithub = githubData || {};
    
    renderTimeline(cachedProfile.timeline || []);
    renderProjects(cachedProfile.projects || []);
    renderRecommendations(cachedProfile.recommendations || []);
    renderStats(cachedGithub || {});
    window.dispatchEvent(new Event("contentUpdated"));
  } catch (error) {
    console.error("Error loading profile data:", error);
    
    renderTimeline([]);
    renderProjects([]);
    renderRecommendations([]);
    renderStats({});
    window.dispatchEvent(new Event("contentUpdated"));
  }
};

document.addEventListener("DOMContentLoaded", init);

window.addEventListener("languageChanged", () => {
  renderProjects(cachedProfile.projects || []);
  renderRecommendations(cachedProfile.recommendations || []);
  renderStats(cachedGithub || {});
  window.dispatchEvent(new Event("contentUpdated"));
});
