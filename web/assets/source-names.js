import { getLocale, messages, t } from './i18n.js';
import { esc } from './utils.js';

const labels = {
  'zh-Hant': {viewOriginal:'查看原文', original:'收錄原名', originalType:'原始類型', more:'其他名稱與分類', names:'名稱', types:'分類', reference:'譯名供辨識參考，不代表官方名稱；收錄名稱與原始來源並列保留。'},
  en: {viewOriginal:'View original', original:'Recorded name', originalType:'Original type', more:'Other names and categories', names:'Names', types:'Categories', reference:'Translations are for reference, not official names. Recorded names and source links are preserved.'},
  ja: {viewOriginal:'原文を見る', original:'登録名', originalType:'元の分類', more:'別の名称と分類', names:'名称', types:'分類', reference:'訳名は識別のための参考訳で、公式名称を示すものではありません。登録名と出典を併記しています。'},
  ko: {viewOriginal:'원문 보기', original:'등록 이름', originalType:'원래 유형', more:'다른 이름과 분류', names:'이름', types:'분류', reference:'번역 이름은 식별을 위한 참고용이며 공식 명칭을 의미하지 않습니다. 등록 이름과 출처를 함께 표시합니다.'},
};
const languageLabels = {'zh-Hant':'中文',en:'EN',ja:'日本語',ko:'한국어'};
const clean = value => typeof value === 'string' ? value.trim() : '';
const normalized = value => value.normalize('NFKC').replace(/\s+/g,' ').toLocaleLowerCase();

function mergedRows(values) {
  const rows = [], seen = new Map();
  for (const [language,value] of values) {
    if (!value) continue;
    const key = normalized(value);
    const existing = seen.get(key);
    if (existing) {
      if (!existing.languages.includes(language)) existing.languages.push(language);
      if (language === 'original') existing.text = value;
    }
    else { const row = {text:value,languages:[language]}; seen.set(key,row); rows.push(row); }
  }
  return rows;
}

export function sourceNameRows(source, locale = getLocale()) {
  const names = source.names || {};
  const original = clean(names.original) || clean(source.name);
  const translated = language => clean(names[language]) || (language === 'en' ? clean(source.nameEn) : '');
  // Keep the reading language first, but never suppress or synthesize the recorded name.
  return mergedRows([[locale,translated(locale)],['original',original],...['zh-Hant','en','ja','ko'].map(language=>[language,translated(language)])]);
}
export function sourceNameText(source) {
  return [...new Set([source.name,source.nameEn,...Object.values(source.names || {})].filter(value=>typeof value==='string' && value.trim()))].join(' ');
}
export function sourceDisplayName(source, locale = getLocale()) {
  return sourceNameRows(source,locale)[0]?.text || '';
}
// Translations are prepared with the catalog; viewing a profile never invokes a translator.
export function sourceSummaryText(source, locale = getLocale()) {
  const translated = source.summaries?.[locale];
  return typeof translated === 'string' && translated.trim() ? translated : typeof source.summary === 'string' ? source.summary : '';
}
export function sourceTags(source, locale = getLocale()) {
  const originals = Array.isArray(source.tags) ? source.tags : [];
  const translated = source.tagsLocalized?.[locale];
  return originals.map((tag,index) => Array.isArray(translated) && clean(translated[index]) ? translated[index] : tag);
}
export function sourceSummaryMarkup(source) {
  const summary = sourceSummaryText(source);
  const original = typeof source.summary === 'string' ? source.summary : '';
  const translated = !!clean(summary) && summary !== original;
  const words = labels[getLocale()] || labels.en;
  const language = translated ? getLocale() : clean(source.summaryLanguage);
  const originalLanguage = clean(source.summaryLanguage);
  return `<div class="source-biography"><p class="source-summary"${language ? ` lang="${esc(language)}"` : ''}>${esc(summary || t('noBio'))}</p>${translated && original.trim() ? `<details class="source-summary-original"><summary>${esc(words.viewOriginal)}</summary><p${originalLanguage ? ` lang="${esc(originalLanguage)}"` : ''}>${esc(original)}</p></details>` : ''}</div>`;
}
export function sourceTranslationNote() {
  return `<p class="source-translation-note">${esc((labels[getLocale()] || labels.en).reference)}</p>`;
}
function rowMarkup(row, index, className, originalLabel = "original", withLabels = true) {
  const language = row.languages.find(value=>value!=='original');
  const title = row.languages.map(value=>value==='original' ? (labels[getLocale()] || labels.en)[originalLabel] : languageLabels[value] || value).join(' · ');
  return `<span class="${className} ${index===0?'is-primary':''}">${withLabels ? `<span class="source-language-label">${esc(title)}</span>` : ""}<span class="source-name-value"${language ? ` lang="${esc(language)}"` : ''}>${esc(row.text)}</span></span>`;
}
export function sourceNamesMarkup(source, {includePrimary = true} = {}) {
  const allRows = sourceNameRows(source);
  const rows = allRows.filter((row,index)=>index===0 || row.languages.includes('original'));
  return `<span class="source-names">${rows.map((row,index)=>!includePrimary && index===0?'':rowMarkup(row,index,'source-name-line','original',false)).join('')}</span>`;
}
const typeAliases = {
  演奏家:'artist',演奏者:'artist',個人:'artist',個人演奏者:'artist',口琴演奏家:'artist',團體:'ensemble',學校社團:'club',活動與比賽:'event',樂器與器材:'equipment',場館與平台:'venue',樂團:'ensemble',口琴樂團:'ensemble',重奏團:'ensemble',社團:'club',學生社團:'club',協會:'organization',組織:'organization',機構:'organization',品牌:'brand',製造商:'brand',廠商:'brand',教師:'teacher',音樂節:'festival',
};
export function sourceTypeRows(source, locale = getLocale()) {
  const original = clean(source.originalType) || clean(source.type);
  const key = typeAliases[source.type] || source.type || 'other';
  const translation = language => messages[language]?.['sourceType_'+key] || '';
  return mergedRows([[locale,translation(locale)],...['zh-Hant','en','ja','ko'].map(language=>[language,translation(language)]),['original',original]]);
}
export function sourceTypesMarkup(source) {
  const row = sourceTypeRows(source)[0];
  return `<span class="source-types">${row ? rowMarkup(row,0,'source-type-line','originalType',false) : ''}</span>`;
}

export function sourceAlternativesMarkup(source) {
  const words = labels[getLocale()] || labels.en;
  return `<details class="source-alternatives"><summary>${esc(words.more)}</summary><div class="source-alternatives-content"><h4>${esc(words.names)}</h4><div class="source-alternative-names">${sourceNameRows(source).map((row,index)=>rowMarkup(row,index,'source-name-line')).join('')}</div><h4>${esc(words.types)}</h4><div class="source-alternative-types">${sourceTypeRows(source).map((row,index)=>rowMarkup(row,index,'source-type-line','originalType')).join('')}</div>${sourceTranslationNote()}</div></details>`;
}
