(() => {
  let experiencesData = [];
  let currentIndex = 0;

  const openModal = (experience) => {
    const modal = document.getElementById("experience-modal");
    if (!modal) return;

    const modalRole = modal.querySelector(".modal-role");
    const modalCompany = modal.querySelector(".modal-company");
    const modalPeriod = modal.querySelector(".modal-period");
    const modalLocation = modal.querySelector(".modal-location");
    const modalCompanyLogo = modal.querySelector(".modal-company-logo");
    const modalDescription = modal.querySelector(".modal-description");
    const modalSkills = modal.querySelector(".modal-skills");
    const modalExtra = modal.querySelector(".modal-extra");

    if (modalRole) modalRole.textContent = experience.role;
    if (modalCompany) modalCompany.textContent = experience.company;
    if (modalPeriod) modalPeriod.textContent = experience.period;
    if (modalLocation) modalLocation.textContent = experience.location;

    if (modalCompanyLogo) {
      const logoSrc = experience.companyLogo || '';
      modalCompanyLogo.innerHTML = logoSrc
        ? `<img src="${logoSrc}" alt="${experience.company}" onerror="this.style.display='none'">`
        : '';
    }

    if (modalDescription) {
      modalDescription.textContent = experience.description || '';
    }

    if (modalSkills && experience.skills) {
      const skillsArray = experience.skills.split(' · ').filter(s => s.trim());
      const skillsTitle = window.i18n?.t('timeline.skills_title') || 'Competências';
      modalSkills.innerHTML = `
        <h3>${skillsTitle}</h3>
        <div class="skills-tags">
          ${skillsArray.map(skill => `<span class="skill-tag">${skill}</span>`).join('')}
        </div>
      `;
    } else if (modalSkills) {
      modalSkills.innerHTML = '';
    }

    if (modalExtra && experience.extraRole) {
      const extraTitle = window.i18n?.t('timeline.extra_experience_title') || 'Experiência adicional na empresa';
      modalExtra.innerHTML = `
        <h3>${extraTitle}</h3>
        <div class="modal-extra-role">${experience.extraRole}</div>
        <div class="modal-extra-period">${experience.extraPeriod}</div>
        <div class="modal-extra-description">${experience.extraDescription || ''}</div>
      `;
      modalExtra.style.display = 'block';
    } else if (modalExtra) {
      modalExtra.style.display = 'none';
    }

    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  const closeModal = () => {
    const modal = document.getElementById("experience-modal");
    if (!modal) return;

    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  const initModal = () => {
    const modal = document.getElementById("experience-modal");
    if (!modal) return;

    const closeButtons = modal.querySelectorAll("[data-modal-close]");
    closeButtons.forEach((btn) => {
      btn.addEventListener("click", closeModal);
    });

    modal.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  };

  const renderTimeline = (experiences) => {
    const wheel = document.getElementById("timeline-wheel");
    const emptyState = document.getElementById("timeline-empty");

    console.log('renderTimeline called', { 
      wheel: !!wheel, 
      experiencesCount: experiences?.length 
    });

    if (!wheel) {
      console.error('Timeline wheel element not found!');
      return;
    }

    wheel.innerHTML = "";

    if (!experiences || experiences.length === 0) {
      console.warn('No experiences to render');
      if (emptyState) emptyState.classList.add("visible");
      return;
    }

    if (emptyState) emptyState.classList.remove("visible");

    const itemCount = experiences.length;
    wheel.style.setProperty('--items', itemCount);
    console.log('Rendering', itemCount, 'timeline items');

    experiences.forEach((exp, index) => {
      const yearMatch = exp.period ? exp.period.match(/\b(20\d{2})\b/) : null;
      const year = yearMatch ? yearMatch[1] : new Date().getFullYear();
      console.log('Creating item', index, exp.role, 'year:', year, 'from period:', exp.period);
      
      const li = document.createElement('li');
      li.style.setProperty('--i', index);

      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.id = `timeline-item-${index}`;
      radio.name = 'timeline-item';
      if (index === 0) radio.checked = true;

      const label = document.createElement('label');
      label.setAttribute('for', `timeline-item-${index}`);
      label.textContent = year;

      const h2 = document.createElement('h2');
      h2.textContent = exp.role;

      const p = document.createElement('p');
      p.addEventListener('click', () => openModal(exp));
      
      let content = '';
      
      if (exp.companyLogo) {
        content += `<img src="${exp.companyLogo}" alt="${exp.company}" style="width: 40px; height: 40px; border-radius: 8px; object-fit: cover; float: left; margin-right: 12px; border: 1px solid var(--line);">`;
      }
      
      content += `<strong>${exp.role}</strong><br>`;
      content += `<span style="color: var(--accent)">${exp.company}</span><br>`;
      content += `<small style="color: var(--muted)">${exp.period} • ${exp.location}</small>`;
      
      if (exp.highlights && exp.highlights.length > 0) {
        const topHighlights = exp.highlights.slice(0, 2);
        content += '<br><br>' + topHighlights.map(h => `→ ${h}`).join('<br>');
      }
      
      p.innerHTML = content;

      li.appendChild(radio);
      li.appendChild(label);
      li.appendChild(h2);
      li.appendChild(p);

      wheel.appendChild(li);
      console.log('Item added to wheel', index);
    });
    
    console.log('Timeline rendering complete. Total items in wheel:', wheel.children.length);
  };

  const loadExperiences = async () => {
    try {
      const baseUrl = document.body?.dataset?.baseurl || "";
      const url = `${baseUrl}/assets/data/profile.json`;
      console.log('Loading experiences from:', url);
      
      const response = await fetch(url);
      console.log('Response status:', response.status);
      
      const data = await response.json();
      console.log('Data loaded:', data);
      
      experiencesData = data.timeline || [];
      console.log('Experiences extracted:', experiencesData.length, 'items');
      
      renderTimeline(experiencesData);
    } catch (error) {
      console.error("Failed to load timeline data:", error);
      renderTimeline([]);
    }
  };

  const init = () => {
    console.log('Timeline init called');
    const wheel = document.getElementById("timeline-wheel");
    
    if (!wheel) {
      console.error('Timeline wheel not found on init');
      return;
    }
    
    console.log('Timeline wheel found, initializing...');
    initModal();
    loadExperiences();
  };

  const refresh = () => {
    init();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Force init after a delay if DOM is ready
  setTimeout(() => {
    const wheel = document.getElementById("timeline-wheel");
    if (wheel && wheel.children.length === 0) {
      console.warn('Timeline empty after delay, forcing init...');
      init();
    }
  }, 1000);

  window.addEventListener("contentUpdated", refresh);
})();
