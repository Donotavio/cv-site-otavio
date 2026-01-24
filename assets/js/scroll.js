(() => {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  let sections = [];
  let ticking = false;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  // Atualizar barra de progresso de scroll
  const updateScrollProgress = () => {
    const progressBar = document.getElementById('scroll-progress-bar');
    if (!progressBar) return;

    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    const scrollTop = window.scrollY;
    const maxScroll = documentHeight - windowHeight;
    const scrollPercent = maxScroll > 0 ? (scrollTop / maxScroll) * 100 : 0;

    progressBar.style.height = `${Math.min(100, Math.max(0, scrollPercent))}%`;
  };

  const updateSection = (section, viewportHeight, strength, blurMax) => {
    const rect = section.getBoundingClientRect();
    const midPoint = rect.top + rect.height / 2;
    const distance = (midPoint - viewportHeight / 2) / viewportHeight;
    const normalized = clamp(distance, -1, 1);
    const progress = 1 - Math.min(1, Math.abs(normalized));

    const opacity = 0.4 + progress * 0.6;
    const scale = 0.96 + progress * 0.04;
    const blur = (1 - progress) * blurMax;
    const shift = normalized * -strength;

    section.style.setProperty("--scroll-progress", progress.toFixed(3));
    section.style.setProperty("--scroll-opacity", opacity.toFixed(3));
    section.style.setProperty("--scroll-scale", scale.toFixed(3));
    section.style.setProperty("--scroll-blur", `${blur.toFixed(2)}px`);
    section.style.setProperty("--scroll-shift", `${shift.toFixed(1)}px`);
    section.dataset.scrollActive = progress > 0.6 ? "true" : "false";
  };

  const update = () => {
    if (prefersReducedMotion) return;
    const viewportHeight = window.innerHeight;
    const strength = 18;
    const blurMax = 4;
    sections.forEach((section) =>
      updateSection(section, viewportHeight, strength, blurMax)
    );
    updateScrollProgress();
  };

  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      update();
      ticking = false;
    });
  };

  const init = () => {
    sections = Array.from(document.querySelectorAll("[data-scroll-section]"));
    if (!sections.length) return;

    if (prefersReducedMotion) {
      sections.forEach((section) => {
        section.style.setProperty("--scroll-progress", "1");
        section.style.setProperty("--scroll-opacity", "1");
        section.style.setProperty("--scroll-scale", "1");
        section.style.setProperty("--scroll-blur", "0px");
        section.style.setProperty("--scroll-shift", "0px");
        section.dataset.scrollActive = "true";
      });
      updateScrollProgress();
      window.addEventListener("scroll", updateScrollProgress, { passive: true });
      window.addEventListener("resize", updateScrollProgress);
      return;
    }

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", update);
  };

  const refresh = () => {
    sections = Array.from(document.querySelectorAll("[data-scroll-section]"));
    update();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.addEventListener("contentUpdated", refresh);
})();
