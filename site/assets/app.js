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
    country: emptyFilterSet(),
    region: emptyFilterSet(),
    hashtags: emptyFilterSet(),
  };
  const feedDefaultIncludes = {
    platform: [],
    country: ["臺灣"],
    region: [],
    source: [],
    tag: ["口琴"],
  };
  const feedState = {
    platform: defaultFeedFilter("platform"),
    country: defaultFeedFilter("country"),
    region: defaultFeedFilter("region"),
    source: defaultFeedFilter("source"),
    tag: defaultFeedFilter("tag"),
    query: "",
    visibleCount: 12,
    autoLoadEnabled: false,
    columnCount: 0,
    sourceExpanded: false,
  };
  const feedBatchSize = 12;
  const directoryRenderBatchSize = 48;
  const directorySearchDelayMs = 120;
  const feedDesktopColumnQuery = "(min-width: 901px)";
  const feedDesktopColumnCount = 3;
  const feedColumnMinWidth = 340;
  const feedColumnGap = 14;
  const feedPlatformOrder = ["Facebook", "Instagram", "RSS", "Threads", "X", "YouTube"];
  const feedPlatformRank = new Map(feedPlatformOrder.map((label, index) => [filterValueKey(label), index]));
  const feedPlatformBadgeLabels = {
    facebook: "Facebook",
    instagram: "Instagram",
    rss: "RSS",
    threads: "Threads",
    x: "X",
    youtube: "YouTube",
    public: "Public",
  };
  let feedAutoLoadObserver = null;

  const nonLocationLabels = new Set(["國際", "臺灣交流", "臺灣爵士圈"]);
  const directoryFilterNames = ["country", "region", "hashtags"];
  const feedFilterNames = ["platform", "country", "region", "source", "tag"];
  const feedApiUrl = "/api/latest.json";
  let feedSearchComposing = false;

  const directoryList = document.querySelector("#directory-list");
  const latestFeedGrid = document.querySelector("#latest-feed-grid");
  const spotlightList = document.querySelector("#spotlight-list");
  const resultCount = document.querySelector("#result-count");
  const directoryHashtagFilters = document.querySelector("#directory-hashtag-filters");
  const directoryFilterPanel = document.querySelector("#directory-filter-panel") || directoryHashtagFilters;
  let directoryIndex = null;
  let directoryRecordByEntry = new WeakMap();
  let directoryRenderToken = 0;
  let directorySearchTimer = 0;
  let directorySearchComposing = false;

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

  function defaultFeedFilter(name) {
    return { include: [...(feedDefaultIncludes[name] || [])], exclude: [] };
  }

  function resetFeedFiltersToDefault() {
    Object.keys(feedDefaultIncludes).forEach((name) => {
      feedState[name] = defaultFeedFilter(name);
    });
    feedState.query = "";
    feedState.sourceExpanded = false;
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

  function normalizedTextMatches(searchText, query) {
    const normalizedQuery = normalize(query);
    return !normalizedQuery || String(searchText || "").includes(normalizedQuery);
  }

  function filterOptionChips(scope, name, values, activeValues, fallbackLabel, { allowExclude = true } = {}) {
    const allPressed = filterEmpty(activeValues);
    return `
      <button
        type="button"
        class="search-filter-option-chip feed-option-chip"
        data-search-filter-scope="${escapeHtml(scope)}"
        data-search-filter-name="${escapeHtml(name)}"
        data-search-filter-value="all"
        aria-pressed="${allPressed ? "true" : "false"}"
        data-filter-state="${allPressed ? "include" : "off"}"
      >
        ${escapeHtml(fallbackLabel)}
      </button>
      ${values
        .map((value) => {
          const stateName = allowExclude
            ? filterValueState(activeValues, value)
            : (filterHasValue(filterIncludes(activeValues), value) ? "include" : "off");
          const label = `${allowExclude && stateName === "exclude" ? "not " : ""}${value}`;
          return `
            <button
              type="button"
              class="search-filter-option-chip feed-option-chip"
              data-search-filter-scope="${escapeHtml(scope)}"
              data-search-filter-name="${escapeHtml(name)}"
              data-search-filter-value="${escapeHtml(value)}"
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

  function searchFilterGroup(scope, group) {
    if (!group.values.length) return "";
    const chips = filterOptionChips(
      scope,
      group.name,
      group.values,
      group.activeValues,
      group.fallbackLabel,
      { allowExclude: group.allowExclude !== false }
    );
    if (group.disclosure) {
      return `
        <details class="search-filter-chip-group search-filter-disclosure feed-filter-chip-group feed-filter-disclosure" ${group.open ? "open" : ""} ${group.disclosureAttribute || ""}>
          <summary>
            <span class="search-filter-chip-group-label feed-chip-group-label">${escapeHtml(group.label)}</span>
            ${group.countLabel ? `<span class="search-filter-disclosure-count feed-disclosure-count">${escapeHtml(group.countLabel)}</span>` : ""}
          </summary>
          <div class="search-filter-option-chips feed-option-chips" aria-label="${escapeHtml(group.ariaLabel)}">${chips}</div>
        </details>
      `;
    }
    return `
      <div class="search-filter-chip-group feed-filter-chip-group">
        <span class="search-filter-chip-group-label feed-chip-group-label">${escapeHtml(group.label)}</span>
        <div class="search-filter-option-chips feed-option-chips" aria-label="${escapeHtml(group.ariaLabel)}">${chips}</div>
      </div>
    `;
  }

  function searchFilterPanel({
    scope,
    className = "",
    label,
    summary,
    searchId,
    searchLabel,
    searchValue,
    searchPlaceholder,
    groups,
  }) {
    return `
      <div class="search-filter-panel feed-river-controls ${className}">
        <div class="search-filter-summary feed-river-summary">
          <p class="search-filter-label feed-filter-label">${escapeHtml(label)}</p>
          <strong>${escapeHtml(summary)}</strong>
        </div>
        <div class="search-filter-tools feed-filter-tools" role="search">
          <label class="search-field search-filter-search-field feed-search-field">
            <span class="sr-only">${escapeHtml(searchLabel)}</span>
            <input id="${escapeHtml(searchId)}" type="search" value="${escapeHtml(searchValue)}" placeholder="${escapeHtml(searchPlaceholder)}" autocomplete="off">
          </label>
          <button class="search-filter-reset-button feed-reset-button" type="button" data-search-filter-reset="${escapeHtml(scope)}">重設</button>
        </div>
        ${groups.map((group) => searchFilterGroup(scope, group)).join("")}
      </div>
    `;
  }

  function bindSearchFilterInput(root, selector, {
    setComposing,
    isComposing,
    setQuery,
    applyChange,
    delay = 0,
  }) {
    const input = root?.querySelector(selector);
    if (!input) return;
    input.addEventListener("compositionstart", () => {
      setComposing(true);
    });
    input.addEventListener("compositionend", () => {
      setComposing(false);
      setQuery(input.value);
      applyChange({ cursorPosition: input.value.length, delay: 0 });
    });
    input.addEventListener("input", () => {
      if (isComposing()) return;
      const cursorPosition = input.selectionStart ?? input.value.length;
      setQuery(input.value);
      applyChange({ cursorPosition, delay });
    });
  }

  function bindSearchFilterChips(root, scope, onSelect) {
    root?.querySelectorAll(`[data-search-filter-scope="${scope}"]`).forEach((button) => {
      button.addEventListener("click", () => {
        onSelect(
          button.dataset.searchFilterName || "",
          button.dataset.searchFilterValue || "all"
        );
      });
    });
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

  function countSortedRecords(records, getter) {
    const counts = new Map();
    records.forEach((record) => {
      getter(record).forEach((value) => {
        const label = String(value || "").trim();
        if (!label) return;
        const key = filterValueKey(label);
        if (!key) return;
        if (!counts.has(key)) counts.set(key, { label, count: 0 });
        counts.get(key).count += 1;
      });
    });
    return [...counts.values()]
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, "zh-Hant"))
      .map((item) => item.label);
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

  function directoryCountryValues() {
    if (directoryIndex) return directoryIndex.countries;
    return countSortedValues(data.entries, entryCountryValues);
  }

  function isDirectoryCountry(value) {
    const key = filterValueKey(value);
    if (directoryIndex) return directoryIndex.countryKeys.has(key);
    return filterHasValue(directoryCountryValues(), value);
  }

  function entryCountryValues(entry) {
    const country = String(entry.country || "").trim();
    return country && !nonLocationLabels.has(country) ? [country] : [];
  }

  function regionCandidateValues(entry, knownCountryKeys = null) {
    const countries = entryCountryValues(entry);
    const countryKeys = knownCountryKeys || directoryIndex?.countryKeys || new Set(directoryCountryValues().map(filterValueKey));
    return uniqueHashtags(
      displayMetaPills([entry.region], 8)
        .filter((region) => region && !nonLocationLabels.has(region))
        .filter((region) => !countryKeys.has(filterValueKey(region)))
        .filter((region) => !filterHasValue(countries, region))
    );
  }

  function directoryRegionValues() {
    if (directoryIndex) return directoryIndex.regions;
    return countSortedValues(data.entries, regionCandidateValues);
  }

  function isDirectoryRegion(value) {
    const key = filterValueKey(value);
    if (directoryIndex) return directoryIndex.regionKeys.has(key);
    return filterHasValue(directoryRegionValues(), value);
  }

  function entryRegionValues(entry) {
    const record = directoryRecordByEntry.get(entry);
    if (record) return record.regionValues;
    return regionCandidateValues(entry).filter(isDirectoryRegion);
  }

  function locationHashtags(entry) {
    return uniqueHashtags([...entryCountryValues(entry), ...entryRegionValues(entry)], 6);
  }

  function entryHashtags(entry) {
    return uniqueHashtags([
      ...entryCountryValues(entry),
      ...entryRegionValues(entry),
      ...(entry.sourceTags || []),
    ]);
  }

  function entrySourceTagValues(entry) {
    const record = directoryRecordByEntry.get(entry);
    if (record) return record.sourceTags;
    return uniqueHashtags(entry.sourceTags || []);
  }

  function buildDirectoryIndex() {
    const records = data.entries.map((entry) => {
      const countryValues = entryCountryValues(entry);
      const sourceTags = uniqueHashtags(entry.sourceTags || []);
      return {
        entry,
        countryValues,
        countryKeys: new Set(countryValues.map(filterValueKey).filter(Boolean)),
        regionValues: [],
        regionKeys: new Set(),
        sourceTags,
        sourceTagKeys: new Set(sourceTags.map(filterValueKey).filter(Boolean)),
        searchText: searchableText(entry),
        cardHtml: "",
      };
    });
    const countries = countSortedRecords(records, (record) => record.countryValues);
    const countryKeys = new Set(countries.map(filterValueKey).filter(Boolean));
    records.forEach((record) => {
      record.regionValues = regionCandidateValues(record.entry, countryKeys)
        .filter((region) => !countryKeys.has(filterValueKey(region)));
      record.regionKeys = new Set(record.regionValues.map(filterValueKey).filter(Boolean));
    });
    const regions = countSortedRecords(records, (record) => record.regionValues);
    const regionKeys = new Set(regions.map(filterValueKey).filter(Boolean));
    const sourceTags = countSortedRecords(records, (record) => record.sourceTags);
    const locationKeys = new Set([...countryKeys, ...regionKeys]);
    const index = {
      records,
      countries,
      countryKeys,
      regions,
      regionKeys,
      sourceTags: sourceTags.filter((tag) => !locationKeys.has(filterValueKey(tag))),
    };
    directoryRecordByEntry = new WeakMap(records.map((record) => [record.entry, record]));
    directoryIndex = index;
    records.forEach((record) => {
      record.cardHtml = entryCard(record.entry);
    });
    return index;
  }

  function directoryFilterState(filterName) {
    return state[filterName] || emptyFilterSet();
  }

  function hashtagButton(label, className = "", filterName = "hashtags") {
    const stateName = filterValueState(directoryFilterState(filterName), label);
    const displayLabel = `${stateName === "exclude" ? "not " : ""}#${escapeHtml(label)}`;
    return `
      <button
        type="button"
        class="pill hashtag-chip ${className}"
        data-directory-hashtag="${escapeHtml(label)}"
        data-directory-filter="${escapeHtml(filterName)}"
        data-filter-state="${stateName}"
        aria-pressed="${ariaPressedForFilterState(stateName)}"
      >${displayLabel}</button>
    `;
  }

  function entryContextHtml(entry) {
    const countries = entryCountryValues(entry)
      .map((tag) => hashtagButton(tag, "country-tag-pill", "country"))
      .join("");
    const regions = entryRegionValues(entry)
      .map((tag) => hashtagButton(tag, "region-tag-pill", "region"))
      .join("");
    const latest = entry.latestUpdateLocal
      ? `<span class="entry-latest">最新 ${escapeHtml(entry.latestUpdateLocal)}</span>`
      : "";
    const locations = countries + regions;
    return locations || latest ? `<div class="entry-context">${locations}${latest}</div>` : "";
  }

  function entryCard(entry) {
    const sourceTags = entrySourceTagValues(entry).slice(0, 8);
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
            ? `<div class="entry-tags">${sourceTags.map((tag) => hashtagButton(tag, "source-tag-pill", "hashtags")).join("")}</div>`
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

  const publicTagOrder = [
    "口琴",
    "公開更新",
    "比賽",
    "交流",
    "成發",
    "招生",
    "限時動態",
    "音樂會",
    "報名",
    "寒訓",
    "補助",
    "演出",
    "甄選",
    "影片",
    "課程",
    "學生社團",
  ];
  const publicTagSet = new Set(publicTagOrder);
  const publicTagAliases = new Map(Object.entries({
    harmonica: "口琴",
    harp: "口琴",
    成果發表: "成發",
    成果展演: "成發",
    發表會: "成發",
    學生音樂比賽: "比賽",
    全國學生音樂比賽: "比賽",
    競賽: "比賽",
    指定曲: "比賽",
    獎助: "補助",
    徵件: "補助",
    徵選: "甄選",
    甄試: "甄選",
    社博: "招生",
    迎新: "招生",
    暑訓: "課程",
    工作坊: "課程",
    講座: "課程",
    校慶: "演出",
    實體活動: "演出",
    活動: "演出",
    event: "演出",
    concert: "音樂會",
    competition: "比賽",
    grant: "補助",
    funding: "補助",
    lesson: "課程",
    course: "課程",
    workshop: "課程",
    video: "影片",
    新片: "影片",
    首播: "影片",
    上架: "影片",
    發布: "影片",
    發佈: "影片",
    直播: "影片",
    截止: "報名",
    學校社團: "學生社團",
    口琴社團: "學生社團",
    "student club": "學生社團",
    "instagram story": "限時動態",
    story: "限時動態",
  }));
  const publicTagRank = new Map(publicTagOrder.map((tag, index) => [tag, index]));
  const tagSplitPattern = /\s*(?:[,，、/／+&]|\band\b|\s+)\s*/i;

  function normalizePublicTag(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const canonical = publicTagAliases.get(raw.toLowerCase()) || publicTagAliases.get(raw) || raw;
    return publicTagSet.has(canonical) ? canonical : "";
  }

  function publicTagsFor(values) {
    const tags = [];
    (Array.isArray(values) ? values : [values]).forEach((value) => {
      String(value || "")
        .split(tagSplitPattern)
        .forEach((part) => {
          const tag = normalizePublicTag(part);
          if (tag && !filterHasValue(tags, tag)) tags.push(tag);
        });
    });
    return tags;
  }

  function sortedPublicTags(values) {
    return publicTagsFor(values).sort((a, b) => {
      const rankDiff = (publicTagRank.get(a) ?? 999) - (publicTagRank.get(b) ?? 999);
      return rankDiff || a.localeCompare(b, "zh-Hant");
    });
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

  function platformKeyFromText(value) {
    const text = String(value || "").toLowerCase();
    if (!text) return "";
    if (text.includes("facebook") || text.includes("facebook.com") || /(^|[\s/_-])fb($|[\s/_-])/.test(text)) return "facebook";
    if (text.includes("instagram") || text.includes("instagram.com") || /(^|[\s/_-])ig($|[\s/_-])/.test(text)) return "instagram";
    if (text.includes("threads") || text.includes("threads.net")) return "threads";
    if (text.includes("youtube") || text.includes("youtu.be") || /(^|[\s/_-])yt($|[\s/_-])/.test(text)) return "youtube";
    if (text.includes("twitter") || text.includes("x.com/") || /(^|[\s/_-])x($|[\s/_-])/.test(text)) return "x";
    if (text.includes("rss") || text.includes("atom") || text.includes("feed.xml")) return "rss";
    return "";
  }

  function feedPlatformBadgeKey(item) {
    const explicitPlatform = [
      item.platform,
      item.platform_label,
    ].join(" ");
    const platformKey = platformKeyFromText(explicitPlatform);
    if (platformKey) return platformKey;
    const sourceHints = [
      item.type,
      item.source_type,
      item.source_id,
      item.source_profile_url,
      item.link,
    ].join(" ");
    return platformKeyFromText(sourceHints) || "public";
  }

  function platformIconSvg(key) {
    if (key === "facebook") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14 13.5H16.5L17.5 9.5H14V7.5C14 6.47062 14 5.5 16 5.5H17.5V2.1401C17.1743 2.09685 15.943 2 14.6429 2C11.9284 2 10 3.65686 10 6.69971V9.5H7V13.5H10V22H14V13.5Z"/></svg>`;
    }
    if (key === "instagram") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.001 9C10.3436 9 9.00098 10.3431 9.00098 12C9.00098 13.6573 10.3441 15 12.001 15C13.6583 15 15.001 13.6569 15.001 12C15.001 10.3427 13.6579 9 12.001 9ZM12.001 7C14.7614 7 17.001 9.2371 17.001 12C17.001 14.7605 14.7639 17 12.001 17C9.24051 17 7.00098 14.7629 7.00098 12C7.00098 9.23953 9.23808 7 12.001 7ZM18.501 6.74915C18.501 7.43926 17.9402 7.99917 17.251 7.99917C16.5609 7.99917 16.001 7.4384 16.001 6.74915C16.001 6.0599 16.5617 5.5 17.251 5.5C17.9393 5.49913 18.501 6.0599 18.501 6.74915ZM12.001 4C9.5265 4 9.12318 4.00655 7.97227 4.0578C7.18815 4.09461 6.66253 4.20007 6.17416 4.38967C5.74016 4.55799 5.42709 4.75898 5.09352 5.09255C4.75867 5.4274 4.55804 5.73963 4.3904 6.17383C4.20036 6.66332 4.09493 7.18811 4.05878 7.97115C4.00703 9.0752 4.00098 9.46105 4.00098 12C4.00098 14.4745 4.00753 14.8778 4.05877 16.0286C4.0956 16.8124 4.2012 17.3388 4.39034 17.826C4.5591 18.2606 4.7605 18.5744 5.09246 18.9064C5.42863 19.2421 5.74179 19.4434 6.17187 19.6094C6.66619 19.8005 7.19148 19.9061 7.97212 19.9422C9.07618 19.9939 9.46203 20 12.001 20C14.4755 20 14.8788 19.9934 16.0296 19.9422C16.8117 19.9055 17.3385 19.7996 17.827 19.6106C18.2604 19.4423 18.5752 19.2402 18.9074 18.9085C19.2436 18.5718 19.4445 18.2594 19.6107 17.8283C19.8013 17.3358 19.9071 16.8098 19.9432 16.0289C19.9949 14.9248 20.001 14.5389 20.001 12C20.001 9.52552 19.9944 9.12221 19.9432 7.97137C19.9064 7.18906 19.8005 6.66149 19.6113 6.17318C19.4434 5.74038 19.2417 5.42635 18.9084 5.09255C18.573 4.75715 18.2616 4.55693 17.8271 4.38942C17.338 4.19954 16.8124 4.09396 16.0298 4.05781C14.9258 4.00605 14.5399 4 12.001 4ZM12.001 2C14.7176 2 15.0568 2.01 16.1235 2.06C17.1876 2.10917 17.9135 2.2775 18.551 2.525C19.2101 2.77917 19.7668 3.1225 20.3226 3.67833C20.8776 4.23417 21.221 4.7925 21.476 5.45C21.7226 6.08667 21.891 6.81333 21.941 7.8775C21.9885 8.94417 22.001 9.28333 22.001 12C22.001 14.7167 21.991 15.0558 21.941 16.1225C21.8918 17.1867 21.7226 17.9125 21.476 18.55C21.2218 19.2092 20.8776 19.7658 20.3226 20.3217C19.7668 20.8767 19.2076 21.22 18.551 21.475C17.9135 21.7217 17.1876 21.89 16.1235 21.94C15.0568 21.9875 14.7176 22 12.001 22C9.28431 22 8.94514 21.99 7.87848 21.94C6.81431 21.8908 6.08931 21.7217 5.45098 21.475C4.79264 21.2208 4.23514 20.8767 3.67931 20.3217C3.12348 19.7658 2.78098 19.2067 2.52598 18.55C2.27848 17.9125 2.11098 17.1867 2.06098 16.1225C2.01348 15.0558 2.00098 14.7167 2.00098 12C2.00098 9.28333 2.01098 8.94417 2.06098 7.8775C2.11014 6.8125 2.27848 6.0875 2.52598 5.45C2.78014 4.79167 3.12348 4.23417 3.67931 3.67833C4.23514 3.1225 4.79348 2.78 5.45098 2.525C6.08848 2.2775 6.81348 2.11 7.87848 2.06C8.94514 2.0125 9.28431 2 12.001 2Z"/></svg>`;
    }
    if (key === "threads") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.1835 1.41016L12.1822 1.41016C9.09012 1.43158 6.70036 2.47326 5.09369 4.51569C3.66581 6.33087 2.93472 8.86436 2.91016 12.0068V12.0082C2.93472 15.1508 3.66586 17.6696 5.09369 19.4847C6.70043 21.5271 9.10257 22.5688 12.1946 22.5902H12.1958C14.944 22.5711 16.8929 21.8504 18.4985 20.2463C20.6034 18.1434 20.5408 15.5048 19.8456 13.8832C19.3163 12.6493 18.2709 11.6618 16.8701 11.0477C16.6891 8.06345 15.0097 6.32178 12.2496 6.30415C10.6191 6.29409 9.14792 7.02378 8.24685 8.39104L9.90238 9.5267C10.4353 8.71818 11.2789 8.32815 12.2371 8.33701C13.6244 8.34586 14.5362 9.11128 14.7921 10.4541C14.02 10.3333 13.1902 10.2982 12.3076 10.3488C9.66843 10.5008 7.9399 12.061 8.05516 14.2244C8.17571 16.4862 10.367 17.7186 12.4476 17.605C14.9399 17.4684 16.4209 15.6292 16.7722 13.2836C17.3493 13.6575 17.7751 14.1344 18.0163 14.6969C18.4559 15.7222 18.4838 17.4132 17.1006 18.7952C15.8838 20.0108 14.4211 20.5407 12.1891 20.5572C9.71428 20.5388 7.85698 19.746 6.65154 18.2136C5.51973 16.7748 4.92843 14.6882 4.90627 12.0002C4.92843 9.31211 5.51973 7.22549 6.65154 5.78673C7.85698 4.25433 9.71424 3.46156 12.189 3.44303C14.6819 3.4617 16.5728 4.25837 17.8254 5.79937C18.5162 6.64934 18.949 7.66539 19.2379 8.71407L21.1776 8.19656C20.8148 6.85917 20.2414 5.58371 19.363 4.50305C17.7098 2.46918 15.2816 1.43166 12.1835 1.41016ZM12.4204 12.3782C13.3044 12.3272 14.1239 12.3834 14.8521 12.5345C14.7114 14.1116 14.0589 15.4806 12.3401 15.575C11.2282 15.6376 10.1031 15.1413 10.0484 14.114C10.0077 13.3503 10.5726 12.4847 12.4204 12.3782Z"/></svg>`;
    }
    if (key === "youtube") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.2439 4C12.778 4.00294 14.1143 4.01586 15.5341 4.07273L16.0375 4.09468C17.467 4.16236 18.8953 4.27798 19.6037 4.4755C20.5486 4.74095 21.2913 5.5155 21.5423 6.49732C21.942 8.05641 21.992 11.0994 21.9982 11.8358L21.9991 11.9884L21.9991 11.9991C21.9991 11.9991 21.9991 12.0028 21.9991 12.0099L21.9982 12.1625C21.992 12.8989 21.942 15.9419 21.5423 17.501C21.2878 18.4864 20.5451 19.261 19.6037 19.5228C18.8953 19.7203 17.467 19.8359 16.0375 19.9036L15.5341 19.9255C14.1143 19.9824 12.778 19.9953 12.2439 19.9983L12.0095 19.9991L11.9991 19.9991C11.9991 19.9991 11.9956 19.9991 11.9887 19.9991L11.7545 19.9983C10.6241 19.9921 5.89772 19.941 4.39451 19.5228C3.4496 19.2573 2.70692 18.4828 2.45587 17.501C2.0562 15.9419 2.00624 12.8989 2 12.1625V11.8358C2.00624 11.0994 2.0562 8.05641 2.45587 6.49732C2.7104 5.51186 3.45308 4.73732 4.39451 4.4755C5.89772 4.05723 10.6241 4.00622 11.7545 4H12.2439ZM9.99911 8.49914V15.4991L15.9991 11.9991L9.99911 8.49914Z"/></svg>`;
    }
    if (key === "x") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M10.4883 14.651L15.25 21H22.25L14.3917 10.5223L20.9308 3H18.2808L13.1643 8.88578L8.75 3H1.75L9.26086 13.0145L2.31915 21H4.96917L10.4883 14.651ZM16.25 19L5.75 5H7.75L18.25 19H16.25Z"/></svg>`;
    }
    if (key === "rss") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 17C5.20914 17 7 18.7909 7 21H3V17ZM3 10C9.07513 10 14 14.9249 14 21H12C12 16.0294 7.97056 12 3 12V10ZM3 3C12.9411 3 21 11.0589 21 21H19C19 12.1634 11.8366 5 3 5V3Z"/></svg>`;
    }
    return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle class="platform-icon-stroke" cx="12" cy="12" r="7"/><path class="platform-icon-stroke" d="M5 12h14M12 5c2 2 3 4.3 3 7s-1 5-3 7M12 5c-2 2-3 4.3-3 7s1 5 3 7"/></svg>`;
  }

  function feedPlatformBadge(item) {
    const key = feedPlatformBadgeKey(item);
    const label = feedPlatformBadgeLabels[key] || sourcePlatformLabel(item.platform_label || item.platform || key);
    return `
      <span class="platform-badge platform-badge-${escapeHtml(key)}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">
        ${platformIconSvg(key)}
        <span class="sr-only">${escapeHtml(label)}</span>
      </span>
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
    return sortedPublicTags(item.matched_keywords || [])
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
          <div class="home-feed-source-main">
            ${sourceIdentity(item)}
          </div>
          ${feedPlatformBadge(item)}
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
        const ratio = image.naturalWidth / image.naturalHeight;
        card.style.setProperty(
          "--feed-image-aspect",
          `${image.naturalWidth} / ${image.naturalHeight}`
        );
        card.classList.add("home-feed-card-media-ready");
        card.classList.toggle("home-feed-card-landscape", ratio >= 1.05);
        card.classList.toggle("home-feed-card-portrait", ratio <= 0.95);
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
    const lowered = value.toLowerCase();
    if (lowered === "facebook") return "Facebook";
    if (lowered === "instagram") return "Instagram";
    if (lowered === "rss") return "RSS";
    if (lowered === "threads") return "Threads";
    if (lowered === "x") return "X";
    if (lowered === "youtube") return "YouTube";
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

  function isInstagramStoryItem(item) {
    const storyFlag = item?.story === true || String(item?.story || "").toLowerCase() === "true";
    return storyFlag ||
      String(item?.media_type || "").toLowerCase() === "instagram_story" ||
      String(item?.platform_label || "").toLowerCase() === "instagram story";
  }

  function homepageFeedUpdates() {
    return (feedData.updates || []).filter((item) => !isInstagramStoryItem(item));
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
      sourcePlatformLabel(item.platform_label),
      ...socialSourcesForItem(item).flatMap(sourceKindLabels),
    ];
  }

  function feedCountryFilterValues(item) {
    const country = String(item.country || "").trim();
    return country && !nonLocationLabels.has(country) ? [country] : [];
  }

  function feedKnownCountryValues(updates = feedData.updates || []) {
    return uniqueSorted([
      ...directoryCountryValues(),
      ...updates.flatMap(feedCountryFilterValues),
    ]);
  }

  function feedRegionFilterValues(item, countryValues = feedKnownCountryValues()) {
    const countries = uniqueHashtags([...countryValues, ...feedCountryFilterValues(item)]);
    return uniqueHashtags(
      displayMetaPills([item.region], 8)
        .filter((region) => region && !nonLocationLabels.has(region))
        .filter((region) => !filterHasValue(countries, region))
    );
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
    return uniqueSorted(updates.flatMap(feedPlatformFilterValues).map(sourcePlatformLabel))
      .sort((left, right) => {
        const leftRank = feedPlatformRank.get(filterValueKey(left)) ?? feedPlatformOrder.length;
        const rightRank = feedPlatformRank.get(filterValueKey(right)) ?? feedPlatformOrder.length;
        if (leftRank !== rightRank) return leftRank - rightRank;
        return left.localeCompare(right, "zh-Hant");
      });
  }

  function feedFilterText(item) {
    return normalize(
      [
        item.headline,
        item.title,
        item.text,
        item.country,
        item.region,
        ...feedRegionFilterValues(item),
        ...feedSourceFilterValues(item),
        ...sortedPublicTags(item.matched_keywords || []),
      ].join(" ")
    );
  }

  function feedMatches(item) {
    if (!valuesMatchFilter(feedPlatformFilterValues(item), feedState.platform)) return false;
    if (!valuesMatchFilter(feedCountryFilterValues(item), feedState.country)) return false;
    if (!valuesMatchFilter(feedRegionFilterValues(item), feedState.region)) return false;
    if (!valuesMatchFilter(feedSourceFilterValues(item), feedState.source)) return false;
    if (!valuesMatchFilter(sortedPublicTags(item.matched_keywords || []), feedState.tag)) return false;
    if (!normalizedTextMatches(feedFilterText(item), feedState.query)) return false;
    return true;
  }

  function resetFeedPagination() {
    feedState.visibleCount = feedBatchSize;
    feedState.autoLoadEnabled = false;
    feedState.columnCount = 0;
  }

  function feedControls(updates, filteredUpdates) {
    const platforms = feedPlatformOptions(updates);
    const countries = countSortedValues(updates, feedCountryFilterValues);
    const knownCountries = uniqueSorted([...feedKnownCountryValues(updates), ...countries]);
    const regions = countSortedValues(updates, (item) => feedRegionFilterValues(item, knownCountries));
    const sources = countSortedValues(updates, feedSourceOptionValue);
    const tags = sortedPublicTags(updates.flatMap((item) => item.matched_keywords || []));
    const sourceDisclosureOpen = feedState.sourceExpanded || !filterEmpty(feedState.source);
    return searchFilterPanel({
      scope: "feed",
      label: "河道篩選",
      summary: `最近 ${feedWindowDays()} 天 · ${filteredUpdates.length} / ${updates.length} 筆`,
      searchId: "feed-search-input",
      searchLabel: "搜尋河道",
      searchValue: feedState.query,
      searchPlaceholder: "搜尋標題、內文、國家、區域、tag 或來源",
      groups: [
        { label: "平台", name: "platform", values: platforms, activeValues: feedState.platform, fallbackLabel: "全部平台", ariaLabel: "平台篩選，可複選", allowExclude: false },
        { label: "國家", name: "country", values: countries, activeValues: feedState.country, fallbackLabel: "全部國家", ariaLabel: "國家篩選，可複選" },
        { label: "區域", name: "region", values: regions, activeValues: feedState.region, fallbackLabel: "全部區域", ariaLabel: "區域篩選，可複選" },
        { label: "Tag", name: "tag", values: tags, activeValues: feedState.tag, fallbackLabel: "全部 tag", ariaLabel: "Tag 篩選，可複選" },
        {
          label: "來源",
          name: "source",
          values: sources,
          activeValues: feedState.source,
          fallbackLabel: "全部來源",
          ariaLabel: "來源篩選，可複選",
          disclosure: true,
          disclosureAttribute: "data-feed-source-disclosure",
          open: sourceDisclosureOpen,
          countLabel: `${sources.length} 個來源`,
        },
      ],
    });
  }

  function toggleFeedSelection(name, value) {
    if (!feedFilterNames.includes(name)) return;
    if (value === "all") {
      feedState[name] = emptyFilterSet();
      return;
    }
    if (name === "platform") {
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
    const filteredUpdates = homepageFeedUpdates().filter(feedMatches);
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

  function feedUrlParamNames() {
    return [
      "platform",
      "source",
      "notSource",
      "country",
      "notCountry",
      "region",
      "notRegion",
      "tag",
      "notTag",
      "hashtag",
      "notHashtag",
      "q",
      "query",
    ];
  }

  function appendFeedFilterUrlParams(url, filterName, includeParam, excludeParam = "") {
    filterIncludes(feedState[filterName]).forEach((value) => url.searchParams.append(includeParam, value));
    if (excludeParam) {
      filterExcludes(feedState[filterName]).forEach((value) => url.searchParams.append(excludeParam, value));
    }
  }

  function syncFeedFilterUrl() {
    if (!latestFeedGrid) return;
    const url = new URL(window.location.href);
    feedUrlParamNames().forEach((name) => url.searchParams.delete(name));
    appendFeedFilterUrlParams(url, "platform", "platform");
    appendFeedFilterUrlParams(url, "country", "country", "notCountry");
    appendFeedFilterUrlParams(url, "region", "region", "notRegion");
    appendFeedFilterUrlParams(url, "tag", "tag", "notTag");
    appendFeedFilterUrlParams(url, "source", "source", "notSource");
    if (feedState.query) url.searchParams.set("q", feedState.query);
    window.history.replaceState({}, "", url);
  }

  function addFeedFilterValue(filterName, value, mode = "include") {
    const label = String(value || "").trim();
    if (!label || !feedFilterNames.includes(filterName)) return;
    if (filterName === "platform") {
      if (mode !== "exclude") {
        feedState.platform = {
          include: addFilterValue(filterIncludes(feedState.platform), label),
          exclude: [],
        };
      }
      return;
    }
    const filter = feedState[filterName];
    if (mode === "exclude") {
      feedState[filterName] = {
        include: removeFilterValue(filterIncludes(filter), label),
        exclude: addFilterValue(filterExcludes(filter), label),
      };
      return;
    }
    feedState[filterName] = {
      include: addFilterValue(filterIncludes(filter), label),
      exclude: removeFilterValue(filterExcludes(filter), label),
    };
  }

  function routeLegacyFeedHashtag(value, mode = "include") {
    const label = String(value || "").trim();
    if (!label) return;
    if (isDirectoryCountry(label)) {
      addFeedFilterValue("country", label, mode);
    } else if (isDirectoryRegion(label)) {
      addFeedFilterValue("region", label, mode);
    } else {
      addFeedFilterValue("tag", label, mode);
    }
  }

  function readFeedFiltersFromUrl() {
    if (!latestFeedGrid) return;
    const params = new URLSearchParams(window.location.search);
    if (!feedUrlParamNames().some((name) => params.has(name))) {
      resetFeedFiltersToDefault();
      return;
    }
    feedFilterNames.forEach((name) => {
      feedState[name] = emptyFilterSet();
    });
    feedState.query = params.get("q") || params.get("query") || "";
    commaSeparatedParamValues(params, ["platform"]).forEach((value) => addFeedFilterValue("platform", value));
    commaSeparatedParamValues(params, ["country"]).forEach((value) => addFeedFilterValue("country", value));
    commaSeparatedParamValues(params, ["notCountry"]).forEach((value) => addFeedFilterValue("country", value, "exclude"));
    commaSeparatedParamValues(params, ["region"]).forEach((value) => addFeedFilterValue("region", value));
    commaSeparatedParamValues(params, ["notRegion"]).forEach((value) => addFeedFilterValue("region", value, "exclude"));
    commaSeparatedParamValues(params, ["tag"]).forEach((value) => addFeedFilterValue("tag", value));
    commaSeparatedParamValues(params, ["notTag"]).forEach((value) => addFeedFilterValue("tag", value, "exclude"));
    commaSeparatedParamValues(params, ["source"]).forEach((value) => addFeedFilterValue("source", value));
    commaSeparatedParamValues(params, ["notSource"]).forEach((value) => addFeedFilterValue("source", value, "exclude"));
    commaSeparatedParamValues(params, ["hashtag"]).forEach((value) => routeLegacyFeedHashtag(value));
    commaSeparatedParamValues(params, ["notHashtag"]).forEach((value) => routeLegacyFeedHashtag(value, "exclude"));
    feedState.sourceExpanded = !filterEmpty(feedState.source);
  }

  function applyFeedSelection(name, value) {
    toggleFeedSelection(name, value);
    syncFeedFilterUrl();
    resetFeedPagination();
    renderLatestFeeds();
  }

  function bindFeedFilters() {
    bindSearchFilterInput(latestFeedGrid, "#feed-search-input", {
      setComposing: (value) => {
        feedSearchComposing = value;
      },
      isComposing: () => feedSearchComposing,
      setQuery: (value) => {
        feedState.query = value;
      },
      applyChange: ({ cursorPosition }) => {
        syncFeedFilterUrl();
        resetFeedPagination();
        renderLatestFeeds();
        const nextSearch = latestFeedGrid.querySelector("#feed-search-input");
        if (nextSearch) {
          nextSearch.focus();
          nextSearch.setSelectionRange(cursorPosition, cursorPosition);
        }
      },
    });

    bindSearchFilterChips(latestFeedGrid, "feed", applyFeedSelection);

    latestFeedGrid.querySelectorAll("[data-feed-tag]").forEach((button) => {
      button.addEventListener("click", () => {
        applyFeedSelection("tag", button.dataset.feedTag || "all");
      });
    });

    const sourceDisclosure = latestFeedGrid.querySelector("[data-feed-source-disclosure]");
    if (sourceDisclosure) {
      sourceDisclosure.addEventListener("toggle", () => {
        feedState.sourceExpanded = sourceDisclosure.open;
      });
    }

    const resetButton = latestFeedGrid.querySelector('[data-search-filter-reset="feed"]');
    if (resetButton) {
      resetButton.addEventListener("click", () => {
        resetFeedFiltersToDefault();
        syncFeedFilterUrl();
        resetFeedPagination();
        renderLatestFeeds();
      });
    }

    bindFeedPagination();
  }

  function renderLatestFeeds() {
    if (!latestFeedGrid) return;
    const updates = homepageFeedUpdates();
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

  function keysMatchFilter(keys, filter) {
    const includes = filterIncludes(filter).map(filterValueKey).filter(Boolean);
    const excludes = filterExcludes(filter).map(filterValueKey).filter(Boolean);
    if (includes.length && !includes.some((key) => keys.has(key))) return false;
    if (excludes.some((key) => keys.has(key))) return false;
    return true;
  }

  function filteredDirectoryRecords() {
    const records = directoryIndex?.records || data.entries.map((entry) => ({ entry }));
    return records.filter((record) => {
      const entry = record.entry;
      const countryKeys = record.countryKeys || new Set(entryCountryValues(entry).map(filterValueKey).filter(Boolean));
      const regionKeys = record.regionKeys || new Set(entryRegionValues(entry).map(filterValueKey).filter(Boolean));
      const sourceTagKeys = record.sourceTagKeys || new Set(entrySourceTagValues(entry).map(filterValueKey).filter(Boolean));
      if (!keysMatchFilter(countryKeys, state.country)) return false;
      if (!keysMatchFilter(regionKeys, state.region)) return false;
      if (!keysMatchFilter(sourceTagKeys, state.hashtags)) return false;
      if (!normalizedTextMatches(record.searchText || searchableText(entry), state.query)) return false;
      return true;
    });
  }

  function filteredEntries() {
    return filteredDirectoryRecords().map((record) => record.entry);
  }

  function directoryTotalCount() {
    return directoryIndex?.records?.length || data.stats.totalEntries || data.entries.length || 0;
  }

  function renderDirectoryResultCount(records) {
    if (!resultCount) return;
    resultCount.textContent = `${records.length} / ${directoryTotalCount()} 筆公開來源`;
  }

  function directoryHashtagValues() {
    if (directoryIndex) {
      return {
        countries: directoryIndex.countries,
        regions: directoryIndex.regions,
        sourceTags: directoryIndex.sourceTags,
      };
    }
    const countries = directoryCountryValues();
    const regions = directoryRegionValues();
    const sourceTags = countSortedValues(data.entries, entrySourceTagValues);
    const locationValues = [...countries, ...regions];
    return {
      countries,
      regions,
      sourceTags: sourceTags.filter((tag) => !filterHasValue(locationValues, tag)),
    };
  }

  function renderDirectoryFilterPanel(records) {
    if (!directoryFilterPanel) return;
    const { countries, regions, sourceTags } = directoryHashtagValues();
    directoryFilterPanel.innerHTML = searchFilterPanel({
      scope: "directory",
      className: "directory-filter-panel",
      label: "索引篩選",
      summary: `${records.length} / ${directoryTotalCount()} 筆公開來源`,
      searchId: "directory-search-input",
      searchLabel: "搜尋資料索引",
      searchValue: state.query,
      searchPlaceholder: "搜尋名稱、城市、類型、關鍵字",
      groups: [
        { label: "國家", name: "country", values: countries, activeValues: state.country, fallbackLabel: "全部國家", ariaLabel: "國家篩選，可複選" },
        { label: "區域", name: "region", values: regions, activeValues: state.region, fallbackLabel: "全部區域", ariaLabel: "區域篩選，可複選" },
        { label: "Tag", name: "hashtags", values: sourceTags, activeValues: state.hashtags, fallbackLabel: "全部 tag", ariaLabel: "Tag 篩選，可複選" },
      ],
    });
    bindDirectoryFilters();
  }

  function syncDirectoryChipStates(root = document) {
    root.querySelectorAll("[data-directory-hashtag]").forEach((button) => {
      const label = button.dataset.directoryHashtag || "";
      const filterName = button.dataset.directoryFilter || "hashtags";
      const stateName = filterValueState(directoryFilterState(filterName), label);
      button.dataset.filterState = stateName;
      button.setAttribute("aria-pressed", ariaPressedForFilterState(stateName));
      button.textContent = `${stateName === "exclude" ? "not " : ""}#${label}`;
    });
  }

  function appendDirectoryCards(records, token, startIndex) {
    if (!directoryList || token !== directoryRenderToken || startIndex >= records.length) return;
    const nextRecords = records.slice(startIndex, startIndex + directoryRenderBatchSize);
    directoryList.insertAdjacentHTML(
      "beforeend",
      nextRecords.map((record) => record.cardHtml || entryCard(record.entry)).join("")
    );
    syncDirectoryChipStates(directoryList);
    const nextIndex = startIndex + nextRecords.length;
    if (nextIndex >= records.length) {
      directoryList.removeAttribute("aria-busy");
      return;
    }
    const scheduler = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 16));
    scheduler(() => appendDirectoryCards(records, token, nextIndex));
  }

  function renderDirectoryCards(records) {
    if (!directoryList) return;
    directoryRenderToken += 1;
    const token = directoryRenderToken;
    if (!records.length) {
      directoryList.removeAttribute("aria-busy");
      directoryList.innerHTML = `<div class="empty-state">沒有符合目前條件的公開來源。</div>`;
      return;
    }
    const firstRecords = records.slice(0, directoryRenderBatchSize);
    directoryList.setAttribute("aria-busy", records.length > firstRecords.length ? "true" : "false");
    directoryList.innerHTML = firstRecords.map((record) => record.cardHtml || entryCard(record.entry)).join("");
    syncDirectoryChipStates(directoryList);
    if (records.length <= firstRecords.length) {
      directoryList.removeAttribute("aria-busy");
      return;
    }
    const scheduler = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 16));
    scheduler(() => appendDirectoryCards(records, token, firstRecords.length));
  }

  function renderDirectory() {
    if (!directoryList || !resultCount) return;
    const records = filteredDirectoryRecords();
    renderDirectoryFilterPanel(records);
    renderDirectoryResultCount(records);
    renderDirectoryCards(records);
  }

  function renderSpotlight() {
    if (!spotlightList) return;
    const spotlightTags = new Set(["活動資訊", "音樂節", "團體樂團", "學生社團"]);
    const spotlight = data.entries
      .filter((entry) => (entry.sourceTags || []).some((tag) => spotlightTags.has(tag)))
      .slice(0, 6);
    spotlightList.innerHTML = spotlight.map(entryCard).join("");
  }

  function directoryUrlParamNames() {
    return [
      "country",
      "region",
      "tag",
      "hashtag",
      "notCountry",
      "notRegion",
      "notTag",
      "notHashtag",
      "q",
      "query",
    ];
  }

  function syncDirectoryFilterUrl() {
    if (!directoryList) return;
    const url = new URL(window.location.href);
    directoryUrlParamNames().forEach((name) => url.searchParams.delete(name));
    filterIncludes(state.country).forEach((country) => url.searchParams.append("country", country));
    filterExcludes(state.country).forEach((country) => url.searchParams.append("notCountry", country));
    filterIncludes(state.region).forEach((region) => url.searchParams.append("region", region));
    filterExcludes(state.region).forEach((region) => url.searchParams.append("notRegion", region));
    filterIncludes(state.hashtags).forEach((hashtag) => url.searchParams.append("tag", hashtag));
    filterExcludes(state.hashtags).forEach((hashtag) => url.searchParams.append("notTag", hashtag));
    if (state.query) url.searchParams.set("q", state.query);
    window.history.replaceState({}, "", url);
  }

  function commaSeparatedParamValues(params, names) {
    return uniqueHashtags(
      names.flatMap((name) => params.getAll(name))
        .flatMap((value) => String(value || "").split(","))
    );
  }

  function addDirectoryFilterValue(filterName, value, mode = "include") {
    const label = String(value || "").trim();
    if (!label || !directoryFilterNames.includes(filterName)) return;
    const filter = directoryFilterState(filterName);
    if (mode === "exclude") {
      state[filterName] = {
        include: removeFilterValue(filterIncludes(filter), label),
        exclude: addFilterValue(filterExcludes(filter), label),
      };
      return;
    }
    state[filterName] = {
      include: addFilterValue(filterIncludes(filter), label),
      exclude: removeFilterValue(filterExcludes(filter), label),
    };
  }

  function routeLegacyDirectoryHashtag(value, mode = "include") {
    const label = String(value || "").trim();
    if (!label) return;
    if (isDirectoryCountry(label)) {
      addDirectoryFilterValue("country", label, mode);
    } else if (isDirectoryRegion(label)) {
      addDirectoryFilterValue("region", label, mode);
    } else {
      addDirectoryFilterValue("hashtags", label, mode);
    }
  }

  function readDirectoryFiltersFromUrl() {
    const params = new URLSearchParams(window.location.search);
    state.country = emptyFilterSet();
    state.region = emptyFilterSet();
    state.hashtags = emptyFilterSet();
    state.query = params.get("q") || params.get("query") || "";
    commaSeparatedParamValues(params, ["country"]).forEach((value) => addDirectoryFilterValue("country", value));
    commaSeparatedParamValues(params, ["notCountry"]).forEach((value) => addDirectoryFilterValue("country", value, "exclude"));
    commaSeparatedParamValues(params, ["region"]).forEach((value) => addDirectoryFilterValue("region", value));
    commaSeparatedParamValues(params, ["notRegion"]).forEach((value) => addDirectoryFilterValue("region", value, "exclude"));
    commaSeparatedParamValues(params, ["tag"]).forEach((value) => addDirectoryFilterValue("hashtags", value));
    commaSeparatedParamValues(params, ["notTag"]).forEach((value) => addDirectoryFilterValue("hashtags", value, "exclude"));
    commaSeparatedParamValues(params, ["hashtag"]).forEach((value) => routeLegacyDirectoryHashtag(value));
    commaSeparatedParamValues(params, ["notHashtag"]).forEach((value) => routeLegacyDirectoryHashtag(value, "exclude"));
  }

  function directoryHashtagUrl(hashtag, filterName = "hashtags") {
    const url = new URL("/directory/", window.location.origin);
    const paramName = filterName === "country" ? "country" : filterName === "region" ? "region" : "tag";
    url.searchParams.append(paramName, hashtag);
    return url.toString();
  }

  function toggleDirectoryHashtag(hashtag, filterName = "hashtags") {
    if (!directoryFilterNames.includes(filterName)) return;
    state[filterName] = cycleFilterValue(directoryFilterState(filterName), hashtag);
    syncDirectoryFilterUrl();
    renderDirectory();
    renderSpotlight();
  }

  function resetDirectoryFilters() {
    state.country = emptyFilterSet();
    state.region = emptyFilterSet();
    state.hashtags = emptyFilterSet();
    state.query = "";
    syncDirectoryFilterUrl();
    renderDirectory();
    renderSpotlight();
  }

  function scheduleDirectoryRender(delay = 0, cursorPosition = null) {
    window.clearTimeout(directorySearchTimer);
    directorySearchTimer = window.setTimeout(() => {
      syncDirectoryFilterUrl();
      renderDirectory();
      renderSpotlight();
      if (cursorPosition !== null) {
        const nextSearch = directoryFilterPanel?.querySelector("#directory-search-input");
        if (nextSearch) {
          nextSearch.focus();
          nextSearch.setSelectionRange(cursorPosition, cursorPosition);
        }
      }
    }, delay);
  }

  function applyDirectoryPanelSelection(name, value) {
    if (!directoryFilterNames.includes(name)) return;
    if (value === "all") {
      state[name] = emptyFilterSet();
    } else {
      state[name] = cycleFilterValue(directoryFilterState(name), value);
    }
    syncDirectoryFilterUrl();
    renderDirectory();
    renderSpotlight();
  }

  function bindDirectoryFilters() {
    if (!directoryFilterPanel) return;
    bindSearchFilterInput(directoryFilterPanel, "#directory-search-input", {
      setComposing: (value) => {
        directorySearchComposing = value;
      },
      isComposing: () => directorySearchComposing,
      setQuery: (value) => {
        state.query = value;
      },
      applyChange: ({ cursorPosition, delay }) => {
        scheduleDirectoryRender(delay, cursorPosition);
      },
      delay: directorySearchDelayMs,
    });
    bindSearchFilterChips(directoryFilterPanel, "directory", applyDirectoryPanelSelection);
    const resetButton = directoryFilterPanel.querySelector('[data-search-filter-reset="directory"]');
    if (resetButton) {
      resetButton.addEventListener("click", resetDirectoryFilters);
    }
  }

  function bindDirectoryHashtags() {
    document.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const clearButton = target.closest("[data-directory-clear-hashtags]");
      if (clearButton) {
        event.preventDefault();
        resetDirectoryFilters();
        return;
      }

      const hashtagButtonElement = target.closest("[data-directory-hashtag]");
      if (!hashtagButtonElement) return;
      event.preventDefault();
      const hashtag = hashtagButtonElement.dataset.directoryHashtag || "";
      const filterName = hashtagButtonElement.dataset.directoryFilter || "hashtags";
      if (!hashtag) return;
      if (!directoryList) {
        window.location.href = directoryHashtagUrl(hashtag, filterName);
        return;
      }
      toggleDirectoryHashtag(hashtag, filterName);
    });
  }

  function init() {
    if (directoryList || spotlightList) {
      buildDirectoryIndex();
      readDirectoryFiltersFromUrl();
    }
    readFeedFiltersFromUrl();
    const watchStats = data.stats.watchSources || {};
    setStat("watchSourceCount", watchStats.totalSources || data.stats.totalEntries || 0);
    setStat("rsshubSourceCount", watchStats.rsshubSources || 0);
    setStat("apifySourceCount", watchStats.apifySources || watchStats.facebookSources || 0);
    setStat("directoryEntryCount", data.stats.totalEntries || 0);
    setStat("totalEntries", data.stats.totalEntries || 0);
    setStat("generatedAt", data.generatedAt || "-");
    feedData.generatedAt = formatFeedGeneratedAt(feedData.generatedAt);
    setStat("feedGeneratedAt", feedData.generatedAt || "-");

    bindDirectoryHashtags();

    renderLatestFeeds();
    fetchLatestFeedData();
    renderSpotlight();
    renderDirectory();
  }

  init();
})();
