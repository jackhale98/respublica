// Site-wide behavior: theme toggle, search shortcut, toast.
// Everything degrades to plain links without JavaScript.

import { prefersReducedMotion } from "./loader";
import "./history";

const root = document.documentElement;

// ---------------------------------------------------------------- reading settings

// Theme, text size and line spacing (the "Aa" panel), kept in this browser
// only and applied before first paint by public/theme.js. Text size scales
// the library's texts everywhere (--read-scale), not menus and buttons.

const THEMES = ["system", "light", "dark"] as const;
const SIZES = ["s", "m", "l", "xl", "xxl"] as const;
const SIZE_NAMES: Record<string, string> = { s: "Small", m: "Medium", l: "Large", xl: "Larger", xxl: "Largest" };

function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
}

const currentTheme = () => (root.getAttribute("data-theme") as "light" | "dark" | null) ?? "system";
const currentSize = () => root.getAttribute("data-size") ?? "m";
const currentLeading = () => root.getAttribute("data-leading") ?? "normal";

// The passage (or any element with a ref) at the top of the screen, and how
// far below the header it sits: kept in place when the text reflows.
function anchorAtTop(): { el: Element; top: number } | null {
  const line = (document.querySelector<HTMLElement>(".site-header")?.offsetHeight ?? 0) + 8;
  for (const el of document.querySelectorAll("[data-ref], .clause-text, .cl-item, .er-passage")) {
    const r = el.getBoundingClientRect();
    if (r.bottom > line) return { el, top: r.top };
  }
  return null;
}

function keepingPlace(change: () => void) {
  const a = window.scrollY > 0 ? anchorAtTop() : null;
  change();
  if (a) window.scrollBy(0, a.el.getBoundingClientRect().top - a.top);
}

function paintPrefs() {
  const size = currentSize();
  const label = document.querySelector("[data-size-label]");
  if (label) label.textContent = SIZE_NAMES[size];
  const i = SIZES.indexOf(size as (typeof SIZES)[number]);
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-size-step]")) {
    const step = Number(b.dataset.sizeStep);
    b.disabled = i + step < 0 || i + step >= SIZES.length;
  }
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-leading-set]"))
    b.setAttribute("aria-pressed", String(b.dataset.leadingSet === currentLeading()));
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-theme-set]"))
    b.setAttribute("aria-pressed", String(b.dataset.themeSet === currentTheme()));
}

for (const b of document.querySelectorAll<HTMLButtonElement>("[data-size-step]")) {
  b.addEventListener("click", () => {
    const i = SIZES.indexOf(currentSize() as (typeof SIZES)[number]) + Number(b.dataset.sizeStep);
    const next = SIZES[Math.max(0, Math.min(SIZES.length - 1, i))];
    keepingPlace(() => (next === "m" ? root.removeAttribute("data-size") : root.setAttribute("data-size", next)));
    store("rp-size", next === "m" ? null : next);
    paintPrefs();
  });
}
for (const b of document.querySelectorAll<HTMLButtonElement>("[data-leading-set]")) {
  b.addEventListener("click", () => {
    const relaxed = b.dataset.leadingSet === "relaxed";
    keepingPlace(() => (relaxed ? root.setAttribute("data-leading", "relaxed") : root.removeAttribute("data-leading")));
    store("rp-leading", relaxed ? "relaxed" : null);
    paintPrefs();
  });
}
for (const b of document.querySelectorAll<HTMLButtonElement>("[data-theme-set]")) {
  b.addEventListener("click", () => {
    const t = b.dataset.themeSet as (typeof THEMES)[number];
    if (t === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", t);
    store("rp-theme", t === "system" ? null : t);
    paintPrefs();
  });
}

const prefs = document.querySelector<HTMLElement>("[data-prefs]");
const prefsButtons = document.querySelectorAll<HTMLButtonElement>("[data-prefs-open]");
function showPrefs(open: boolean) {
  if (!prefs) return;
  prefs.hidden = !open;
  for (const b of prefsButtons) b.setAttribute("aria-expanded", String(open));
  if (open) {
    paintPrefs();
    prefs.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus({ preventScroll: true });
  }
}
for (const b of prefsButtons) b.addEventListener("click", (e) => {
  e.stopPropagation();
  showPrefs(!!prefs?.hidden);
});
document.addEventListener("click", (e) => {
  if (prefs && !prefs.hidden && !prefs.contains(e.target as Node)) showPrefs(false);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && prefs && !prefs.hidden) {
    showPrefs(false);
    document.querySelector<HTMLButtonElement>(".site-header [data-prefs-open]")?.focus({ preventScroll: true });
  }
});

// ---------------------------------------------------------------- logo egg

// Pressing the footer logo plays the nib loader once (decision 30). The SVG's
// animations all begin with #rpeggGo and freeze on the resting pose.
const egg = document.querySelector<HTMLElement>("[data-logo-egg]");
if (egg && !prefersReducedMotion()) {
  const go = egg.querySelector<SVGAnimationElement>("#rpeggGo");
  const ring = egg.querySelector<SVGPathElement>("[data-egg-ring]");
  // The ring draws on, then off, over the same 4 s as the SMIL animations
  // (which Firefox's CSP handling would block for these two properties).
  const draw = { easing: "cubic-bezier(0.45, 0, 0.25, 1)" };
  const play = () => {
    go?.beginElement();
    ring?.animate(
      [
        { offset: 0, strokeDashoffset: 239, opacity: 0 },
        { offset: 0.2, strokeDashoffset: 239, opacity: 0 },
        { offset: 0.2, strokeDashoffset: 239, opacity: 1, ...draw },
        { offset: 0.64, strokeDashoffset: 0, opacity: 1 },
        { offset: 0.76, strokeDashoffset: 0, opacity: 1, ...draw },
        { offset: 0.92, strokeDashoffset: -239, opacity: 1 },
        { offset: 0.92, strokeDashoffset: -239, opacity: 0 },
        { offset: 1, strokeDashoffset: -239, opacity: 0 },
      ],
      { duration: 4000, fill: "forwards" },
    );
  };
  egg.setAttribute("role", "button");
  egg.setAttribute("aria-label", "Play the logo animation");
  egg.tabIndex = 0;
  egg.addEventListener("click", play);
  egg.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      play();
    }
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
