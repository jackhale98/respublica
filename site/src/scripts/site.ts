// Site-wide behavior: theme toggle, search shortcut, toast.
// Everything degrades to plain links without JavaScript.

const root = document.documentElement;

// ---------------------------------------------------------------- theme

const THEMES = ["system", "light", "dark"] as const;

function currentTheme(): (typeof THEMES)[number] {
  const t = root.getAttribute("data-theme");
  return t === "light" || t === "dark" ? t : "system";
}

function setTheme(theme: (typeof THEMES)[number]) {
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  try {
    if (theme === "system") localStorage.removeItem("rp-theme");
    else localStorage.setItem("rp-theme", theme);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-theme-toggle]")) {
    b.setAttribute("aria-label", `Color theme: ${theme}`);
    b.title = `Theme: ${theme}`;
  }
}

for (const b of document.querySelectorAll<HTMLButtonElement>("[data-theme-toggle]")) {
  b.title = `Theme: ${currentTheme()}`;
  b.addEventListener("click", () => {
    const next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    setTheme(next);
    toast(`Theme: ${next}`);
  });
}

// ---------------------------------------------------------------- toast

let toastTimer: number | undefined;
export function toast(message: string) {
  const el = document.querySelector<HTMLElement>("[data-toast]");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => el.classList.remove("show"), 1800);
}
(window as any).rpToast = toast;

// ---------------------------------------------------------------- search

const dialog = document.querySelector<HTMLDialogElement>("#search-dialog");
let searchModule: Promise<typeof import("./search")> | null = null;

async function openSearch(initial = "") {
  if (!dialog) return;
  if (location.pathname === `${import.meta.env.BASE_URL.replace(/\/$/, "")}/search/`) {
    document.querySelector<HTMLInputElement>(".search-page [data-search-input]")?.focus();
    return;
  }
  searchModule ??= import("./search");
  const mod = await searchModule;
  dialog.showModal();
  mod.attachPalette(dialog, initial);
}

for (const trigger of document.querySelectorAll<HTMLElement>("[data-search-open]")) {
  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    openSearch();
  });
}

dialog?.querySelector("[data-search-close]")?.addEventListener("click", () => dialog.close());
dialog?.addEventListener("click", (e) => {
  if (e.target === dialog) dialog.close();
});

function isTyping(t: EventTarget | null) {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
}

document.addEventListener("keydown", (e) => {
  if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !isTyping(e.target) && !e.metaKey && !e.ctrlKey)) {
    e.preventDefault();
    openSearch();
  }
});
