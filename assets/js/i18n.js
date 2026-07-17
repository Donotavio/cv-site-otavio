const supportedLanguages = ["pt-BR", "en-US", "es-ES"];
const defaultLanguage = "pt-BR";
const storageKey = "preferredLanguage";
const cvFiles = {
  "pt-BR": "/assets/cv/cv-otavio-ptBR.pdf",
  "en-US": "/assets/cv/cv-otavio-en.pdf",
  "es-ES": "/assets/cv/cv-otavio-es.pdf",
};

const getBaseUrl = () => {
  const base = document.body?.dataset?.baseurl || "";
  if (!base || base === "/") {
    return "";
  }
  return base;
};

const detectLanguage = () => {
  const saved = localStorage.getItem(storageKey);
  if (saved && supportedLanguages.includes(saved)) {
    return saved;
  }

  const browserLanguages = navigator.languages || [navigator.language];
  for (const lang of browserLanguages) {
    if (supportedLanguages.includes(lang)) {
      return lang;
    }
    const normalized = lang.split("-")[0];
    const match = supportedLanguages.find((supported) => supported.startsWith(normalized));
    if (match) {
      return match;
    }
  }
  return defaultLanguage;
};

// Cache em memória por idioma — evita refetch a cada navegação SPA
// (astro:page-load reaplica traduções em toda navegação).
const translationCache = {};

const fetchTranslations = async (lang) => {
  if (translationCache[lang]) {
    return translationCache[lang];
  }
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}/assets/i18n/${lang}.json`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to load translations");
  }
  const json = await response.json();
  translationCache[lang] = json;
  return json;
};

const resolveKey = (obj, key) => {
  return key.split(".").reduce((acc, part) => (acc ? acc[part] : undefined), obj);
};

let currentTranslations = {};
let currentLanguage = defaultLanguage;

window.i18n = {
  t: (key) => resolveKey(currentTranslations, key),
  get lang() {
    return currentLanguage;
  },
};

const applyTranslations = (translations, lang) => {
  const htmlRoot = document.getElementById('html-root') || document.documentElement;
  htmlRoot.lang = lang;
  currentTranslations = translations;
  currentLanguage = lang;
  
  const pageTitle = document.getElementById('page-title');
  if (pageTitle && translations.hero?.role) {
    pageTitle.textContent = `${translations.hero.role} | Otávio Ribeiro`;
  }
  
  const pageDescription = document.getElementById('page-description');
  if (pageDescription && translations.hero?.summary) {
    pageDescription.setAttribute('content', translations.hero.summary);
  }
  
  document.querySelectorAll("[data-i18n-key]").forEach((el) => {
    const key = el.dataset.i18nKey;
    const value = resolveKey(translations, key);
    if (value !== undefined) {
      el.textContent = value;
    }
  });

  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    const key = el.dataset.i18nAria;
    const value = resolveKey(translations, key);
    if (value !== undefined) {
      el.setAttribute("aria-label", value);
    }
  });

  /**
   * Padrão genérico: data-i18n-attr="attr1:key1,attr2:key2"
   * Permite traduzir QUALQUER atributo HTML (title, placeholder, value,
   * aria-label, data-* etc.) numa única declaração. Mantém total
   * retrocompatibilidade com data-i18n-key (textContent) e data-i18n-aria
   * (atalho legacy para aria-label).
   *
   * Exemplo:
   *   <input data-i18n-attr="placeholder:contact.email_label,title:a11y.help" />
   */
  document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    const spec = el.dataset.i18nAttr || "";
    spec.split(",").forEach((pair) => {
      const trimmed = pair.trim();
      if (!trimmed) return;
      const colonIdx = trimmed.indexOf(":");
      if (colonIdx === -1) return;
      const attr = trimmed.slice(0, colonIdx).trim();
      const key = trimmed.slice(colonIdx + 1).trim();
      if (!attr || !key) return;
      const value = resolveKey(translations, key);
      if (value !== undefined) {
        el.setAttribute(attr, value);
      }
    });
  });

  const cvLink = document.getElementById("cv-download");
  if (cvLink && cvFiles[lang]) {
    const baseUrl = getBaseUrl();
    cvLink.href = `${baseUrl}${cvFiles[lang]}`;
  }

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });

  window.dispatchEvent(
    new CustomEvent("languageChanged", {
      detail: { lang, translations },
    })
  );
};

const setLanguage = async (lang) => {
  const normalized = supportedLanguages.includes(lang) ? lang : defaultLanguage;
  const translations = await fetchTranslations(normalized);
  localStorage.setItem(storageKey, normalized);
  applyTranslations(translations, normalized);
};

const initI18n = () => {
  const initial = detectLanguage();
  setLanguage(initial).catch(() => setLanguage(defaultLanguage));

  // Após o swap do <ClientRouter />, os .lang-btn são elementos NOVOS — re-liga
  // o click a cada page-load. São elementos frescos, então não há duplicação.
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setLanguage(btn.dataset.lang).catch(() => setLanguage(defaultLanguage));
    });
  });
};

// astro:page-load (não DOMContentLoaded): dispara no 1º carregamento E após
// cada navegação SPA do <ClientRouter />. Sem isso, o DOM novo vinha em pt-BR
// (SSG) e o seletor de idioma parava de responder após a 1ª navegação.
// __i18nBooted evita registrar o listener duas vezes se o script for reavaliado.
if (!window.__i18nBooted) {
  window.__i18nBooted = true;
  document.addEventListener("astro:page-load", initI18n);
}
