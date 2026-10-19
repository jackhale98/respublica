// The "Where you've been" list (history.ts keeps the places; this draws
// them). Loaded the first time the list is opened.

import type { store as Store } from "./history";

type S = typeof Store;
let wired = false;

function ago(t: number): string {
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? "yesterday" : d < 30 ? `${d} days ago` : new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const span = (className: string, textContent: string) => Object.assign(document.createElement("span"), { className, textContent });

function render(dialog: HTMLDialogElement, store: S) {
  const s = store.load();
  const list = dialog.querySelector<HTMLOListElement>("[data-history-list]");
  if (!list) return;
  list.replaceChildren();
  if (!s.items.length) {
    const li = document.createElement("li");
    li.className = "history-empty";
    li.textContent = "Nothing yet. The places you read will appear here.";
    list.append(li);
  }
  for (const item of [...s.items].reverse()) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = item.u;
    if (item.id === s.cur) {
      li.className = "current";
      a.setAttribute("aria-current", "location");
    }
    a.append(span("h-title", item.t), span("h-time", ago(item.at)));
    if (item.w) a.append(span("h-where", item.w));
    a.addEventListener("click", (e) => {
      e.preventDefault();
      store.go(item.id);
    });
    li.append(a);
    list.append(li);
  }
  for (const b of dialog.querySelectorAll<HTMLButtonElement>("[data-history-step]"))
    b.disabled = !store.neighbour(Number(b.dataset.historyStep));
  const clear = dialog.querySelector<HTMLButtonElement>("[data-history-clear]");
  if (clear) clear.disabled = !s.items.length;
}

export function open(dialog: HTMLDialogElement, store: S) {
  if (!wired) {
    wired = true;
    dialog.querySelector("[data-history-close]")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
    for (const b of dialog.querySelectorAll<HTMLButtonElement>("[data-history-step]")) {
      b.addEventListener("click", () => {
        const n = store.neighbour(Number(b.dataset.historyStep));
        if (n) store.go(n.id);
      });
    }
    dialog.querySelector("[data-history-clear]")?.addEventListener("click", () => {
      store.write(store.KEY, null);
      store.write(store.WORKS, null);
      store.clearCurrent();
      render(dialog, store);
      for (const el of document.querySelectorAll<HTMLElement>("[data-continue]")) el.hidden = true;
    });
  }
  render(dialog, store);
  dialog.showModal();
  dialog.querySelector<HTMLElement>(".history-list .current a, [data-history-close]")?.focus({ preventScroll: true });
}
