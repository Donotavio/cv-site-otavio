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

const fetchTranslations = async (lang) => {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}/assets/i18n/${lang}.json`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to load translations");
  }
  return response.json();
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

document.addEventListener("DOMContentLoaded", () => {
  const initial = detectLanguage();
  setLanguage(initial).catch(() => setLanguage(defaultLanguage));

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setLanguage(btn.dataset.lang).catch(() => setLanguage(defaultLanguage));
    });
  });
});
