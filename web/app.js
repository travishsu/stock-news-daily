(() => {
  const navEl = document.getElementById("rail-nav");
  const paperEl = document.getElementById("paper");
  const mastDateEl = document.getElementById("mast-date");
  const metaKindEl = document.getElementById("meta-kind");
  const metaTitleEl = document.getElementById("meta-title");
  const tkGenEl = document.getElementById("tk-gen");
  const footTimeEl = document.getElementById("foot-time");

  let manifest = null;
  let currentKey = null;

  function keyOf(kind, entry) {
    return kind === "daily" ? `daily/${entry.date}` : `weekly/${entry.start}_${entry.end}`;
  }

  function renderDateMasthead(text) {
    mastDateEl.innerHTML = "";
    [...text].forEach((ch) => {
      const span = document.createElement("span");
      span.className = ch === "-" ? "dash" : "d";
      span.textContent = ch === "-" ? "—" : ch;
      mastDateEl.appendChild(span);
    });
    const kids = mastDateEl.children;
    for (let i = 0; i < kids.length; i++) {
      kids[i].style.animation = "none";
      // eslint-disable-next-line no-unused-expressions
      kids[i].offsetHeight;
      kids[i].style.animation = `fadeUp .6s cubic-bezier(.2,.7,.2,1) ${0.05 * i + 0.05}s forwards`;
    }
  }

  function setSidebarActive(key) {
    document.querySelectorAll(".rail-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.key === key);
    });
  }

  async function loadReport(kind, entry) {
    const key = keyOf(kind, entry);
    currentKey = key;
    setSidebarActive(key);

    if (kind === "daily") {
      renderDateMasthead(entry.date);
      metaKindEl.textContent = "DAILY";
      metaKindEl.classList.remove("weekly");
    } else {
      renderDateMasthead(`${entry.start.slice(5)} › ${entry.end.slice(5)}`);
      metaKindEl.textContent = "WEEKLY";
      metaKindEl.classList.add("weekly");
    }
    metaTitleEl.textContent = entry.title;

    try {
      const res = await fetch(`../reports/${entry.file}`);
      if (!res.ok) throw new Error(res.statusText);
      const md = await res.text();
      paperEl.classList.remove("swap");
      // eslint-disable-next-line no-unused-expressions
      paperEl.offsetHeight;
      paperEl.innerHTML = marked.parse(md);
      paperEl.classList.add("swap");
    } catch (err) {
      paperEl.innerHTML = `<p class="empty">讀取失敗：${entry.file}（${err.message}）</p>`;
    }

    const hash = `#${key}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }

  function makeItem(kind, entry, isLatest) {
    const li = document.createElement("li");
    li.className = "rail-item" + (isLatest ? " is-live" : "");
    li.dataset.key = keyOf(kind, entry);

    const mark = document.createElement("span");
    mark.className = "mark";

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = kind === "daily" ? entry.date : `${entry.start.slice(5)}–${entry.end.slice(5)}`;

    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = isLatest ? "● LIVE" : (kind === "weekly" ? "WK" : "");

    li.appendChild(mark);
    li.appendChild(label);
    li.appendChild(tag);

    li.addEventListener("click", () => loadReport(kind, entry));
    return li;
  }

  function renderSidebar() {
    navEl.innerHTML = "";

    const mkSection = (title, entries, count) => {
      const sec = document.createElement("div");
      sec.className = "rail-section";
      const h = document.createElement("div");
      h.className = "rail-section-title";
      h.innerHTML = `<span>${title}</span><span class="rail-section-count">${count}</span>`;
      const ul = document.createElement("ul");
      ul.className = "rail-list";
      entries.forEach((el, i) => {
        el.style.animationDelay = `${0.25 + i * 0.025}s`;
        ul.appendChild(el);
      });
      sec.appendChild(h);
      sec.appendChild(ul);
      return sec;
    };

    const dailyItems = manifest.daily.map((e, i) => makeItem("daily", e, i === 0));
    const weeklyItems = manifest.weekly.map((e, i) => makeItem("weekly", e, i === 0));

    navEl.appendChild(mkSection("DAILY", dailyItems, manifest.daily.length));
    navEl.appendChild(mkSection("WEEKLY", weeklyItems, manifest.weekly.length));
  }

  function resolveFromHash() {
    const h = location.hash.replace(/^#/, "");
    if (!h) return null;
    const [kind, rest] = h.split("/");
    if (kind === "daily") {
      return ["daily", manifest.daily.find((e) => e.date === rest)];
    }
    if (kind === "weekly") {
      const [start, end] = rest.split("_");
      return ["weekly", manifest.weekly.find((e) => e.start === start && e.end === end)];
    }
    return null;
  }

  async function init() {
    try {
      const res = await fetch("manifest.json");
      manifest = await res.json();
    } catch {
      navEl.innerHTML = `<div class="rail-loading">manifest.json 不存在。請先執行：<br><code>uv run python scripts/build_web.py</code></div>`;
      return;
    }

    const gen = manifest.generated_at || "—";
    tkGenEl.textContent = gen;
    footTimeEl.textContent = gen.replace("T", " ");

    renderSidebar();

    const hashMatch = resolveFromHash();
    if (hashMatch && hashMatch[1]) {
      loadReport(hashMatch[0], hashMatch[1]);
    } else if (manifest.daily.length) {
      loadReport("daily", manifest.daily[0]);
    } else if (manifest.weekly.length) {
      loadReport("weekly", manifest.weekly[0]);
    }
  }

  window.addEventListener("hashchange", () => {
    const m = resolveFromHash();
    if (m && m[1] && keyOf(m[0], m[1]) !== currentKey) loadReport(m[0], m[1]);
  });

  init();
})();
