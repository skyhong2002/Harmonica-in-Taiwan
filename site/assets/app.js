(function () {
  const data = window.HARMONICA_OBSERVE_DATA || {
    entries: [],
    stats: { categories: {}, totalEntries: 0, verifiedEntries: 0 },
    generatedAt: "-",
  };
  const feedData = window.HARMONICA_OBSERVE_FEEDS || {
    generatedAt: "-",
    feeds: [],
    updates: [],
  };

  const state = {
    query: "",
    category: "全部",
    status: "all",
  };

  const categoryOrder = [
    "全部",
    "活動資訊",
    "團體樂團",
    "演奏者",
    "學校社團",
    "教學器材",
    "場館平台",
    "國際交流",
    "其他來源",
  ];

  const directoryList = document.querySelector("#directory-list");
  const latestFeedGrid = document.querySelector("#latest-feed-grid");
  const spotlightList = document.querySelector("#spotlight-list");
  const resultCount = document.querySelector("#result-count");
  const tabs = document.querySelector("#category-tabs");
  const directorySearch = document.querySelector("#directory-search-input");
  const heroSearch = document.querySelector("#hero-search-input");
  const statusFilter = document.querySelector("#status-filter");

  function setStat(name, value) {
    document.querySelectorAll(`[data-stat="${name}"]`).forEach((node) => {
      node.textContent = value;
    });
  }

  function normalize(value) {
    return String(value || "").trim().toLocaleLowerCase("zh-Hant");
  }

  function searchableText(entry) {
    return normalize(
      [
        entry.name,
        entry.nameEn,
        entry.category,
        entry.type,
        entry.tier,
        entry.region,
        entry.cityOrFocus,
        entry.summary,
        entry.keywords,
        entry.sourceStatus,
      ].join(" ")
    );
  }

  function statusClass(status) {
    if (status === "已查核") return "status-verified";
    if (status === "部分查核") return "status-partial";
    return "status-pending";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderLinks(links) {
    return (links || [])
      .map(
        (link) => `
          <a href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">
            ${escapeHtml(link.label)}
          </a>
        `
      )
      .join("");
  }

  function entryCard(entry) {
    const meta = [
      entry.latestUpdateLocal ? `最新 ${entry.latestUpdateLocal}` : "",
      entry.category,
      entry.tier ? `${entry.tier} tier` : "",
      entry.region,
      entry.cityOrFocus,
    ].filter(Boolean);

    return `
      <article class="entry-card">
        <h3>${escapeHtml(entry.name)}</h3>
        <p class="entry-en">${escapeHtml(entry.nameEn)}</p>
        <div class="entry-meta">
          <span class="pill ${statusClass(entry.status)}">${escapeHtml(entry.status)}</span>
          ${meta.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}
        </div>
        <p class="entry-summary">${escapeHtml(entry.summary || entry.type || "公開來源")}</p>
        <div class="entry-links">${renderLinks(entry.links)}</div>
      </article>
    `;
  }

  function feedItemRow(item) {
    const image = item.image_url
      ? `<img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : "";
    const itemClass = item.image_url ? "feed-latest-item has-image" : "feed-latest-item no-image";
    return `
      <a class="${itemClass}" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">
        ${image}
        <span>
          <span class="feed-latest-meta">${escapeHtml(item.posted_at_local || "未標示")} · ${escapeHtml(item.source || "公開來源")}</span>
          <strong>${escapeHtml(item.title || "公開更新")}</strong>
        </span>
      </a>
    `;
  }

  function renderLatestFeeds() {
    if (!latestFeedGrid) return;
    const feeds = feedData.feeds || [];
    if (!feeds.length) {
      latestFeedGrid.innerHTML = `<div class="empty-state">目前沒有可顯示的公開 feed。</div>`;
      return;
    }

    latestFeedGrid.innerHTML = feeds
      .map((feed) => {
        const items = (feed.items || []).slice(0, 3);
        const list = items.length
          ? items.map(feedItemRow).join("")
          : `<div class="feed-latest-empty">目前沒有近期待觀測項目。</div>`;
        return `
          <article class="feed-latest-column">
            <div class="feed-latest-head">
              <div>
                <p class="section-kicker">${escapeHtml(feed.id)}</p>
                <h3>${escapeHtml(feed.title)}</h3>
              </div>
              <span class="pill">${escapeHtml(feed.count || 0)} 筆</span>
            </div>
            <div class="feed-latest-list">${list}</div>
            <div class="feed-card-actions">
              <a href="${escapeHtml(feed.page)}">看全部</a>
              <a href="${escapeHtml(feed.rss)}">RSS</a>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function filteredEntries() {
    const query = normalize(state.query);
    return data.entries.filter((entry) => {
      if (state.category !== "全部" && entry.category !== state.category) return false;
      if (state.status !== "all" && entry.status !== state.status) return false;
      if (query && !searchableText(entry).includes(query)) return false;
      return true;
    });
  }

  function renderDirectory() {
    if (!directoryList || !resultCount) return;
    const entries = filteredEntries();
    resultCount.textContent = `${entries.length} 筆公開來源`;
    if (!entries.length) {
      directoryList.innerHTML = `<div class="empty-state">沒有符合目前條件的公開來源。</div>`;
      return;
    }
    directoryList.innerHTML = entries.map(entryCard).join("");
  }

  function renderSpotlight() {
    if (!spotlightList) return;
    const spotlight = data.entries
      .filter((entry) => entry.tier === "A" || entry.category === "活動資訊")
      .slice(0, 6);
    spotlightList.innerHTML = spotlight.map(entryCard).join("");
  }

  function renderTabs() {
    if (!tabs) return;
    const categories = new Set(data.entries.map((entry) => entry.category));
    const ordered = categoryOrder.filter(
      (category) => category === "全部" || categories.has(category)
    );

    tabs.innerHTML = ordered
      .map(
        (category) => `
          <button
            type="button"
            class="category-tab"
            data-category="${escapeHtml(category)}"
            aria-pressed="${category === state.category ? "true" : "false"}"
          >
            ${escapeHtml(category)}
          </button>
        `
      )
      .join("");

    tabs.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.category = button.dataset.category;
        renderTabs();
        renderDirectory();
      });
    });
  }

  function bindSearch(source, target) {
    if (!source) return;
    source.addEventListener("input", () => {
      state.query = source.value;
      if (target) target.value = source.value;
      renderDirectory();
    });
  }

  function init() {
    setStat("totalEntries", data.stats.totalEntries || 0);
    setStat("verifiedEntries", data.stats.verifiedEntries || 0);
    setStat("categoryCount", Object.keys(data.stats.categories || {}).length);
    setStat("generatedAt", data.generatedAt || "-");
    setStat("feedGeneratedAt", feedData.generatedAt || "-");

    bindSearch(heroSearch, directorySearch);
    bindSearch(directorySearch, heroSearch);
    if (statusFilter) {
      statusFilter.addEventListener("change", () => {
        state.status = statusFilter.value;
        renderDirectory();
      });
    }

    renderTabs();
    renderLatestFeeds();
    renderSpotlight();
    renderDirectory();
  }

  init();
})();
