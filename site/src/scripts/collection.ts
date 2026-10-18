// Filter the papers by author and by title/number. The filter is kept in
// the URL (?author=madison&q=executive) so a filtered view can be shared.

const bar = document.querySelector<HTMLElement>("[data-filters]");
const items = Array.from(document.querySelectorAll<HTMLElement>("[data-papers] > li"));
const input = document.querySelector<HTMLInputElement>("[data-filter-text]");
const showing = document.querySelector<HTMLElement>("[data-showing]");
const noMatch = document.querySelector<HTMLElement>("[data-no-match]");

const params = new URLSearchParams(location.search);
let author = params.get("author") || "";
if (input) input.value = params.get("q") || "";

function apply() {
  const q = (input?.value || "").trim().toLowerCase();
  let n = 0;
  for (const li of items) {
    const ok = (!author || li.dataset.author === author) && (!q || (li.dataset.text || "").includes(q));
    li.hidden = !ok;
    if (ok) n++;
  }
  for (const b of bar?.querySelectorAll<HTMLButtonElement>("button[data-author]") ?? []) {
    b.setAttribute("aria-pressed", String(b.dataset.author === author));
  }
  if (showing) showing.textContent = n === items.length ? `Showing all ${n} papers` : `Showing ${n} of ${items.length} papers`;
  if (noMatch) noMatch.hidden = n > 0;
  const u = new URL(location.href);
  author ? u.searchParams.set("author", author) : u.searchParams.delete("author");
  q ? u.searchParams.set("q", q) : u.searchParams.delete("q");
  history.replaceState(null, "", u);
}

bar?.addEventListener("click", (e) => {
  const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-author]");
  if (!b) return;
  author = b.dataset.author || "";
  apply();
});
input?.addEventListener("input", apply);
document.querySelector("[data-reset]")?.addEventListener("click", () => {
  author = "";
  if (input) input.value = "";
  apply();
});
apply();
