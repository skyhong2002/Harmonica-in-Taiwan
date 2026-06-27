(function () {
  const data = window.HARMONICA_OBSERVE_DATA || {
    entries: [],
    stats: { categories: {}, totalEntries: 0 },
    generatedAt: "-",
  };
  const FEED_FALLBACK_WINDOW_DAYS = 30;
  let feedData = window.HARMONICA_OBSERVE_FEEDS || {
    generatedAt: "-",
    feeds: [],
    socialSources: [],
    updates: [],
    updatesWindowDays: FEED_FALLBACK_WINDOW_DAYS,
  };

  const state = {
    query: "",
    category: "全部",
    hashtags: emptyFilterSet(),
  };
  const feedState = {
    platform: emptyFilterSet(),
    country: emptyFilterSet(),
    source: emptyFilterSet(),
    tag: emptyFilterSet(),
    query: "",
    visibleCount: 12,
    autoLoadEnabled: false,
    columnCount: 0,
    sourceExpanded: false,
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
  const feedApiUrl = "/api/latest.json";
  let feedSearchComposing = false;

  const directoryList = document.querySelector("#directory-list");
  const latestFeedGrid = document.querySelector("#latest-feed-grid");
  const spotlightList = document.querySelector("#spotlight-list");
  const resultCount = document.querySelector("#result-count");
  const tabs = document.querySelector("#category-tabs");
  const directoryHashtagFilters = document.querySelector("#directory-hashtag-filters");
  const directorySearch = document.querySelector("#directory-search-input");
  const heroSearch = document.querySelector("#hero-search-input");

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
      socialSources: Array.isArray(payload.socialSources) ? payload.socialSources : [],
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

  function emptyFilterSet() {
    return { include: [], exclude: [] };
  }

  function filterIncludes(filter) {
    return Array.isArray(filter?.include) ? filter.include : [];
  }

  function filterExcludes(filter) {
    return Array.isArray(filter?.exclude) ? filter.exclude : [];
  }

  function filterEmpty(filter) {
    return !filterIncludes(filter).length && !filterExcludes(filter).length;
  }

  function filterValueKey(value) {
    return normalize(value);
  }

  function filterHasValue(values, value) {
    const key = filterValueKey(value);
    return values.some((item) => filterValueKey(item) === key);
  }

  function removeFilterValue(values, value) {
    const key = filterValueKey(value);
    return values.filter((item) => filterValueKey(item) !== key);
  }

  function addFilterValue(values, value) {
    const label = String(value || "").trim();
    if (!label || filterHasValue(values, label)) return values;
    return [...values, label];
  }

  function filterValueState(filter, value) {
    if (filterHasValue(filterIncludes(filter), value)) return "include";
    if (filterHasValue(filterExcludes(filter), value)) return "exclude";
    return "off";
  }

  function ariaPressedForFilterState(stateName) {
    if (stateName === "include") return "true";
    if (stateName === "exclude") return "mixed";
    return "false";
  }

  function cycleFilterValue(filter, value) {
    const label = String(value || "").trim().replace(/^#/, "");
    if (!label) return filter;
    const stateName = filterValueState(filter, label);
    if (stateName === "off") {
      return {
        include: addFilterValue(filterIncludes(filter), label),
        exclude: removeFilterValue(filterExcludes(filter), label),
      };
    }
    if (stateName === "include") {
      return {
        include: removeFilterValue(filterIncludes(filter), label),
        exclude: addFilterValue(filterExcludes(filter), label),
      };
    }
    return {
      include: removeFilterValue(filterIncludes(filter), label),
      exclude: removeFilterValue(filterExcludes(filter), label),
    };
  }

  function toggleFilterValue(filter, value) {
    const label = String(value || "").trim().replace(/^#/, "");
    if (!label) return filter;
    return {
      include: filterHasValue(filterIncludes(filter), label)
        ? removeFilterValue(filterIncludes(filter), label)
        : addFilterValue(filterIncludes(filter), label),
      exclude: [],
    };
  }

  function valuesMatchFilter(values, filter) {
    const normalizedValues = values.map(filterValueKey).filter(Boolean);
    const includes = filterIncludes(filter).map(filterValueKey).filter(Boolean);
    const excludes = filterExcludes(filter).map(filterValueKey).filter(Boolean);
    if (includes.length && !includes.some((key) => normalizedValues.includes(key))) return false;
    if (excludes.some((key) => normalizedValues.includes(key))) return false;
    return true;
  }

  function urlSearchParts(url) {
    const raw = String(url || "").trim();
    if (!raw) return [];
    try {
      const parsed = new URL(raw, window.location.origin);
      return [
        raw,
        parsed.hostname.replace(/^www\./, ""),
        decodeURIComponent(parsed.pathname).replace(/^\/+|\/+$/g, ""),
      ];
    } catch (error) {
      return [raw];
    }
  }

  function linkSearchParts(links) {
    return (links || []).flatMap((link) => [
      link.label,
      ...urlSearchParts(link.url),
    ]);
  }

  function monitorSourceSearchParts(sources) {
    return (sources || []).flatMap((source) => [
      source.id,
      source.name,
      source.platform,
      source.type,
      source.username,
      source.profileUrl,
      source.feedUrl,
      ...urlSearchParts(source.profileUrl),
      ...urlSearchParts(source.feedUrl),
    ]);
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
        ...(entry.sourceTags || []),
        entry.sourceSummary,
        entry.source,
        entry.latestUpdateSource,
        entry.latestUpdateUrl,
        ...linkSearchParts(entry.links),
        ...monitorSourceSearchParts(entry.monitorSources),
      ].join(" ")
    );
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

  function uniqueHashtags(values, limit = Infinity) {
    const hashtags = [];
    const seen = new Set();
    values.forEach((value) => {
      const label = String(value || "").trim().replace(/^#/, "");
      const key = filterValueKey(label);
      if (!label || seen.has(key)) return;
      seen.add(key);
      hashtags.push(label);
    });
    return Number.isFinite(limit) ? hashtags.slice(0, limit) : hashtags;
  }

  function locationHashtags(entry) {
    return displayMetaPills([entry.country, entry.region], 6);
  }

  function entryHashtags(entry) {
    return uniqueHashtags([...locationHashtags(entry), ...(entry.sourceTags || [])]);
  }

  function hashtagButton(label, className = "") {
    const stateName = filterValueState(state.hashtags, label);
    const displayLabel = `${stateName === "exclude" ? "not " : ""}#${escapeHtml(label)}`;
    return `
      <button
        type="button"
        class="pill hashtag-chip ${className}"
        data-directory-hashtag="${escapeHtml(label)}"
        data-filter-state="${stateName}"
        aria-pressed="${ariaPressedForFilterState(stateName)}"
      >${displayLabel}</button>
    `;
  }

  function entryContextHtml(entry) {
    const locations = locationHashtags(entry)
      .map((tag) => hashtagButton(tag, "location-tag-pill"))
      .join("");
    const latest = entry.latestUpdateLocal
      ? `<span class="entry-latest">最新 ${escapeHtml(entry.latestUpdateLocal)}</span>`
      : "";
    return locations || latest ? `<div class="entry-context">${locations}${latest}</div>` : "";
  }

  function entryCard(entry) {
    const sourceTags = uniqueHashtags(entry.sourceTags || [], 8);
    const summary = entry.summary || entry.sourceSummary || entry.type || "公開來源";
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
        ${entryContextHtml(entry)}
        ${
          sourceTags.length
            ? `<div class="entry-tags">${sourceTags.map((tag) => hashtagButton(tag, "source-tag-pill")).join("")}</div>`
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
    const platform = item.platform_label || item.platform || "public";
    const body = `
      ${sourceAvatar(item, avatarClass)}
      <div>
        <span class="${metaClass}">${escapeHtml(item.posted_at_local || "未標示")} · ${escapeHtml(platform)}</span>
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

  function feedTagChip(tag) {
    const stateName = filterValueState(feedState.tag, tag);
    const label = `${stateName === "exclude" ? "not " : ""}${tag}`;
    return `
      <button
        type="button"
        class="pill feed-tag-pill feed-option-chip"
        data-feed-tag="${escapeHtml(tag)}"
        aria-pressed="${ariaPressedForFilterState(stateName)}"
        data-filter-state="${stateName}"
      >
        ${escapeHtml(label)}
      </button>
    `;
  }

  function feedTagPills(item) {
    return (item.matched_keywords || [])
      .slice(0, 5)
      .map(feedTagChip)
      .join("");
  }

  function homeFeedCard(item) {
    const thumb = item.image_url
      ? `<span class="home-feed-thumb"><img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`
      : "";
    const excerpt = multilineHtml(item.text || "", 260, 4, true);
    const bodyClass = thumb ? "home-feed-body" : "home-feed-body home-feed-body-no-image";
    const tagHtml = feedTagPills(item);
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
          ${tagHtml ? `<div class="entry-meta">${tagHtml}</div>` : ""}
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

  function sourcePlatformLabel(platform) {
    const value = String(platform || "").trim();
    if (!value) return "public";
    if (value.toLowerCase() === "x") return "X";
    if (value.toLowerCase() === "rss") return "RSS";
    return value;
  }

  function feedSocialSources() {
    return Array.isArray(feedData.socialSources) ? feedData.socialSources : [];
  }

  function sourceKindLabels(source) {
    const labels = [sourcePlatformLabel(source.platform || source.type)];
    if (String(source.type || "").toLowerCase() === "rss" && !filterHasValue(labels, "RSS")) {
      labels.push("RSS");
    }
    if (String(source.type || "").toLowerCase() === "rsshub_instagram_story" && !filterHasValue(labels, "Instagram story")) {
      labels.push("Instagram story");
    }
    return labels;
  }

  function socialSourcesForItem(item) {
    const id = filterValueKey(item.source_id);
    if (!id) return [];
    return feedSocialSources().filter((source) => filterValueKey(source.id) === id);
  }

  function socialSourceLabel(source) {
    const name = source.name || source.username || source.id || "公開來源";
    return String(name).trim();
  }

  function feedSourceFilterValues(item) {
    const displaySource = feedSourceOptionValue(item);
    const sourceMatches = socialSourcesForItem(item);
    return [
      displaySource,
      item.directory_entry_name,
      item.directory_entry_id,
      item.source,
      item.source_system_name,
      item.source_id,
      item.account,
      item.source_profile_url,
      item.link,
      ...urlSearchParts(item.source_profile_url),
      ...urlSearchParts(item.link),
      ...monitorSourceSearchParts(sourceMatches),
      ...sourceMatches.map(socialSourceLabel),
    ];
  }

  function feedSourceOptionValue(item) {
    return String(
      item.directory_entry_name ||
      item.source ||
      item.source_system_name ||
      String(item.account || "").replace(/^@/, "") ||
      item.source_id ||
      ""
    ).trim();
  }

  function feedPlatformFilterValues(item) {
    return [
      sourcePlatformLabel(item.platform),
      item.platform_label,
      ...socialSourcesForItem(item).flatMap(sourceKindLabels),
    ];
  }

  function feedCountryFilterValues(item) {
    return [item.country].filter(Boolean);
  }

  function countSortedValues(updates, valueGetter) {
    const counts = new Map();
    updates.forEach((item) => {
      const values = Array.isArray(valueGetter(item)) ? valueGetter(item) : [valueGetter(item)];
      values.forEach((raw) => {
        const value = String(raw || "").trim();
        if (!value) return;
        counts.set(value, (counts.get(value) || 0) + 1);
      });
    });
    return [...counts.entries()]
      .sort((left, right) => {
        if (right[1] !== left[1]) return right[1] - left[1];
        return left[0].localeCompare(right[0], "zh-Hant");
      })
      .map(([value]) => value);
  }

  function feedPlatformOptions(updates) {
    return uniqueSorted([
      ...feedSocialSources().flatMap(sourceKindLabels),
      ...updates.flatMap(feedPlatformFilterValues),
    ]);
  }

  function feedFilterText(item) {
    return normalize(
      [
        item.headline,
        item.title,
        item.text,
        item.country,
        item.region,
        ...feedSourceFilterValues(item),
        ...(item.matched_keywords || []),
      ].join(" ")
    );
  }

  function feedMatches(item) {
    const query = normalize(feedState.query);
    if (!valuesMatchFilter(feedPlatformFilterValues(item), feedState.platform)) return false;
    if (!valuesMatchFilter(feedCountryFilterValues(item), feedState.country)) return false;
    if (!valuesMatchFilter(feedSourceFilterValues(item), feedState.source)) return false;
    if (!valuesMatchFilter(item.matched_keywords || [], feedState.tag)) return false;
    if (query && !feedFilterText(item).includes(query)) return false;
    return true;
  }

  function resetFeedPagination() {
    feedState.visibleCount = feedBatchSize;
    feedState.autoLoadEnabled = false;
    feedState.columnCount = 0;
  }

  function feedOptionChips(items, activeValues, dataName, fallbackLabel, { allowExclude = true } = {}) {
    const allPressed = filterEmpty(activeValues);
    return `
      <button
        type="button"
        class="feed-option-chip"
        data-feed-${dataName}="all"
        aria-pressed="${allPressed ? "true" : "false"}"
        data-filter-state="${allPressed ? "include" : "off"}"
      >
        ${escapeHtml(fallbackLabel)}
      </button>
      ${items
        .map((item) => {
          const stateName = allowExclude
            ? filterValueState(activeValues, item)
            : (filterHasValue(filterIncludes(activeValues), item) ? "include" : "off");
          const label = `${allowExclude && stateName === "exclude" ? "not " : ""}${item}`;
          return `
            <button
              type="button"
              class="feed-option-chip"
              data-feed-${dataName}="${escapeHtml(item)}"
              aria-pressed="${ariaPressedForFilterState(stateName)}"
              data-filter-state="${stateName}"
            >
              ${escapeHtml(label)}
            </button>
          `;
        })
        .join("")}
    `;
  }

  function feedControls(updates, filteredUpdates) {
    const platforms = feedPlatformOptions(updates);
    const countries = countSortedValues(updates, (item) => item.country);
    const sources = countSortedValues(updates, feedSourceOptionValue);
    const tags = uniqueSorted(updates.flatMap((item) => item.matched_keywords || []));
    return `
      <div class="feed-river-controls">
        <div class="feed-river-summary">
          <p class="feed-filter-label">河道篩選</p>
          <strong>最近 ${escapeHtml(feedWindowDays())} 天 · ${filteredUpdates.length} / ${updates.length} 筆</strong>
        </div>
        <div class="feed-filter-tools">
          <label class="search-field feed-search-field">
            <span class="sr-only">搜尋河道</span>
            <input id="feed-search-input" type="search" value="${escapeHtml(feedState.query)}" placeholder="搜尋標題、內文、國家、tag 或來源">
          </label>
          <button class="feed-reset-button" type="button">重設</button>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">平台</span>
          <div class="feed-option-chips" aria-label="平台篩選，可複選">${feedOptionChips(platforms, feedState.platform, "platform", "全部平台", { allowExclude: false })}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">國家</span>
          <div class="feed-option-chips" aria-label="國家篩選，可複選">${feedOptionChips(countries, feedState.country, "country", "全部國家", { allowExclude: false })}</div>
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

  function toggleFeedSelection(name, value) {
    if (!["platform", "country", "source", "tag"].includes(name)) return;
    if (value === "all") {
      feedState[name] = emptyFilterSet();
      return;
    }
    if (name === "platform" || name === "country") {
      feedState[name] = toggleFilterValue(feedState[name], value);
      return;
    }
    feedState[name] = cycleFilterValue(feedState[name], value);
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

    latestFeedGrid.querySelectorAll("[data-feed-country]").forEach((button) => {
      button.addEventListener("click", () => {
        toggleFeedSelection("country", button.dataset.feedCountry || "all");
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

    const sourceDisclosure = latestFeedGrid.querySelector("[data-feed-source-disclosure]");
    if (sourceDisclosure) {
      sourceDisclosure.addEventListener("toggle", () => {
        feedState.sourceExpanded = sourceDisclosure.open;
      });
    }

    const resetButton = latestFeedGrid.querySelector(".feed-reset-button");
    if (resetButton) {
      resetButton.addEventListener("click", () => {
        feedState.platform = emptyFilterSet();
        feedState.country = emptyFilterSet();
        feedState.source = emptyFilterSet();
        feedState.tag = emptyFilterSet();
        feedState.query = "";
        feedState.sourceExpanded = false;
        resetFeedPagination();
        renderLatestFeeds();
      });
    }

    bindFeedPagination();
  }

  function renderLatestFeeds() {
    if (!latestFeedGrid) return;
    const updates = feedData.updates || [];
    if (!updates.length) {
      latestFeedGrid.innerHTML = `<div class="empty-state">目前沒有可顯示的公開 feed。</div>`;
      return;
    }

    const filteredUpdates = updates.filter(feedMatches);
    const visibleCount = Math.min(feedState.visibleCount, filteredUpdates.length);
    const visibleUpdates = filteredUpdates.slice(0, visibleCount);
    latestFeedGrid.innerHTML = `
      ${feedControls(updates, filteredUpdates)}
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
      if (!valuesMatchFilter(entryHashtags(entry), state.hashtags)) return false;
      if (query && !searchableText(entry).includes(query)) return false;
      return true;
    });
  }

  function renderDirectoryResultCount(entries) {
    if (!resultCount) return;
    const activeHashtags = [...filterIncludes(state.hashtags), ...filterExcludes(state.hashtags)]
      .map((hashtag) => hashtagButton(hashtag, "active-filter-chip"))
      .join("");
    const clearButton = !filterEmpty(state.hashtags)
      ? `<button type="button" class="directory-clear-hashtags" data-directory-clear-hashtags>清除</button>`
      : "";
    resultCount.innerHTML = `
      <span>${entries.length} 筆公開來源</span>
      ${
        activeHashtags
          ? `<span class="directory-active-hashtags">${activeHashtags}${clearButton}</span>`
          : ""
      }
    `;
  }

  function directoryHashtagValues() {
    const locations = uniqueSorted(data.entries.flatMap(locationHashtags));
    const sourceTags = uniqueSorted(data.entries.flatMap((entry) => entry.sourceTags || []));
    return {
      locations,
      sourceTags: sourceTags.filter((tag) => !filterHasValue(locations, tag)),
    };
  }

  function directoryHashtagFilterGroup(label, values, className) {
    if (!values.length) return "";
    return `
      <div class="directory-hashtag-filter-group">
        <span class="directory-hashtag-label">${escapeHtml(label)}</span>
        <div class="directory-hashtag-chips">
          ${values.map((tag) => hashtagButton(tag, className)).join("")}
        </div>
      </div>
    `;
  }

  function renderDirectoryHashtagFilters() {
    if (!directoryHashtagFilters) return;
    const { locations, sourceTags } = directoryHashtagValues();
    directoryHashtagFilters.innerHTML = [
      directoryHashtagFilterGroup("地區", locations, "location-tag-pill"),
      directoryHashtagFilterGroup("Tag", sourceTags, "source-tag-pill"),
    ].join("");
  }

  function renderDirectory() {
    if (!directoryList || !resultCount) return;
    const entries = filteredEntries();
    renderDirectoryHashtagFilters();
    renderDirectoryResultCount(entries);
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

  function syncDirectoryHashtagUrl() {
    if (!directoryList) return;
    const url = new URL(window.location.href);
    url.searchParams.delete("hashtag");
    url.searchParams.delete("notHashtag");
    filterIncludes(state.hashtags).forEach((hashtag) => url.searchParams.append("hashtag", hashtag));
    filterExcludes(state.hashtags).forEach((hashtag) => url.searchParams.append("notHashtag", hashtag));
    window.history.replaceState({}, "", url);
  }

  function readDirectoryHashtagsFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const includes = uniqueHashtags(
      params
        .getAll("hashtag")
        .flatMap((value) => String(value || "").split(","))
    );
    state.hashtags = {
      include: includes,
      exclude: uniqueHashtags(
        params
          .getAll("notHashtag")
          .flatMap((value) => String(value || "").split(","))
      ).filter((hashtag) => !filterHasValue(includes, hashtag)),
    };
  }

  function directoryHashtagUrl(hashtag) {
    const url = new URL("/directory/", window.location.origin);
    url.searchParams.append("hashtag", hashtag);
    return url.toString();
  }

  function toggleDirectoryHashtag(hashtag) {
    state.hashtags = cycleFilterValue(state.hashtags, hashtag);
    syncDirectoryHashtagUrl();
    renderDirectory();
    renderSpotlight();
  }

  function clearDirectoryHashtags() {
    state.hashtags = emptyFilterSet();
    syncDirectoryHashtagUrl();
    renderDirectory();
    renderSpotlight();
  }

  function bindDirectoryHashtags() {
    document.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const clearButton = target.closest("[data-directory-clear-hashtags]");
      if (clearButton) {
        event.preventDefault();
        clearDirectoryHashtags();
        return;
      }

      const hashtagButtonElement = target.closest("[data-directory-hashtag]");
      if (!hashtagButtonElement) return;
      event.preventDefault();
      const hashtag = hashtagButtonElement.dataset.directoryHashtag || "";
      if (!hashtag) return;
      if (!directoryList) {
        window.location.href = directoryHashtagUrl(hashtag);
        return;
      }
      toggleDirectoryHashtag(hashtag);
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
    readDirectoryHashtagsFromUrl();
    const watchStats = data.stats.watchSources || {};
    setStat("watchSourceCount", watchStats.totalSources || data.stats.totalEntries || 0);
    setStat("rsshubSourceCount", watchStats.rsshubSources || 0);
    setStat("apifySourceCount", watchStats.apifySources || watchStats.facebookSources || 0);
    setStat("directoryEntryCount", data.stats.totalEntries || 0);
    setStat("totalEntries", data.stats.totalEntries || 0);
    setStat("categoryCount", Object.keys(data.stats.categories || {}).length);
    setStat("generatedAt", data.generatedAt || "-");
    feedData.generatedAt = formatFeedGeneratedAt(feedData.generatedAt);
    setStat("feedGeneratedAt", feedData.generatedAt || "-");

    bindSearch(heroSearch, directorySearch);
    bindSearch(directorySearch, heroSearch);
    bindDirectoryHashtags();

    renderTabs();
    renderLatestFeeds();
    fetchLatestFeedData();
    renderSpotlight();
    renderDirectory();
  }

  init();
})();
