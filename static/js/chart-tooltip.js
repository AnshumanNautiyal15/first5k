// Hover / focus / tap tooltip for server-rendered SVG bar charts.
document.querySelectorAll("[data-chart]").forEach((figure) => {
  const tip = figure.querySelector("[data-chart-tip]");
  const show = (target) => {
    const box = figure.getBoundingClientRect();
    const r = target.getBoundingClientRect();
    tip.textContent = target.dataset.tip;
    tip.classList.remove("hidden");
    const left = Math.min(Math.max(r.left - box.left + r.width / 2 - tip.offsetWidth / 2, 0), box.width - tip.offsetWidth);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(r.top - box.top - tip.offsetHeight - 6, 0)}px`;
  };
  const hide = () => tip.classList.add("hidden");
  figure.querySelectorAll("[data-tip]").forEach((el) => {
    el.querySelector("title")?.remove(); // avoid a double native tooltip once JS is running
    el.addEventListener("pointerenter", () => show(el));
    el.addEventListener("focus", () => show(el));
    el.addEventListener("click", () => show(el));
    el.addEventListener("pointerleave", hide);
    el.addEventListener("blur", hide);
  });
});
