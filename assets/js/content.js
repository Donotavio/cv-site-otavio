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

const getArticlesJsonPath = () => {
  const baseUrl = document.body?.dataset?.baseurl || "";
  const lang = window.i18n?.lang || 'pt-BR';
  if (lang === 'pt-BR') {
    return `${baseUrl}/assets/data/blog_articles.json`;
  }
  return `${baseUrl}/assets/data/blog_articles_${lang}.json`;
};

const openArticleModal = (article) => {
  const modal = document.getElementById('article-modal');
  if (!modal) return;

  const img = modal.querySelector('.article-modal-image');
  const title = modal.querySelector('.article-modal-title');
  const meta = modal.querySelector('.article-modal-meta');
  const text = modal.querySelector('.article-modal-text');
  const link = modal.querySelector('.article-modal-link');

  title.textContent = article.title;

  if (article.image) {
    img.src = article.image;
    img.alt = article.title;
    img.hidden = false;
  } else {
    img.hidden = true;
  }

  const likesLabel = window.i18n?.t('blog.likes') || 'curtidas';
  const metaParts = [];
  if (article.date) metaParts.push(`<span>${article.date}</span>`);
  if (article.read_time) metaParts.push(`<span>${article.read_time} ${window.i18n?.t('blog.read_time') || 'leitura'}</span>`);
  if (article.likes) metaParts.push(`<span>${article.likes} ${likesLabel}</span>`);
  meta.innerHTML = metaParts.join('<span>•</span>');

  // Render body as HTML
  text.innerHTML = renderArticleBody(article.body || '');

  if (article.external_url) {
    link.href = article.external_url;
    link.textContent = window.i18n?.t('blog.read_on_linkedin') || 'Ler no LinkedIn';
    link.hidden = false;
  } else {
    link.hidden = true;
  }

  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
};

const closeArticleModal = () => {
  const modal = document.getElementById('article-modal');
  if (!modal) return;
  modal.classList.remove('active');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
};

const renderArticleBody = (body) => {
  if (!body) return '';
  return body
    .split('\n\n')
    .map(block => {
      block = block.trim();
      if (!block) return '';
      if (block.startsWith('## ')) return `<h3>${block.slice(3)}</h3>`;
      if (block.startsWith('> ')) return `<blockquote>${block.slice(2)}</blockquote>`;
      if (block.startsWith('- ')) {
        const items = block.split('\n').map(l => `<li>${l.replace(/^- /, '')}</li>`).join('');
        return `<ul>${items}</ul>`;
      }
      return `<p>${block}</p>`;
    })
    .join('\n');
};

const initArticleModal = () => {
  const modal = document.getElementById('article-modal');
  if (!modal) return;

  modal.querySelectorAll('[data-article-modal-close]').forEach(el => {
    el.addEventListener('click', closeArticleModal);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      closeArticleModal();
    }
  });
};

const renderBlogArticles = async () => {
  const grid = document.getElementById('blog-grid');
  const emptyState = document.getElementById('blog-empty');
  if (!grid) return;

  try {
    const baseUrl = document.body?.dataset?.baseurl || "";
    const articlesUrl = getArticlesJsonPath();
    let response = await fetch(articlesUrl);

    // Fallback to base pt-BR if translated file doesn't exist
    if (!response.ok) {
      response = await fetch(`${baseUrl}/assets/data/blog_articles.json`);
    }

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
      const hasBody = !!(article.body);
      card.className = `card blog-card${hasBody ? ' has-body' : ''} reveal reveal-delay-${Math.min(index + 1, 4)}`;

      const featuredBadge = article.featured ?
        `<span class="blog-featured-badge">${window.i18n?.t('blog.featured_label') || 'Destaque'}</span>` : '';

      const tagsHtml = (article.tags || [])
        .map(tag => `<span class="blog-tag">${tag}</span>`)
        .join('');

      card.innerHTML = `
        ${featuredBadge}
        ${article.image ? `<img class="blog-card-image" src="${article.image}" alt="${article.title}" loading="lazy">` : ''}
        <h3>${article.title}</h3>
        <p>${article.excerpt || ''}</p>
        <div class="blog-meta-info">
          <span>${article.date || ''}</span>
          <span>•</span>
          <span>${article.read_time} ${window.i18n?.t('blog.read_time') || 'leitura'}</span>
        </div>
        ${tagsHtml ? `<div class="blog-tags">${tagsHtml}</div>` : ''}
      `;

      if (hasBody) {
        card.addEventListener('click', (e) => {
          e.preventDefault();
          openArticleModal(article);
        });
      } else if (article.external_url) {
        const link = document.createElement('a');
        link.className = 'btn ghost';
        link.href = article.external_url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = window.i18n?.t('blog.read_more') || 'Ler artigo';
        card.appendChild(link);
      }

      grid.appendChild(card);
    });
  } catch (error) {
    console.error('Failed to load blog articles:', error);
    emptyState?.classList.add('visible');
  }
};

const initContent = async () => {
  initArticleModal();
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
