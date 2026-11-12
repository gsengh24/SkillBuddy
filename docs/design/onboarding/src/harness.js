// Renders each <template data-variant> at phone 390px and desktop 1280px, scaled to fit,
// and wires the few mockup interactions (chip and card toggles, segmented controls, counters).
(() => {
  const main = document.querySelector("main");
  const SIZES = { phone: [390, "Phone · 390px"], desk: [1280, "Desktop · 1280px"] };

  for (const t of document.querySelectorAll("template[data-variant]")) {
    const sec = document.createElement("section");
    sec.className = "mk-variant";
    const vh = document.createElement("div");
    vh.className = "mk-vh";
    vh.innerHTML = `<h2 class="mono"></h2>${t.dataset.note ? "<p></p>" : ""}`;
    vh.querySelector("h2").textContent = t.dataset.variant;
    if (t.dataset.note) vh.querySelector("p").textContent = t.dataset.note;
    const row = document.createElement("div");
    row.className = "mk-row";
    sec.append(vh, row);
    for (const [key, [w, cap]] of Object.entries(SIZES)) {
      const col = document.createElement("div");
      col.className = "mk-" + key;
      col.innerHTML = `<p class="mk-cap mono">${cap}</p><div class="mk-fit"><div class="mk-scale" style="width:${w}px"><div class="mk-frame"></div></div></div>`;
      const frame = col.querySelector(".mk-frame");
      frame.append(t.content.cloneNode(true));
      if (t.dataset.clear !== undefined) frame.querySelectorAll("[aria-pressed]").forEach((b) => b.setAttribute("aria-pressed", "false"));
      row.append(col);
    }
    main.append(sec);
  }

  const update = (scope) => {
    const on = (sel) => scope.querySelectorAll(`${sel}[aria-pressed="true"]`);
    const n = on("[data-pick]").length;
    scope.querySelectorAll("[data-count]").forEach((c) => (c.textContent = c.dataset.count.replace("{n}", c.dataset.of ? on(c.dataset.of).length : n)));
    scope.querySelectorAll("[data-mirror]").forEach((m) => {
      const tags = [...on(m.dataset.mirror)].map((b) => {
        const t = document.createElement("span");
        t.className = "tag want";
        t.textContent = b.textContent.trim();
        return t;
      });
      if (!tags.length) {
        const e = document.createElement("span");
        e.className = "tag empty";
        e.textContent = m.dataset.empty || "None yet";
        tags.push(e);
      }
      m.replaceChildren(...tags);
    });
    scope.querySelectorAll("[data-needs]").forEach((b) => (b.disabled = n < Number(b.dataset.needs)));
  };
  document.querySelectorAll("[data-scope]").forEach(update);

  const fit = () => {
    for (const f of document.querySelectorAll(".mk-fit")) {
      const s = f.firstElementChild;
      const k = Math.min(1, f.clientWidth / parseFloat(s.style.width));
      s.style.transform = k < 1 ? `scale(${k})` : "";
      f.style.height = s.offsetHeight * k + "px";
    }
  };
  new ResizeObserver(fit).observe(document.body);
  fit();
  document.fonts && document.fonts.ready.then(fit);

  document.addEventListener("click", (e) => {
    const radio = e.target.closest('[role="radio"]');
    if (radio) {
      radio.closest('[role="radiogroup"]').querySelectorAll('[role="radio"]').forEach((r) => r.setAttribute("aria-checked", String(r === radio)));
      return;
    }
    const b = e.target.closest("button[aria-pressed]");
    if (!b) { if (e.target.closest("a[href='#']")) e.preventDefault(); return; }
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(on));
    if (on && b.classList.contains("chip")) { b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop"); }
    const scope = b.closest("[data-scope]");
    if (scope) { update(scope); fit(); }
  });
  document.addEventListener("toggle", fit, true);
})();
