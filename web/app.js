(() => {
  const navEl = document.getElementById("rail-nav");
  const paperEl = document.getElementById("paper");
  const mastDateEl = document.getElementById("mast-date");
  const metaKindEl = document.getElementById("meta-kind");
  const metaTitleEl = document.getElementById("meta-title");
  const tkGenEl = document.getElementById("tk-gen");
  const tkSrcEl = document.getElementById("tk-src");
  const footTimeEl = document.getElementById("foot-time");

  let manifest = null;
  let currentKey = null;
  let stockAliases = new Map();

  function keyOf(kind, entry) {
    if (kind === "daily") return `daily/${entry.date}`;
    if (kind === "stock") return `stock/${entry.id}`;
    return `weekly/${entry.start}_${entry.end}`;
  }

  function pathOf(kind, entry) {
    return kind === "stock"
      ? `../notes/stock-timeline/${entry.file}`
      : `../reports/${entry.file}`;
  }

  function indexStocks() {
    stockAliases = new Map();
    (manifest.stocks || []).forEach((s) => {
      const keys = [s.id, s.name, s.file.replace(/\.md$/, ""), ...(s.aliases || [])];
      keys.forEach((k) => stockAliases.set(k.toLowerCase(), s));
    });
  }

  // [[AVGO]] → link to that stock's timeline; unknown targets stay as plain text.
  function linkifyWikilinks(md) {
    return md.replace(/\[\[([^\]|]+)\]\]/g, (full, target) => {
      const stock = stockAliases.get(target.trim().toLowerCase());
      return stock ? `[${target}](#stock/${stock.id})` : full;
    });
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
      metaTitleEl.textContent = entry.title;
    } else if (kind === "stock") {
      renderDateMasthead(entry.ticker);
      metaKindEl.textContent = "STOCK";
      metaTitleEl.textContent =
        `${entry.name}　涵蓋 ${entry.start} › ${entry.end}　更新 ${entry.updated}`;
    } else {
      renderDateMasthead(`${entry.start.slice(5)} › ${entry.end.slice(5)}`);
      metaKindEl.textContent = "WEEKLY";
      metaTitleEl.textContent = entry.title;
    }
    metaKindEl.className = "meta-tag" + (kind === "daily" ? "" : ` ${kind}`);
    tkSrcEl.textContent =
      kind === "stock" ? "notes/stock-timeline/*.md" : "reports/*.md";

    try {
      const res = await fetch(pathOf(kind, entry));
      if (!res.ok) throw new Error(res.statusText);
      const md = await res.text();
      paperEl.classList.remove("swap");
      // eslint-disable-next-line no-unused-expressions
      paperEl.offsetHeight;
      paperEl.innerHTML = marked.parse(linkifyWikilinks(md));
      paperEl.classList.add("swap");
      window.scrollTo({ top: 0 });
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
    if (kind === "daily") label.textContent = entry.date;
    else if (kind === "stock") label.textContent = `${entry.ticker}　${entry.name}`;
    else label.textContent = `${entry.start.slice(5)}–${entry.end.slice(5)}`;

    const tag = document.createElement("span");
    tag.className = "tag";
    if (kind === "stock") tag.textContent = (entry.updated || "").slice(5);
    else tag.textContent = isLatest ? "● LIVE" : (kind === "weekly" ? "WK" : "");

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

    const stocks = manifest.stocks || [];
    const dailyItems = manifest.daily.map((e, i) => makeItem("daily", e, i === 0));
    const weeklyItems = manifest.weekly.map((e, i) => makeItem("weekly", e, i === 0));
    const stockItems = stocks.map((e) => makeItem("stock", e, false));

    if (stockItems.length) {
      navEl.appendChild(mkSection("STOCKS", stockItems, stocks.length));
    }
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
    if (kind === "stock") {
      const id = decodeURIComponent(rest || "");
      return ["stock", (manifest.stocks || []).find((e) => e.id === id)];
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

    indexStocks();
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
