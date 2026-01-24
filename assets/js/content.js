const renderFeaturedProjects = async () => {
  const grid = document.getElementById('featured-projects-grid');
  if (!grid) return;

  try {
    const baseUrl = document.body?.dataset?.baseurl || "";
    const response = await fetch(`${baseUrl}/assets/data/projects_extended.json`);
    const data = await response.json();
    const projects = data.featured_projects || [];

    grid.innerHTML = '';
    projects.forEach((project, index) => {
      const card = document.createElement('article');
      card.className = `featured-project-card reveal reveal-delay-${Math.min(index + 1, 4)}`;
      
      const metricsHtml = Object.entries(project.impact_metrics || {})
        .map(([key, value]) => `
          <div class="metric-item">
            <span class="metric-value">${value}</span>
            <span class="metric-label">${key.replace(/_/g, ' ')}</span>
          </div>
        `).join('');

      const techStackHtml = (project.tech_stack || [])
        .map(tech => `<span class="tech-badge">${tech}</span>`)
        .join('');

      const challengesHtml = (project.challenges || [])
        .map(item => `<li>${item}</li>`)
        .join('');

      const solutionsHtml = (project.solutions || [])
        .map(item => `<li>${item}</li>`)
        .join('');

      card.innerHTML = `
        <div class="project-header">
          <span class="project-category">${project.category || ''}</span>
          <h3 class="project-title">${project.name || ''}</h3>
        </div>
        <div class="project-body">
          <div class="project-metrics">
            ${metricsHtml}
          </div>
          <div class="project-tech-stack">
            ${techStackHtml}
          </div>
          ${challengesHtml ? `
            <div class="project-section">
              <h4>${window.i18n?.t('featured_projects.challenges') || 'Desafios'}</h4>
              <ul>${challengesHtml}</ul>
            </div>
          ` : ''}
          ${solutionsHtml ? `
            <div class="project-section">
              <h4>${window.i18n?.t('featured_projects.solutions') || 'Soluções'}</h4>
              <ul>${solutionsHtml}</ul>
            </div>
          ` : ''}
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (error) {
    console.error('Failed to load featured projects:', error);
  }
};

const renderTechStack = async () => {
  const grid = document.getElementById('tech-stack-grid');
  if (!grid) return;

  try {
    const baseUrl = document.body?.dataset?.baseurl || "";
    const response = await fetch(`${baseUrl}/assets/data/tech_stack.json`);
    const data = await response.json();
    const categories = data.categories || [];

    grid.innerHTML = '';
    categories.forEach((category, catIndex) => {
      const categoryDiv = document.createElement('div');
      categoryDiv.className = `tech-category reveal reveal-delay-${Math.min(catIndex + 1, 4)}`;
      
      const techItemsHtml = (category.technologies || [])
        .map(tech => `
          <div class="tech-item">
            <img src="${tech.logo}" alt="${tech.name}" class="tech-logo" onerror="this.style.display='none'">
            <span class="tech-name">${tech.name}</span>
            <span class="tech-level">${window.i18n?.t(`tech_stack.level_${tech.level}`) || tech.level}</span>
          </div>
        `).join('');

      categoryDiv.innerHTML = `
        <h3>${category.name}</h3>
        <div class="tech-items">
          ${techItemsHtml}
        </div>
      `;
      grid.appendChild(categoryDiv);
    });
  } catch (error) {
    console.error('Failed to load tech stack:', error);
  }
};

const renderBlogArticles = async () => {
  const grid = document.getElementById('blog-grid');
  const emptyState = document.getElementById('blog-empty');
  if (!grid) return;

  try {
    const baseUrl = document.body?.dataset?.baseurl || "";
    const response = await fetch(`${baseUrl}/assets/data/blog_articles.json`);
    const data = await response.json();
    const articles = data.articles || [];

    if (!articles.length) {
      emptyState?.classList.add('visible');
      return;
    }

    emptyState?.classList.remove('visible');
    grid.innerHTML = '';
    
    articles.slice(0, 6).forEach((article, index) => {
      const card = document.createElement('article');
      card.className = `card blog-card reveal reveal-delay-${Math.min(index + 1, 4)}`;
      
      const featuredBadge = article.featured ? 
        `<span class="blog-featured-badge">✨ ${window.i18n?.t('blog.featured_label') || 'Destaque'}</span>` : '';
      
      const tagsHtml = (article.tags || [])
        .map(tag => `<span class="blog-tag">${tag}</span>`)
        .join('');

      card.innerHTML = `
        ${featuredBadge}
        <h3>${article.title}</h3>
        <p>${article.excerpt || ''}</p>
        <div class="blog-meta-info">
          <span>${article.date || ''}</span>
          <span>•</span>
          <span>${article.read_time} ${window.i18n?.t('blog.read_time') || 'leitura'}</span>
        </div>
        ${tagsHtml ? `<div class="blog-tags">${tagsHtml}</div>` : ''}
        ${article.external_url ? `
          <a class="btn ghost" href="${article.external_url}" target="_blank" rel="noopener">
            ${window.i18n?.t('blog.read_more') || 'Ler artigo'}
          </a>
        ` : ''}
      `;
      grid.appendChild(card);
    });
  } catch (error) {
    console.error('Failed to load blog articles:', error);
    emptyState?.classList.add('visible');
  }
};

const initContent = async () => {
  await Promise.all([
    renderFeaturedProjects(),
    renderTechStack(),
    renderBlogArticles()
  ]);
  window.dispatchEvent(new Event('contentUpdated'));
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initContent);
} else {
  initContent();
}

window.addEventListener('languageChanged', () => {
  initContent();
});
