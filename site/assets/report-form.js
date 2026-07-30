(() => {
  "use strict";

  const configElement = document.querySelector("#submission-form-public-config");
  const frame = document.querySelector("[data-report-form-frame]");
  const fallbackLink = document.querySelector("[data-report-form-link]");
  if (!configElement || !frame || !fallbackLink) return;

  let config;
  try {
    config = JSON.parse(configElement.textContent || "{}");
  } catch (_error) {
    return;
  }

  const limits = {
    name: 240,
    source: 1500,
    page: 1500,
    desired: 2400,
    event: 1800,
    extra: 1800,
  };
  const labels = {
    kind: "回報類型",
    name: "名稱",
    source: "主要公開來源",
    page: "觀測站頁面",
    desired: "建議處理方式",
    event: "活動資訊",
    extra: "補充來源",
  };
  const params = new URLSearchParams(window.location.search);
  const formUrl = new URL(config.responderUri);
  formUrl.searchParams.set("usp", "pp_url");

  const populated = [];
  Object.entries(config.entryIds || {}).forEach(([key, entryId]) => {
    let value = params.get(key) || "";
    if (key === "kind") value = (config.kindLabels || {})[value] || "";
    value = value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").trim();
    if (limits[key]) value = value.slice(0, limits[key]);
    if (!value) return;
    formUrl.searchParams.set(`entry.${entryId}`, value);
    populated.push(key);
  });

  fallbackLink.href = formUrl.toString();
  const embeddedUrl = new URL(formUrl);
  embeddedUrl.searchParams.set("embedded", "true");
  frame.src = embeddedUrl.toString();

  if (!populated.length) return;
  const summary = document.querySelector("[data-report-prefill-summary]");
  const title = document.querySelector("[data-report-prefill-title]");
  const fields = document.querySelector("[data-report-prefill-fields]");
  const clear = document.querySelector("[data-report-clear]");
  if (summary) summary.hidden = false;
  if (clear) clear.hidden = false;
  if (title) {
    const name = params.get("name");
    title.textContent = name ? `已帶入「${name.slice(0, 80)}」的資料` : "已帶入相關資料";
  }
  if (fields) {
    fields.textContent = `已預填：${populated.map((key) => labels[key]).filter(Boolean).join("、")}。`;
  }
})();
