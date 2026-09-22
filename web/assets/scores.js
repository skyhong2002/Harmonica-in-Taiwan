import { t, getLocale, countryName } from './i18n.js';
import { esc, link, icon, number, safeUrl, textMatch } from './utils.js';
import { pageHeading } from './views.js';
import { reportLink } from './reporting.js';

const labels = {
  'zh-Hant': {
    repertoire: '比賽指定曲', collections: '出版者與譜集', browse: '樂譜瀏覽',
    indexNote: '這是比賽指定曲與出版線索索引，不代表每筆都有可下載的完整樂譜。請由原始佐證核對曲目，再向出版者或來源洽詢取得方式。',
    collectionsNote: '公開出版公告、譜集與洽詢入口。保留來源原文；實際取得方式與授權以原始來源為準。',
    academicYear: '學年度', yearNote: '臺灣學年度以西元起始年顯示，括號保留來源的民國年。', rocYear: '民國 {year}',
    instrument: '編制', allInstruments: '所有編制', division: '組別', allDivisions: '所有組別', publisher: '出版／洽詢來源', allPublishers: '所有來源',
    sort: '排序', year_desc: '學年度：新到舊', year_asc: '學年度：舊到新', title: '曲名：A–Z', composer: '作曲者：A–Z', name: '來源名稱：A–Z',
    evidence: '原始佐證', publisherLink: '出版／洽詢入口', sourceAndEvidence: '來源與佐證',
    noResults: '沒有符合條件的曲目', noCollections: '沒有符合條件的出版來源', reset: '清除篩選', notes: '原始備註', records: '{count} 筆曲目索引', collectionRecords: '{count} 筆出版／譜集來源',
    solo: '口琴獨奏', quartet: '口琴四重奏', ensemble: '口琴合奏',
  },
  en: {
    repertoire: 'Competition repertoire', collections: 'Publishers & collections', browse: 'Browse scores',
    indexNote: 'This is an index of competition repertoire and publishing leads. Entries do not necessarily include a downloadable full score. Check the original evidence, then contact the publisher or source for availability.',
    collectionsNote: 'Public publishing announcements, collections and enquiry links. Original descriptions are preserved; availability and permissions are determined by each source.',
    academicYear: 'Academic year', yearNote: 'Taiwan academic years show the Gregorian starting year, followed by the original ROC year.', rocYear: 'ROC {year}',
    instrument: 'Instrumentation', allInstruments: 'All instrumentation', division: 'Division', allDivisions: 'All divisions', publisher: 'Publisher / enquiry source', allPublishers: 'All sources',
    sort: 'Sort', year_desc: 'Year: newest first', year_asc: 'Year: oldest first', title: 'Title: A–Z', composer: 'Composer: A–Z', name: 'Source name: A–Z',
    evidence: 'Original evidence', publisherLink: 'Publisher / enquiries', sourceAndEvidence: 'Source & evidence',
    noResults: 'No matching repertoire', noCollections: 'No matching publishing sources', reset: 'Clear filters', notes: 'Original notes', records: '{count} repertoire entries', collectionRecords: '{count} publishing / collection sources',
    solo: 'Harmonica solo', quartet: 'Harmonica quartet', ensemble: 'Harmonica ensemble',
  },
  ja: {
    repertoire: 'コンクール課題曲', collections: '出版社・楽譜集', browse: '楽譜を探す',
    indexNote: 'コンクール課題曲と出版情報の索引です。すべての項目にダウンロード可能な楽譜があるわけではありません。原資料で曲目を確認し、入手方法は出版社・情報源にお問い合わせください。',
    collectionsNote: '公開の出版案内、楽譜集、お問い合わせ先です。説明は原文を保持し、入手条件・利用許諾は各情報源に従います。',
    academicYear: '学年度', yearNote: '台湾の学年度は開始年を西暦で表示し、原資料の民国年を括弧内に併記しています。', rocYear: '民国{year}年',
    instrument: '編成', allInstruments: 'すべての編成', division: '部門', allDivisions: 'すべての部門', publisher: '出版社・問い合わせ先', allPublishers: 'すべての情報源',
    sort: '並べ替え', year_desc: '年度：新しい順', year_asc: '年度：古い順', title: '曲名：A–Z', composer: '作曲者：A–Z', name: '情報源名：A–Z',
    evidence: '原資料', publisherLink: '出版社・お問い合わせ', sourceAndEvidence: '情報源・原資料',
    noResults: '条件に合う曲目がありません', noCollections: '条件に合う出版情報がありません', reset: '絞り込みを解除', notes: '原文の備考', records: '曲目索引 {count} 件', collectionRecords: '出版社・楽譜集 {count} 件',
    solo: 'ハーモニカ独奏', quartet: 'ハーモニカ四重奏', ensemble: 'ハーモニカ合奏',
  },
  ko: {
    repertoire: '콩쿠르 지정곡', collections: '출판사·악보집', browse: '악보 찾기',
    indexNote: '콩쿠르 지정곡과 출판 정보의 목록입니다. 모든 항목에 내려받을 수 있는 전체 악보가 있는 것은 아닙니다. 원본 근거에서 곡목을 확인한 후 출판사나 출처에 입수 방법을 문의하세요.',
    collectionsNote: '공개 출판 공지, 악보집 및 문의처입니다. 설명은 원문을 유지하며 입수 조건과 이용 허가는 각 출처를 따릅니다.',
    academicYear: '학년도', yearNote: '대만 학년도는 시작하는 서기 연도를 표시하며, 출처의 민국년을 괄호 안에 함께 표시합니다.', rocYear: '민국 {year}년',
    instrument: '편성', allInstruments: '모든 편성', division: '부문', allDivisions: '모든 부문', publisher: '출판사·문의처', allPublishers: '모든 출처',
    sort: '정렬', year_desc: '학년도: 최신순', year_asc: '학년도: 오래된순', title: '곡명: A–Z', composer: '작곡가: A–Z', name: '출처 이름: A–Z',
    evidence: '원본 근거', publisherLink: '출판사·문의', sourceAndEvidence: '출처·근거',
    noResults: '조건에 맞는 곡목이 없습니다', noCollections: '조건에 맞는 출판 정보가 없습니다', reset: '필터 초기화', notes: '원문 비고', records: '곡목 색인 {count}건', collectionRecords: '출판사·악보집 출처 {count}건',
    solo: '하모니카 독주', quartet: '하모니카 4중주', ensemble: '하모니카 합주',
  },
};
export const scoreLabels = labels;
const l = (key, values = {}) => (labels[getLocale()] || labels.en)[key].replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '');
const instrumentation = value => ({ '口琴獨奏': l('solo'), '口琴四重奏': l('quartet'), '口琴合奏': l('ensemble') })[value] || value;
export function academicYearNumber(row) {
  const year = Number(row.year) || 0;
  return row.countryCode === 'TW' && year > 0 && year < 1000 ? year + 1911 : year;
}
export function academicYearLabel(row) {
  const year = academicYearNumber(row);
  return year && String(year) !== String(row.year) ? `${year} (${l('rocYear', { year: row.year })})` : String(row.year || '—');
}
const fields = { year: 'year', instrument: 'instrument', division: 'division', publisher: 'sourceName', country: 'countryCode' };
const match = (row, state, omit = '') => textMatch(row, state.q) && Object.entries(fields).every(([key, field]) => key === omit || !state[key] || String(row[field] || (key === 'country' ? 'UNKNOWN' : '')) === String(state[key]));

export function filterScores(rows, state = {}) {
  const collator = new Intl.Collator(getLocale(), { numeric: true, sensitivity: 'base' });
  const sort = ['year_desc', 'year_asc', 'title', 'composer'].includes(state.scoreSort) ? state.scoreSort : 'year_desc';
  return rows.filter(row => match(row, state)).sort((a, b) => {
    if (sort === 'year_desc' || sort === 'year_asc') {
      const difference = academicYearNumber(a) - academicYearNumber(b);
      if (difference) return difference * (sort === 'year_desc' ? -1 : 1);
    } else if (sort === 'composer') {
      if (!a.composer !== !b.composer) return a.composer ? -1 : 1;
      const comparison = collator.compare(a.composer || '', b.composer || '');
      if (comparison) return comparison;
    }
    return collator.compare(a.title || '', b.title || '') || collator.compare(a.id || '', b.id || '');
  });
}

export function scoreFacets(rows, state = {}, key) {
  const field = fields[key];
  if (!field) return [];
  const counts = new Map();
  for (const row of rows.filter(row => match(row, state, key))) {
    const value = String(row[field] || (key === 'country' ? 'UNKNOWN' : ''));
    if (value) counts.set(value, (counts.get(value) || 0) + 1);
  }
  if (state[key] && !counts.has(String(state[key]))) counts.set(String(state[key]), 0);
  const collator = new Intl.Collator(getLocale(), { numeric: true });
  const comparableYear = value => academicYearNumber(rows.find(row => String(row.year) === value) || { year: value });
  return [...counts].sort(([a], [b]) => key === 'year' ? comparableYear(b) - comparableYear(a) : collator.compare(a, b)).map(([value, count]) => ({ value, count }));
}

function tabs(active, state, catalog) {
  const query = new URLSearchParams({ lang: getLocale() });
  if (state.q) query.set('q', state.q);
  if (state.country) query.set('country', state.country);
  return `<nav class="score-tabs" aria-label="${esc(l('browse'))}">${[['repertoire', '/scores/', catalog.scores?.length || 0], ['collections', '/scores/sources/', catalog.scoreSources?.length || 0]].map(([key, href, count]) => link(href + '?' + query.toString(), `${esc(l(key))}<span>${number(count)}</span>`, `score-tab ${key === active ? 'is-active' : ''}`, key === active ? 'aria-current="page"' : '')).join('')}</nav>`;
}
function select(key, label, allLabel, rows, state) {
  const valueLabel = value => key === 'country' ? countryName(value) : key === 'instrument' ? instrumentation(value) : key === 'year' ? academicYearLabel(rows.find(row => String(row.year) === value) || { year: value }) : value;
  return `<label>${esc(label)}<select data-filter="${key}"><option value="">${esc(allLabel)}</option>${scoreFacets(rows, state, key).map(({ value, count }) => `<option value="${esc(value)}" ${String(state[key] || '') === value ? 'selected' : ''}>${esc(valueLabel(value))} (${number(count)})</option>`).join('')}</select></label>`;
}
function controls(rows, state, collections = false) {
  const relevantState = collections ? { q: state.q, country: state.country } : state;
  return `<section class="filter-bar scores-filters" aria-label="${t('filter')}"><label class="search-label"><span>${t('search')}</span><div class="search-wrap">${icon('search')}<input id="catalog-search" type="search" value="${esc(state.q || '')}" placeholder="${t('searchPlaceholder')}" autocomplete="off"></div></label>${select('country', t('country'), t('allCountries'), rows, relevantState)}${collections ? '' : select('year', l('academicYear'), t('allYears'), rows, state) + select('instrument', l('instrument'), l('allInstruments'), rows, state) + select('division', l('division'), l('allDivisions'), rows, state) + select('publisher', l('publisher'), l('allPublishers'), rows, state)}${collections ? '' : `<label>${esc(l('sort'))}<select data-filter="scoreSort">${['year_desc', 'year_asc', 'title', 'composer'].map(value => `<option value="${value}" ${(state.scoreSort || 'year_desc') === value ? 'selected' : ''}>${esc(l(value))}</option>`).join('')}</select></label>`}${['q', 'country', ...(collections ? [] : ['year', 'instrument', 'division', 'publisher'])].some(key => state[key]) ? `<button class="clear-filter" data-action="reset">${esc(l('reset'))}</button>` : ''}</section>`;
}
export function scoreEvidenceLinks(row) {
  const evidence = safeUrl(row.sourceUrl), publisher = safeUrl(row.url);
  const seen = new Set();
  const links = [];
  function add(url, label) { const safe = safeUrl(url); if (safe && !seen.has(safe)) { seen.add(safe); links.push(link(safe, esc(label), 'score-evidence-link')); } }
  if (evidence && evidence === publisher) add(evidence, l('sourceAndEvidence'));
  else { add(evidence, l('evidence')); add(publisher, l('publisherLink')); }
  for (const item of Array.isArray(row.links) ? row.links : []) add(item.url, item.label || l('evidence'));
  return `<div class="score-evidence">${links.join('')}</div>`;
}
function repertoireRow(row) {
  return `<article class="score-row repertoire-row"><div class="score-icon">${icon('music')}</div><div class="score-main"><div class="score-row-meta"><span>${esc(l('academicYear'))} ${esc(academicYearLabel(row))}</span><span>${esc(instrumentation(row.instrument || ''))}</span><span>${esc(row.division || '')}</span></div><h3>${esc(row.title)}</h3>${row.composer || row.arranger ? `<p>${row.composer ? `${t('composer')}: ${esc(row.composer)}` : ''}${row.composer && row.arranger ? ' · ' : ''}${row.arranger ? `${t('arranger')}: ${esc(row.arranger)}` : ''}</p>` : ''}${row.sourceName ? `<p class="score-publisher">${esc(l('publisher'))}: ${esc(row.sourceName)}</p>` : ''}<div class="score-row-links">${scoreEvidenceLinks(row)}${reportLink(row, row.sourceUrl || row.url)}</div>${row.notes ? `<details class="score-notes"><summary>${esc(l('notes'))}</summary><p>${esc(row.notes)}</p></details>` : ''}</div></article>`;
}
function collectionRow(row) {
  return `<article class="score-row repertoire-row"><div class="score-icon">${icon('music')}</div><div class="score-main"><div class="score-row-meta">${esc(countryName(row.countryCode))}</div><h3>${esc(row.name || row.title)}</h3>${row.title && row.title !== row.name ? `<p class="collection-title">${esc(row.title)}</p>` : ''}${row.summary ? `<p class="collection-original">${esc(row.summary)}</p>` : ''}<div class="score-row-links">${scoreEvidenceLinks(row)}${reportLink(row)}</div></div></article>`;
}
function noResults(collections) {
  return `<div class="empty-state"><h2>${esc(l(collections ? 'noCollections' : 'noResults'))}</h2><p>${t('noResultsBody')}</p><button class="button button-outline" data-action="reset">${esc(l('reset'))}</button></div>`;
}
function pagination(length, limit) {
  return length > limit ? `<div class="pagination"><p>${t('showing', { shown: number(limit), total: number(length) })}</p><button class="button button-outline" data-action="more">${t('loadMore')}${icon('plus')}</button></div>` : '';
}
export function scoresView(catalog, state = {}, limit = 24) {
  const rows = catalog.scores || [], results = filterScores(rows, state);
  return `${pageHeading('scores', 'scoresBody')}${tabs('repertoire', state, catalog)}<p class="score-index-note">${icon('info')}<span>${esc(l('indexNote'))}</span></p>${controls(rows, state)}<div class="results-bar"><p role="status">${esc(l('records', { count: number(results.length) }))}</p><span>${esc(l('yearNote'))}</span></div><div class="score-list">${results.length ? results.slice(0, limit).map(repertoireRow).join('') : noResults(false)}</div>${pagination(results.length, limit)}`;
}
export function scoreSourcesView(catalog, state = {}, limit = 24) {
  const rows = catalog.scoreSources || [];
  const collator = new Intl.Collator(getLocale(), { numeric: true, sensitivity: 'base' });
  const results = rows.filter(row => match(row, { q: state.q, country: state.country })).sort((a, b) => collator.compare(a.name || a.title || '', b.name || b.title || '') || collator.compare(a.title || '', b.title || ''));
  return `${pageHeading('scoreSources', 'scoreSourcesBody')}${tabs('collections', state, catalog)}<p class="score-index-note">${icon('info')}<span>${esc(l('collectionsNote'))}</span></p>${controls(rows, state, true)}<div class="results-bar"><p role="status">${esc(l('collectionRecords', { count: number(results.length) }))}</p><span>${t('originalLanguage')}</span></div><div class="score-list score-source-list">${results.length ? results.slice(0, limit).map(collectionRow).join('') : noResults(true)}</div>${pagination(results.length, limit)}`;
}
