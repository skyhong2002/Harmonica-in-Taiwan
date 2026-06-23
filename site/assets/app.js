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
  const feedCategoryLabels = {
    events: "實體活動",
    "posts-videos": "貼文影片",
    "student-clubs": "學生社團",
    opportunities: "補助比賽",
  };

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

  function multilineHtml(value, limit = 220, maxLines = 3, skipFirst = false) {
    let text = String(value || "").trim();
    if (!text) return "";
    if (text.length > limit) text = `${text.slice(0, limit - 1)}…`;
    let lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (skipFirst) lines = lines.slice(1);
    lines = lines.slice(0, maxLines);
    return escapeHtml(lines.join("\n")).replaceAll("\n", "<br>");
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

  function sourceAvatar(item, className = "source-avatar") {
    if (item.avatar_url) {
      return `
        <span class="${className}">
          <img src="${escapeHtml(item.avatar_url)}" alt="${escapeHtml(item.source || "公開來源")} 頭貼" loading="lazy" referrerpolicy="no-referrer">
        </span>
      `;
    }
    return `<span class="${className} source-avatar-fallback" aria-hidden="true">${escapeHtml(item.source_initials || "H")}</span>`;
  }

  function feedCategoryPills(item) {
    const labels = item.category_labels || (item.categories || []).map((category) => feedCategoryLabels[category] || category);
    return labels.map((label) => `<span class="pill">${escapeHtml(label)}</span>`).join("");
  }

  function homeFeedCard(item) {
    const thumb = item.image_url
      ? `<span class="home-feed-thumb"><img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`
      : "";
    const excerpt = multilineHtml(item.text || "", 260, 4, true);
    return `
      <article class="home-feed-card">
        <div class="home-feed-source">
          ${sourceAvatar(item)}
          <div>
            <span class="feed-latest-meta">${escapeHtml(item.posted_at_local || "未標示")} · ${escapeHtml(item.platform || "public")}</span>
            <strong>${escapeHtml(item.source || "公開來源")}</strong>
          </div>
        </div>
        <a class="home-feed-body" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">
          <span class="home-feed-copy">
            <h3>${escapeHtml(item.headline || item.title || "公開更新")}</h3>
            ${excerpt ? `<span class="feed-latest-excerpt">${excerpt}</span>` : ""}
          </span>
          ${thumb}
        </a>
        <div class="home-feed-footer">
          <div class="entry-meta">${feedCategoryPills(item)}</div>
          <a class="feed-open-link" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">開啟來源</a>
        </div>
      </article>
    `;
  }

  function renderLatestFeeds() {
    if (!latestFeedGrid) return;
    const feeds = feedData.feeds || [];
    const updates = feedData.updates || [];
    if (!updates.length) {
      latestFeedGrid.innerHTML = `<div class="empty-state">目前沒有可顯示的公開 feed。</div>`;
      return;
    }

    const feedLinks = feeds
      .map((feed) => `<a href="${escapeHtml(feed.page)}">${escapeHtml(feed.shortTitle || feed.title)} ${escapeHtml(feed.count || 0)} 筆</a>`)
      .join("");
    latestFeedGrid.innerHTML = `
      <div class="feed-filter-row">
        <span class="feed-filter-label">分類 feed</span>
        <div class="feed-links">${feedLinks}<a href="/feeds/">全部 RSS</a></div>
      </div>
      ${updates.slice(0, 8).map(homeFeedCard).join("")}
    `;
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
