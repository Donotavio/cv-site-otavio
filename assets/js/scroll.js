(() => {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  let sections = [];
  let ticking = false;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

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
    if (!sections.length) return;
    const viewportHeight = window.innerHeight || 0;
    const strength = window.innerWidth < 900 ? 24 : 60;
    const blurMax = window.innerWidth < 900 ? 3 : 6;

    sections.forEach((section) => {
      updateSection(section, viewportHeight, strength, blurMax);
    });
  };

  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(() => {
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
