(function () {
  const data = window.HARMONICA_OBSERVE_DATA || {
    entries: [],
    stats: { categories: {}, totalEntries: 0, verifiedEntries: 0 },
    generatedAt: "-",
  };
  const FEED_FALLBACK_WINDOW_DAYS = 30;
  let feedData = window.HARMONICA_OBSERVE_FEEDS || {
    generatedAt: "-",
    feeds: [],
    updates: [],
    updatesWindowDays: FEED_FALLBACK_WINDOW_DAYS,
  };

  const state = {
    query: "",
    category: "全部",
    status: "all",
  };
  const feedState = {
    category: "all",
    platform: [],
    source: [],
    tag: [],
    query: "",
    visibleCount: 12,
    autoLoadEnabled: false,
    columnCount: 0,
  };
  const feedBatchSize = 12;
  const feedDesktopColumnQuery = "(min-width: 901px)";
  const feedDesktopColumnCount = 3;
  const feedColumnMinWidth = 340;
  const feedColumnGap = 14;
  let feedAutoLoadObserver = null;

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
  const feedCategoryOrder = [
    "all",
    "events",
    "posts-videos",
    "student-clubs",
    "opportunities",
  ];
  const feedApiUrl = "/api/latest.json";
  let feedSearchComposing = false;

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

  function feedWindowDays() {
    const days = Number(feedData.updatesWindowDays || feedData.windowDays || FEED_FALLBACK_WINDOW_DAYS);
    return Number.isFinite(days) && days > 0 ? days : FEED_FALLBACK_WINDOW_DAYS;
  }

  function formatFeedGeneratedAt(value) {
    const text = String(value || "").trim();
    if (!text) return "-";
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return text;
    const parts = new Intl.DateTimeFormat("zh-TW", {
      timeZone: "Asia/Taipei",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(parsed);
    const part = Object.fromEntries(parts.map((item) => [item.type, item.value]));
    return `${part.year}-${part.month}-${part.day} ${part.hour}:${part.minute}`;
  }

  function normalizeFeedPayload(payload) {
    if (!payload || !Array.isArray(payload.updates)) return null;
    return {
      generatedAt: formatFeedGeneratedAt(payload.generatedAt || feedData.generatedAt),
      updatesWindowDays: Number(payload.updatesWindowDays || payload.windowDays || feedWindowDays()),
      updates: payload.updates,
      feeds: Array.isArray(payload.feeds) ? payload.feeds : [],
    };
  }

  async function fetchLatestFeedData() {
    if (!latestFeedGrid || !window.fetch) return;
    const url = new URL(feedApiUrl, window.location.href);
    url.searchParams.set("_", String(Date.now()));
    try {
      const response = await fetch(url, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const nextFeedData = normalizeFeedPayload(await response.json());
      if (!nextFeedData) return;
      feedData = nextFeedData;
      setStat("feedGeneratedAt", feedData.generatedAt || "-");
      renderLatestFeeds();
    } catch (error) {
      latestFeedGrid.dataset.feedFetchStatus = "fallback";
    }
  }

  function normalize(value) {
    return String(value || "").trim().toLocaleLowerCase("zh-Hant");
  }

  function searchableText(entry) {
    return normalize(
      [
        entry.name,
        entry.nameEn,
        ...(entry.aliases || []),
        entry.category,
        entry.type,
        entry.country,
        entry.region,
        entry.cityOrFocus,
        entry.summary,
        entry.keywords,
        entry.sourceStatus,
        ...(entry.sourceTags || []),
        entry.sourceSummary,
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

  function splitMetaPills(value) {
    return String(value || "")
      .split(/\s*(?:[/／；;、,，+&]|\band\b)\s*/i)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function displayMetaPills(values, limit = 12) {
    const pills = [];
    const seen = new Set();
    values.forEach((value) => {
      splitMetaPills(value).forEach((pill) => {
        if (seen.has(pill)) return;
        seen.add(pill);
        pills.push(pill);
      });
    });
    return pills.slice(0, limit);
  }

  function entryCard(entry) {
    const meta = displayMetaPills([
      entry.latestUpdateLocal ? `最新 ${entry.latestUpdateLocal}` : "",
      entry.category,
      entry.country,
      entry.region,
      entry.cityOrFocus,
    ].filter(Boolean));
    const sourceTags = (entry.sourceTags || []).slice(0, 8);
    const summary = entry.sourceSummary || entry.summary || entry.type || "公開來源";
    const aliases = (entry.aliases || []).slice(0, 4);

    return `
      <article class="entry-card">
        <div class="entry-card-head">
          ${sourceAvatar(
            {
              avatar_url: entry.avatarUrl,
              source: entry.name,
              source_initials: entry.sourceInitials,
            },
            "source-avatar entry-avatar"
          )}
          <div class="entry-title-block">
            <h3>${escapeHtml(entry.name)}</h3>
            <p class="entry-en">${escapeHtml(entry.nameEn)}</p>
            ${aliases.length ? `<p class="entry-aliases">也收錄：${aliases.map(escapeHtml).join("、")}</p>` : ""}
          </div>
        </div>
        <div class="entry-meta">
          <span class="pill ${statusClass(entry.status)}">${escapeHtml(entry.status)}</span>
          ${meta.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}
        </div>
        ${
          sourceTags.length
            ? `<div class="entry-tags">${sourceTags.map((tag) => `<span class="pill source-tag-pill">${escapeHtml(tag)}</span>`).join("")}</div>`
            : ""
        }
        <p class="entry-summary">${escapeHtml(summary)}</p>
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

  function sourceProfileUrl(item) {
    const directCandidates = [item.source_profile_url, item.profile_url, item.source_url];
    for (const candidate of directCandidates) {
      const url = String(candidate || "").trim();
      if (/^https?:\/\//i.test(url)) return url;
    }

    const rawAccount = String(item.account || "").trim();
    if (/^https?:\/\//i.test(rawAccount)) return rawAccount;
    const account = rawAccount.replace(/^@/, "").replace(/^\/+|\/+$/g, "");
    if (!account || /\s/.test(account)) return "";

    const platform = String(item.platform || "").toLowerCase();
    if (platform.includes("instagram")) return `https://www.instagram.com/${encodeURIComponent(account)}/`;
    if (platform.includes("facebook")) return `https://www.facebook.com/${account}/`;
    if (platform.includes("youtube")) {
      if (/^(channel|c|user)\//.test(account)) return `https://www.youtube.com/${account}`;
      return `https://www.youtube.com/@${encodeURIComponent(account)}`;
    }
    if (platform === "x" || platform.includes("twitter")) return `https://x.com/${encodeURIComponent(account)}`;
    if (platform.includes("threads")) return `https://www.threads.net/@${encodeURIComponent(account)}`;
    if (platform.includes("tiktok")) {
      const tiktokAccount = account.startsWith("@") ? account : `@${account}`;
      return `https://www.tiktok.com/${encodeURIComponent(tiktokAccount)}`;
    }
    return "";
  }

  function sourceIdentity(item, avatarClass = "source-avatar", metaClass = "feed-latest-meta") {
    const source = item.source || "公開來源";
    const body = `
      ${sourceAvatar(item, avatarClass)}
      <div>
        <span class="${metaClass}">${escapeHtml(item.posted_at_local || "未標示")} · ${escapeHtml(item.platform || "public")}</span>
        <strong>${escapeHtml(source)}</strong>
      </div>
    `;
    const profileUrl = sourceProfileUrl(item);
    if (!profileUrl) return body;
    return `
      <a class="source-identity-link" href="${escapeHtml(profileUrl)}" target="_blank" rel="noreferrer" aria-label="開啟 ${escapeHtml(source)} 個人首頁">
        ${body}
      </a>
    `;
  }

  function feedCategoryPills(item) {
    const labels = item.category_labels || (item.categories || []).map((category) => feedCategoryLabels[category] || category);
    return labels.map((label) => `<span class="pill">${escapeHtml(label)}</span>`).join("");
  }

  function feedTagPills(item) {
    return (item.matched_keywords || [])
      .slice(0, 5)
      .map((tag) => `<span class="pill feed-tag-pill">${escapeHtml(tag)}</span>`)
      .join("");
  }

  function homeFeedCard(item) {
    const thumb = item.image_url
      ? `<span class="home-feed-thumb"><img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`
      : "";
    const excerpt = multilineHtml(item.text || "", 260, 4, true);
    const bodyClass = thumb ? "home-feed-body" : "home-feed-body home-feed-body-no-image";
    return `
      <article class="home-feed-card">
        <div class="home-feed-source">
          ${sourceIdentity(item)}
        </div>
        <div class="${bodyClass}">
          <h3 class="home-feed-title">${escapeHtml(item.headline || item.title || "公開更新")}</h3>
          ${thumb}
          ${excerpt ? `<span class="feed-latest-excerpt">${excerpt}</span>` : ""}
        </div>
        <div class="home-feed-footer">
          <div class="entry-meta">${feedCategoryPills(item)}${feedTagPills(item)}</div>
          <a class="feed-open-link" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">開啟來源</a>
        </div>
      </article>
    `;
  }

  function updateFeedImageOrientation() {
    if (!latestFeedGrid) return;
    latestFeedGrid.querySelectorAll(".home-feed-thumb img").forEach((image) => {
      const card = image.closest(".home-feed-card");
      if (!card) return;
      const applyOrientation = () => {
        if (!image.naturalWidth || !image.naturalHeight) return;
        card.classList.toggle(
          "home-feed-card-landscape",
          image.naturalWidth > image.naturalHeight
        );
      };
      if (image.complete) {
        applyOrientation();
      } else {
        image.addEventListener("load", applyOrientation, { once: true });
      }
    });
  }

  function uniqueSorted(values) {
    return [...new Set(values.filter(Boolean))].sort((a, b) =>
      String(a).localeCompare(String(b), "zh-Hant")
    );
  }

  function feedFilterText(item) {
    return normalize(
      [
        item.headline,
        item.title,
        item.text,
        item.source,
        item.platform,
        item.account,
        ...(item.category_labels || []),
        ...(item.categories || []),
        ...(item.matched_keywords || []),
      ].join(" ")
    );
  }

  function feedMatches(item) {
    const query = normalize(feedState.query);
    if (feedState.category !== "all" && !(item.categories || []).includes(feedState.category)) return false;
    if (feedState.platform.length && !feedState.platform.includes(item.platform)) return false;
    if (feedState.source.length && !feedState.source.includes(item.source)) return false;
    if (
      feedState.tag.length &&
      !(item.matched_keywords || []).some((tag) => feedState.tag.includes(tag))
    ) return false;
    if (query && !feedFilterText(item).includes(query)) return false;
    return true;
  }

  function resetFeedPagination() {
    feedState.visibleCount = feedBatchSize;
    feedState.autoLoadEnabled = false;
    feedState.columnCount = 0;
  }

  function feedCategoryCount(categoryId, updates, feeds) {
    if (categoryId === "all") return updates.length;
    const feed = feeds.find((item) => item.id === categoryId);
    if (feed) return feed.count || 0;
    return updates.filter((item) => (item.categories || []).includes(categoryId)).length;
  }

  function feedCategoryControls(updates, feeds) {
    return feedCategoryOrder
      .filter((categoryId) => categoryId === "all" || feeds.some((feed) => feed.id === categoryId))
      .map((categoryId) => {
        const label = categoryId === "all" ? "全部" : feedCategoryLabels[categoryId] || categoryId;
        const count = feedCategoryCount(categoryId, updates, feeds);
        return `
          <button
            type="button"
            class="feed-filter-chip"
            data-feed-category="${escapeHtml(categoryId)}"
            aria-pressed="${categoryId === feedState.category ? "true" : "false"}"
          >
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(count)}</strong>
          </button>
        `;
      })
      .join("");
  }

  function feedOptionChips(items, activeValues, dataName, fallbackLabel) {
    const selectedValues = Array.isArray(activeValues) ? activeValues : [];
    const allPressed = selectedValues.length === 0;
    return `
      <button
        type="button"
        class="feed-option-chip"
        data-feed-${dataName}="all"
        aria-pressed="${allPressed ? "true" : "false"}"
      >
        ${escapeHtml(fallbackLabel)}
      </button>
      ${items
        .map(
          (item) => `
            <button
              type="button"
              class="feed-option-chip"
              data-feed-${dataName}="${escapeHtml(item)}"
              aria-pressed="${selectedValues.includes(item) ? "true" : "false"}"
            >
              ${escapeHtml(item)}
            </button>
          `
        )
        .join("")}
    `;
  }

  function feedControls(updates, feeds, filteredUpdates) {
    const sources = uniqueSorted(updates.map((item) => item.source));
    const platforms = uniqueSorted(updates.map((item) => item.platform));
    const tags = uniqueSorted(updates.flatMap((item) => item.matched_keywords || []));
    const activeCategory = feedState.category === "all" ? "全部" : feedCategoryLabels[feedState.category] || feedState.category;
    return `
      <div class="feed-river-controls">
        <div class="feed-river-summary">
          <p class="feed-filter-label">河道篩選</p>
          <strong>${escapeHtml(activeCategory)} · 最近 ${escapeHtml(feedWindowDays())} 天 · ${filteredUpdates.length} / ${updates.length} 筆</strong>
        </div>
        <div class="feed-filter-chips" aria-label="分類篩選">
          ${feedCategoryControls(updates, feeds)}
        </div>
        <div class="feed-filter-tools">
          <label class="search-field feed-search-field">
            <span class="sr-only">搜尋河道</span>
            <input id="feed-search-input" type="search" value="${escapeHtml(feedState.query)}" placeholder="搜尋標題、內文、tag 或來源">
          </label>
          <button class="feed-reset-button" type="button">重設</button>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">平台</span>
          <div class="feed-option-chips" aria-label="平台篩選，可複選">${feedOptionChips(platforms, feedState.platform, "platform", "全部平台")}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">Tag</span>
          <div class="feed-option-chips" aria-label="Tag 篩選，可複選">${feedOptionChips(tags, feedState.tag, "tag", "全部 tag")}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">來源</span>
          <div class="feed-option-chips" aria-label="來源篩選，可複選">${feedOptionChips(sources, feedState.source, "source", "全部來源")}</div>
        </div>
      </div>
    `;
  }

  function syncFeedUrl() {
    const url = new URL(window.location.href);
    if (feedState.category === "all") {
      url.searchParams.delete("feed");
    } else {
      url.searchParams.set("feed", feedState.category);
    }
    url.hash = "latest-feed";
    window.history.replaceState({}, "", url);
  }

  function toggleFeedSelection(name, value) {
    if (!["platform", "source", "tag"].includes(name)) return;
    if (value === "all") {
      feedState[name] = [];
      return;
    }
    const selectedValues = Array.isArray(feedState[name]) ? feedState[name] : [];
    feedState[name] = selectedValues.includes(value)
      ? selectedValues.filter((item) => item !== value)
      : [...selectedValues, value];
  }

  function feedLoadMore(filteredCount, visibleCount) {
    if (!filteredCount || visibleCount >= filteredCount) return "";
    if (feedState.autoLoadEnabled) {
      return `
        <div class="feed-load-more-wrap feed-auto-load-wrap" data-feed-auto-load="true" aria-live="polite">
          <span class="feed-load-more-status">已顯示 ${escapeHtml(visibleCount)} / ${escapeHtml(filteredCount)} 筆</span>
        </div>
      `;
    }
    return `
      <div class="feed-load-more-wrap">
        <span class="feed-load-more-status">已顯示 ${escapeHtml(visibleCount)} / ${escapeHtml(filteredCount)} 筆</span>
        <button class="feed-load-more-button" type="button">載入更多</button>
      </div>
    `;
  }

  function feedColumnCount(river) {
    const width = river.clientWidth || latestFeedGrid.clientWidth || window.innerWidth || feedColumnMinWidth;
    if (window.matchMedia?.(feedDesktopColumnQuery).matches) return feedDesktopColumnCount;
    return Math.max(1, Math.min(2, Math.floor((width + feedColumnGap) / (feedColumnMinWidth + feedColumnGap)) || 1));
  }

  function createFeedColumns(river, columnCount) {
    river.innerHTML = Array.from({ length: columnCount }, (_, index) => (
      `<div class="feed-river-column" data-feed-column="${index + 1}"></div>`
    )).join("");
    feedState.columnCount = columnCount;
    return Array.from(river.querySelectorAll(".feed-river-column"));
  }

  function feedCardElement(item) {
    const template = document.createElement("template");
    template.innerHTML = homeFeedCard(item).trim();
    return template.content.firstElementChild;
  }

  function shortestFeedColumn(columns) {
    return columns.reduce((shortest, column) => (
      column.getBoundingClientRect().height < shortest.getBoundingClientRect().height ? column : shortest
    ), columns[0]);
  }

  function appendFeedCards(river, updates, { reset = false } = {}) {
    const columnCount = feedColumnCount(river);
    let columns = Array.from(river.querySelectorAll(".feed-river-column"));
    if (reset || columns.length !== columnCount) {
      columns = createFeedColumns(river, columnCount);
    }
    updates.forEach((item) => {
      const card = feedCardElement(item);
      shortestFeedColumn(columns).appendChild(card);
    });
  }

  function appendNextFeedBatch() {
    const filteredUpdates = (feedData.updates || []).filter(feedMatches);
    const previousCount = Math.min(feedState.visibleCount, filteredUpdates.length);
    feedState.visibleCount += feedBatchSize;
    const visibleCount = Math.min(feedState.visibleCount, filteredUpdates.length);
    const nextUpdates = filteredUpdates.slice(previousCount, visibleCount);
    const river = latestFeedGrid.querySelector(".feed-river");
    if (!river || !nextUpdates.length) {
      renderLatestFeeds();
      return;
    }

    if (feedColumnCount(river) !== feedState.columnCount) {
      renderLatestFeeds();
      return;
    }

    appendFeedCards(river, nextUpdates);
    const existingLoadMore = latestFeedGrid.querySelector(".feed-load-more-wrap");
    const nextLoadMore = feedLoadMore(filteredUpdates.length, visibleCount);
    if (existingLoadMore) {
      existingLoadMore.outerHTML = nextLoadMore;
    } else if (nextLoadMore) {
      latestFeedGrid.insertAdjacentHTML("beforeend", nextLoadMore);
    }
    updateFeedImageOrientation();
    bindFeedPagination();
  }

  function bindFeedAutoLoad() {
    if (feedAutoLoadObserver) {
      feedAutoLoadObserver.disconnect();
      feedAutoLoadObserver = null;
    }
    if (!feedState.autoLoadEnabled || !("IntersectionObserver" in window)) return;

    const marker = latestFeedGrid.querySelector("[data-feed-auto-load]");
    if (!marker) return;
    feedAutoLoadObserver = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        if (feedAutoLoadObserver) {
          feedAutoLoadObserver.disconnect();
          feedAutoLoadObserver = null;
        }
        appendNextFeedBatch();
      },
      { rootMargin: "360px 0px" }
    );
    feedAutoLoadObserver.observe(marker);
  }

  function bindFeedPagination() {
    const loadMoreButton = latestFeedGrid.querySelector(".feed-load-more-button");
    if (loadMoreButton) {
      loadMoreButton.addEventListener("click", () => {
        feedState.autoLoadEnabled = true;
        appendNextFeedBatch();
      });
    }
    bindFeedAutoLoad();
  }

  function bindFeedFilters() {
    latestFeedGrid.querySelectorAll("[data-feed-category]").forEach((button) => {
      button.addEventListener("click", () => {
        feedState.category = button.dataset.feedCategory || "all";
        resetFeedPagination();
        syncFeedUrl();
        renderLatestFeeds();
      });
    });

    const feedSearch = latestFeedGrid.querySelector("#feed-search-input");
    if (feedSearch) {
      feedSearch.addEventListener("compositionstart", () => {
        feedSearchComposing = true;
      });
      feedSearch.addEventListener("compositionend", () => {
        feedSearchComposing = false;
        feedState.query = feedSearch.value;
        resetFeedPagination();
        renderLatestFeeds();
        latestFeedGrid.querySelector("#feed-search-input")?.focus();
      });
      feedSearch.addEventListener("input", () => {
        if (feedSearchComposing) return;
        const cursorPosition = feedSearch.selectionStart ?? feedSearch.value.length;
        feedState.query = feedSearch.value;
        resetFeedPagination();
        renderLatestFeeds();
        const nextSearch = latestFeedGrid.querySelector("#feed-search-input");
        if (nextSearch) {
          nextSearch.focus();
          nextSearch.setSelectionRange(cursorPosition, cursorPosition);
        }
      });
    }

    latestFeedGrid.querySelectorAll("[data-feed-source]").forEach((button) => {
      button.addEventListener("click", () => {
        toggleFeedSelection("source", button.dataset.feedSource || "all");
        resetFeedPagination();
        renderLatestFeeds();
      });
    });

    latestFeedGrid.querySelectorAll("[data-feed-platform]").forEach((button) => {
      button.addEventListener("click", () => {
        toggleFeedSelection("platform", button.dataset.feedPlatform || "all");
        resetFeedPagination();
        renderLatestFeeds();
      });
    });

    latestFeedGrid.querySelectorAll("[data-feed-tag]").forEach((button) => {
      button.addEventListener("click", () => {
        toggleFeedSelection("tag", button.dataset.feedTag || "all");
        resetFeedPagination();
        renderLatestFeeds();
      });
    });

    const resetButton = latestFeedGrid.querySelector(".feed-reset-button");
    if (resetButton) {
      resetButton.addEventListener("click", () => {
        feedState.category = "all";
        feedState.platform = [];
        feedState.source = [];
        feedState.tag = [];
        feedState.query = "";
        resetFeedPagination();
        syncFeedUrl();
        renderLatestFeeds();
      });
    }

    bindFeedPagination();
  }

  function bindFeedNav() {
    document.querySelectorAll(".nav-feed-link[data-feed-category]").forEach((link) => {
      link.addEventListener("click", (event) => {
        if (!latestFeedGrid) return;
        event.preventDefault();
        feedState.category = link.dataset.feedCategory || "all";
        resetFeedPagination();
        syncFeedUrl();
        renderLatestFeeds();
        document.querySelector("#latest-feed")?.scrollIntoView({ block: "start" });
        link.closest("details")?.removeAttribute("open");
      });
    });
  }

  function renderLatestFeeds() {
    if (!latestFeedGrid) return;
    const feeds = feedData.feeds || [];
    const updates = feedData.updates || [];
    if (!updates.length) {
      latestFeedGrid.innerHTML = `<div class="empty-state">目前沒有可顯示的公開 feed。</div>`;
      return;
    }

    const filteredUpdates = updates.filter(feedMatches);
    const visibleCount = Math.min(feedState.visibleCount, filteredUpdates.length);
    const visibleUpdates = filteredUpdates.slice(0, visibleCount);
    latestFeedGrid.innerHTML = `
      ${feedControls(updates, feeds, filteredUpdates)}
      <div class="feed-river" aria-live="polite"></div>
      ${feedLoadMore(filteredUpdates.length, visibleCount)}
    `;
    const river = latestFeedGrid.querySelector(".feed-river");
    if (river) {
      if (visibleUpdates.length) {
        appendFeedCards(river, visibleUpdates, { reset: true });
      } else {
        river.innerHTML = `<div class="empty-state">沒有符合目前篩選的公開更新。</div>`;
        feedState.columnCount = 0;
      }
    }
    bindFeedFilters();
    updateFeedImageOrientation();
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
      .filter((entry) => entry.category === "活動資訊" || (entry.sourceTags || []).some((tag) => ["音樂節", "團體樂團", "學生社團"].includes(tag)))
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
    const initialFeed = new URLSearchParams(window.location.search).get("feed");
    if (initialFeed && feedCategoryOrder.includes(initialFeed)) {
      feedState.category = initialFeed;
    }

    const watchStats = data.stats.watchSources || {};
    setStat("watchSourceCount", watchStats.totalSources || data.stats.totalEntries || 0);
    setStat("rsshubSourceCount", watchStats.rsshubSources || 0);
    setStat("apifySourceCount", watchStats.apifySources || watchStats.facebookSources || 0);
    setStat("directoryEntryCount", data.stats.totalEntries || 0);
    setStat("totalEntries", data.stats.totalEntries || 0);
    setStat("verifiedEntries", data.stats.verifiedEntries || 0);
    setStat("categoryCount", Object.keys(data.stats.categories || {}).length);
    setStat("generatedAt", data.generatedAt || "-");
    feedData.generatedAt = formatFeedGeneratedAt(feedData.generatedAt);
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
    bindFeedNav();
    fetchLatestFeedData();
    renderSpotlight();
    renderDirectory();
  }

  init();
})();
