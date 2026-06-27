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
  const nonLocationLabels = new Set(["國際", "臺灣交流", "臺灣爵士圈"]);
  const directoryFilterNames = ["country", "region", "hashtags"];
  const feedFilterNames = ["platform", "country", "region", "source", "tag"];
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

  function directoryCountryValues() {
    return uniqueSorted(data.entries
      .map((entry) => String(entry.country || "").trim())
      .filter((country) => country && !nonLocationLabels.has(country)));
  }

  function isDirectoryCountry(value) {
    return filterHasValue(directoryCountryValues(), value);
  }

  function entryCountryValues(entry) {
    const country = String(entry.country || "").trim();
    return country && !nonLocationLabels.has(country) ? [country] : [];
  }

  function regionCandidateValues(entry) {
    const countries = entryCountryValues(entry);
    return uniqueHashtags(
      displayMetaPills([entry.region], 8)
        .filter((region) => region && !nonLocationLabels.has(region))
        .filter((region) => !isDirectoryCountry(region))
        .filter((region) => !filterHasValue(countries, region))
    );
  }

  function directoryRegionValues() {
    return uniqueSorted(data.entries.flatMap(regionCandidateValues));
  }

  function isDirectoryRegion(value) {
    return filterHasValue(directoryRegionValues(), value);
  }

  function entryRegionValues(entry) {
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
    return uniqueHashtags(entry.sourceTags || []);
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
      item.platform_label,
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
    return uniqueSorted(updates.flatMap(feedPlatformFilterValues));
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
    const query = normalize(feedState.query);
    if (!valuesMatchFilter(feedPlatformFilterValues(item), feedState.platform)) return false;
    if (!valuesMatchFilter(feedCountryFilterValues(item), feedState.country)) return false;
    if (!valuesMatchFilter(feedRegionFilterValues(item), feedState.region)) return false;
    if (!valuesMatchFilter(feedSourceFilterValues(item), feedState.source)) return false;
    if (!valuesMatchFilter(sortedPublicTags(item.matched_keywords || []), feedState.tag)) return false;
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
    const countries = countSortedValues(updates, feedCountryFilterValues);
    const knownCountries = uniqueSorted([...feedKnownCountryValues(updates), ...countries]);
    const regions = countSortedValues(updates, (item) => feedRegionFilterValues(item, knownCountries));
    const sources = countSortedValues(updates, feedSourceOptionValue);
    const tags = sortedPublicTags(updates.flatMap((item) => item.matched_keywords || []));
    return `
      <div class="feed-river-controls">
        <div class="feed-river-summary">
          <p class="feed-filter-label">河道篩選</p>
          <strong>最近 ${escapeHtml(feedWindowDays())} 天 · ${filteredUpdates.length} / ${updates.length} 筆</strong>
        </div>
        <div class="feed-filter-tools">
          <label class="search-field feed-search-field">
            <span class="sr-only">搜尋河道</span>
            <input id="feed-search-input" type="search" value="${escapeHtml(feedState.query)}" placeholder="搜尋標題、內文、國家、區域、tag 或來源">
          </label>
          <button class="feed-reset-button" type="button">重設</button>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">平台</span>
          <div class="feed-option-chips" aria-label="平台篩選，可複選">${feedOptionChips(platforms, feedState.platform, "platform", "全部平台", { allowExclude: false })}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">國家</span>
          <div class="feed-option-chips" aria-label="國家篩選，可複選">${feedOptionChips(countries, feedState.country, "country", "全部國家")}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">區域</span>
          <div class="feed-option-chips" aria-label="區域篩選，可複選">${feedOptionChips(regions, feedState.region, "region", "全部區域")}</div>
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
  }

  function applyFeedSelection(name, value) {
    toggleFeedSelection(name, value);
    syncFeedFilterUrl();
    resetFeedPagination();
    renderLatestFeeds();
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
        syncFeedFilterUrl();
        resetFeedPagination();
        renderLatestFeeds();
        latestFeedGrid.querySelector("#feed-search-input")?.focus();
      });
      feedSearch.addEventListener("input", () => {
        if (feedSearchComposing) return;
        const cursorPosition = feedSearch.selectionStart ?? feedSearch.value.length;
        feedState.query = feedSearch.value;
        syncFeedFilterUrl();
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
        applyFeedSelection("source", button.dataset.feedSource || "all");
      });
    });

    latestFeedGrid.querySelectorAll("[data-feed-platform]").forEach((button) => {
      button.addEventListener("click", () => {
        applyFeedSelection("platform", button.dataset.feedPlatform || "all");
      });
    });

    latestFeedGrid.querySelectorAll("[data-feed-country]").forEach((button) => {
      button.addEventListener("click", () => {
        applyFeedSelection("country", button.dataset.feedCountry || "all");
      });
    });

    latestFeedGrid.querySelectorAll("[data-feed-region]").forEach((button) => {
      button.addEventListener("click", () => {
        applyFeedSelection("region", button.dataset.feedRegion || "all");
      });
    });

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

    const resetButton = latestFeedGrid.querySelector(".feed-reset-button");
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

  function filteredEntries() {
    const query = normalize(state.query);
    return data.entries.filter((entry) => {
      if (state.category !== "全部" && entry.category !== state.category) return false;
      if (!valuesMatchFilter(entryCountryValues(entry), state.country)) return false;
      if (!valuesMatchFilter(entryRegionValues(entry), state.region)) return false;
      if (!valuesMatchFilter(entrySourceTagValues(entry), state.hashtags)) return false;
      if (query && !searchableText(entry).includes(query)) return false;
      return true;
    });
  }

  function directoryFiltersEmpty() {
    return directoryFilterNames.every((name) => filterEmpty(directoryFilterState(name)));
  }

  function directoryActiveFilterChips() {
    return [
      ["country", "country-tag-pill"],
      ["region", "region-tag-pill"],
      ["hashtags", "source-tag-pill"],
    ]
      .flatMap(([filterName, className]) => [
        ...filterIncludes(directoryFilterState(filterName)),
        ...filterExcludes(directoryFilterState(filterName)),
      ].map((value) => hashtagButton(value, `active-filter-chip ${className}`, filterName)))
      .join("");
  }

  function renderDirectoryResultCount(entries) {
    if (!resultCount) return;
    const activeHashtags = directoryActiveFilterChips();
    const clearButton = !directoryFiltersEmpty()
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
    const countries = directoryCountryValues();
    const regions = directoryRegionValues();
    const sourceTags = uniqueSorted(data.entries.flatMap((entry) => entry.sourceTags || []));
    const locationValues = [...countries, ...regions];
    return {
      countries,
      regions,
      sourceTags: sourceTags.filter((tag) => !filterHasValue(locationValues, tag)),
    };
  }

  function directoryHashtagFilterGroup(label, values, className, filterName) {
    if (!values.length) return "";
    return `
      <div class="directory-hashtag-filter-group">
        <span class="directory-hashtag-label">${escapeHtml(label)}</span>
        <div class="directory-hashtag-chips">
          ${values.map((tag) => hashtagButton(tag, className, filterName)).join("")}
        </div>
      </div>
    `;
  }

  function renderDirectoryHashtagFilters() {
    if (!directoryHashtagFilters) return;
    const { countries, regions, sourceTags } = directoryHashtagValues();
    directoryHashtagFilters.innerHTML = [
      directoryHashtagFilterGroup("國家", countries, "country-tag-pill", "country"),
      directoryHashtagFilterGroup("區域", regions, "region-tag-pill", "region"),
      directoryHashtagFilterGroup("Tag", sourceTags, "source-tag-pill", "hashtags"),
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
    ["country", "region", "tag", "hashtag", "notCountry", "notRegion", "notTag", "notHashtag"].forEach((name) => {
      url.searchParams.delete(name);
    });
    filterIncludes(state.country).forEach((country) => url.searchParams.append("country", country));
    filterExcludes(state.country).forEach((country) => url.searchParams.append("notCountry", country));
    filterIncludes(state.region).forEach((region) => url.searchParams.append("region", region));
    filterExcludes(state.region).forEach((region) => url.searchParams.append("notRegion", region));
    filterIncludes(state.hashtags).forEach((hashtag) => url.searchParams.append("tag", hashtag));
    filterExcludes(state.hashtags).forEach((hashtag) => url.searchParams.append("notTag", hashtag));
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

  function readDirectoryHashtagsFromUrl() {
    const params = new URLSearchParams(window.location.search);
    state.country = emptyFilterSet();
    state.region = emptyFilterSet();
    state.hashtags = emptyFilterSet();
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
    syncDirectoryHashtagUrl();
    renderDirectory();
    renderSpotlight();
  }

  function clearDirectoryHashtags() {
    state.country = emptyFilterSet();
    state.region = emptyFilterSet();
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
      const filterName = hashtagButtonElement.dataset.directoryFilter || "hashtags";
      if (!hashtag) return;
      if (!directoryList) {
        window.location.href = directoryHashtagUrl(hashtag, filterName);
        return;
      }
      toggleDirectoryHashtag(hashtag, filterName);
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
    readFeedFiltersFromUrl();
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
