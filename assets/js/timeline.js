(() => {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  let observer;
  let items = [];
  let timeline;
  let ticking = false;
  let experiencesData = [];
  let currentYear = null;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const updateProgressLine = () => {
    if (!timeline) return;
    const rect = timeline.getBoundingClientRect();
    const viewportHeight = window.innerHeight || 0;
    const start = rect.top + window.scrollY;
    const end = start + rect.height;
    const current = window.scrollY + viewportHeight * 0.6;
    const progress = clamp((current - start) / (end - start), 0, 1);

    timeline.style.setProperty(
      "--timeline-progress",
      `${(progress * 100).toFixed(2)}%`
    );
  };

  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(() => {
      updateProgressLine();
      ticking = false;
    });
  };

  const observeItems = () => {
    if (!items.length) return;

    if (prefersReducedMotion) {
      items.forEach((item) => item.classList.add("is-active"));
      return;
    }

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-active");
          }
        });
      },
      { threshold: 0.25 }
    );

    items.forEach((item) => observer.observe(item));
  };

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
      modalCompanyLogo.innerHTML = experience.companyLogo
        ? `<img src="${experience.companyLogo}" alt="${experience.company}" onerror="this.style.display='none'">`
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

  const createYearButtons = (years) => {
    const yearsContainer = document.getElementById("timeline-years");
    if (!yearsContainer) return;

    yearsContainer.innerHTML = years
      .map(
        (year) => `
        <button class="year-button" data-year="${year}">
          <span>${year}</span>
        </button>
      `
      )
      .join("");

    const buttons = yearsContainer.querySelectorAll(".year-button");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const year = parseInt(btn.dataset.year);
        filterByYear(year);
        updateActiveYear(year);
      });
    });

    if (years.length > 0) {
      updateActiveYear(years[0]);
    }
  };

  const updateActiveYear = (year) => {
    currentYear = year;
    const buttons = document.querySelectorAll(".year-button");
    buttons.forEach((btn) => {
      if (parseInt(btn.dataset.year) === year) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  };

  const filterByYear = (year) => {
    items.forEach((item) => {
      const itemYear = parseInt(item.dataset.year);
      if (itemYear === year) {
        item.style.display = "";
      } else {
        item.style.display = "none";
      }
    });

    setTimeout(() => {
      updateProgressLine();
    }, 100);
  };

  const renderTimeline = (experiences) => {
    const container = document.getElementById("timeline-container");
    const template = document.getElementById("timeline-item-template");
    const emptyState = document.getElementById("timeline-empty");

    if (!container || !template) return;

    container.innerHTML = "";

    if (!experiences || experiences.length === 0) {
      if (emptyState) emptyState.classList.add("visible");
      return;
    }

    if (emptyState) emptyState.classList.remove("visible");

    experiences.forEach((exp) => {
      const clone = template.content.cloneNode(true);
      const item = clone.querySelector(".timeline-item");
      const card = clone.querySelector(".timeline-card");

      if (item) item.dataset.year = exp.year;

      const logoWrapper = clone.querySelector(".company-logo-wrapper");
      if (logoWrapper && exp.companyLogo) {
        logoWrapper.innerHTML = `<img class="company-logo" src="${exp.companyLogo}" alt="${exp.company}" onerror="this.style.display='none'">`;
      }

      const role = clone.querySelector(".timeline-role");
      if (role) role.textContent = exp.role;

      const company = clone.querySelector(".timeline-company");
      if (company) company.textContent = exp.company;

      const period = clone.querySelector(".timeline-period");
      if (period) period.textContent = exp.period;

      const location = clone.querySelector(".timeline-location");
      if (location) location.textContent = exp.location;

      const highlights = clone.querySelector(".timeline-highlights");
      if (highlights && exp.highlights) {
        highlights.innerHTML = exp.highlights
          .map((h) => `<li>${h}</li>`)
          .join("");
      }

      if (card) {
        card.addEventListener("click", () => openModal(exp));
        card.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openModal(exp);
          }
        });
      }

      container.appendChild(clone);
    });

    items = Array.from(container.querySelectorAll(".timeline-item"));
    observeItems();

    const years = [...new Set(experiences.map((e) => e.year))].sort((a, b) => b - a);
    createYearButtons(years);

    if (years.length > 0) {
      filterByYear(years[0]);
    }
  };

  const loadExperiences = async () => {
    try {
      const response = await fetch("/assets/data/linkedin_profile.json");
      const data = await response.json();
      experiencesData = data.experience || [];
      renderTimeline(experiencesData);
    } catch (error) {
      console.error("Failed to load timeline data:", error);
      renderTimeline([]);
    }
  };

  const init = () => {
    timeline = document.querySelector("[data-timeline]");
    if (!timeline) return;

    initModal();
    loadExperiences();
    updateProgressLine();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", updateProgressLine);
  };

  const destroy = () => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", updateProgressLine);
  };

  const refresh = () => {
    destroy();
    init();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.addEventListener("contentUpdated", refresh);
})();
