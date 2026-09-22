import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost/' });
globalThis.document = dom.window.document;
globalThis.localStorage = dom.window.localStorage;
const { setLocale } = await import('../assets/i18n.js');
const { filterScores, scoreFacets, scoresView, scoreSourcesView, scoreEvidenceLinks, scoreLabels } = await import('../assets/scores.js');
const rows = [
  { id: 'a', title: 'Alpha <b>原曲</b>', composer: 'Bach', arranger: '林', countryCode: 'TW', year: '115', instrument: '口琴獨奏', division: '國中', sourceName: 'Publisher One', sourceUrl: 'https://example.org/official.pdf', url: 'https://example.org/publisher', links: [{url:'https://example.org/official.pdf',label:'Evidence duplicate'}], notes:'原始 <i>完整演奏</i>' },
  { id: 'b', title: 'Beta', composer: 'Adams', countryCode: 'TW', year: '99', instrument: '口琴四重奏', division: '國中', sourceName: 'Publisher Two', sourceUrl: 'https://example.org/official.pdf', url: 'https://example.org/official.pdf' },
  { id: 'c', title: 'Gamma', composer: '', countryCode: 'TW', year: '114', instrument: '口琴獨奏', division: '高中', sourceName: 'Publisher One' },
  { id: 'd', title: 'Delta', composer: 'Adams', countryCode: 'JP', year: '2025', instrument: '口琴四重奏', division: 'Open', sourceName: 'Publisher Two' },
];
const catalog = { scores: rows, scoreSources: [{name:'Publisher <b>One</b>',title:'Original collection title',summary:'原始說明 <script>unsafe</script>',countryCode:'UNKNOWN',url:'https://example.org/home',sourceUrl:'https://example.org/announcement',links:[]} ] };

test('score filters combine real facets without mapping language to country; numeric years sort correctly',()=>{
 for(const locale of ['en','zh-Hant','ja','ko']){
  setLocale(locale);
  assert.deepEqual(filterScores(rows,{country:'TW',instrument:'口琴獨奏',publisher:'Publisher One',division:'國中'}).map(r=>r.id),['a']);
  assert.deepEqual(filterScores(rows,{country:'TW',scoreSort:'year_asc'}).map(r=>r.year),['99','114','115']);
  assert.deepEqual(filterScores(rows,{country:'TW',scoreSort:'composer'}).map(r=>r.id),['b','a','c']);
  assert.equal(filterScores(rows,{q:'Ｐｕｂｌｉｓｈｅｒ One'}).length,2);
  assert.equal(filterScores(rows,{country:'JP'}).length,1);
 }
 assert.deepEqual(rows.map(r=>r.id),['a','b','c','d']);
});
test('contextual facet counts exclude only their own active filter and retain selected zero-result values',()=>{
 setLocale('en');
 assert.deepEqual(scoreFacets(rows,{country:'TW',year:'115',instrument:'口琴獨奏'},'year'),[{value:'115',count:1},{value:'114',count:1}]);
 assert.deepEqual(scoreFacets(rows,{country:'US'},'country'),[{value:'JP',count:1},{value:'TW',count:3},{value:'US',count:0}]);
 assert.deepEqual(scoreFacets(rows,{country:'TW',division:'國中'},'instrument'),[{value:'口琴四重奏',count:1},{value:'口琴獨奏',count:1}]);
});
test('repertoire links retain evidence and publisher separately, deduplicate URLs, and reject unsafe URLs',()=>{
 setLocale('en');
 document.body.innerHTML=scoreEvidenceLinks({...rows[0],links:[...rows[0].links,{url:'javascript:alert(1)',label:'unsafe'},{url:'https://example.org/extra',label:'<original>'}]});
 const links=[...document.querySelectorAll('a')];
 assert.deepEqual(links.map(a=>a.href),['https://example.org/official.pdf','https://example.org/publisher','https://example.org/extra']);
 assert.match(links[0].textContent,/Original evidence/);
 assert.match(links[1].textContent,/Publisher/);
 assert.match(links[2].textContent,/<original>/);
 assert.equal(document.querySelector('original'),null);
 document.body.innerHTML=scoreEvidenceLinks(rows[1]);
 assert.equal(document.querySelectorAll('a').length,1);
});
test('four-language score views keep original text and collection titles, preserve global tab facets, and paginate honestly',()=>{
 const keys=Object.keys(scoreLabels.en).sort();
 for(const locale of ['en','zh-Hant','ja','ko']){
  assert.deepEqual(Object.keys(scoreLabels[locale]).sort(),keys);
  setLocale(locale);
  document.body.innerHTML=scoresView(catalog,{country:'TW',q:'Publisher',year:'115'},1);
  assert.equal(document.querySelectorAll('.repertoire-row').length,1);
  const report=new URL(document.querySelector('.context-report-link').href);
  assert.equal(report.pathname,'/submit/');
  assert.equal(report.searchParams.get('reportUrl'),rows[0].sourceUrl);
  assert.equal(report.searchParams.get('reportCountry'),'TW');
  assert.equal(report.searchParams.get('lang'),locale);
  assert.ok(document.querySelector('.score-main h3').textContent.includes('<b>原曲</b>'));
  assert.equal(document.querySelector('.score-main b'),null);
  assert.ok(document.querySelector('.score-notes').textContent.includes('<i>完整演奏</i>'));
  const tab=new URL(document.querySelectorAll('.score-tab')[1].href);
  assert.equal(tab.searchParams.get('country'),'TW');
  assert.equal(tab.searchParams.get('lang'),locale);
  assert.equal(tab.searchParams.get('q'),'Publisher');
  assert.equal(tab.searchParams.has('year'),false);
  assert.equal(document.querySelector('[data-action="more"]'),null);
  document.body.innerHTML=scoresView(catalog,{country:'TW'},1);
  assert.ok(document.querySelector('[data-action="more"]'));
  document.body.innerHTML=scoreSourcesView(catalog,{year:'115',instrument:'口琴獨奏'},24);
  assert.ok(document.querySelector('.collection-title').textContent.includes('Original collection title'));
  assert.ok(document.querySelector('.collection-original').textContent.includes('<script>unsafe</script>'));
  assert.equal(document.querySelector('script'),null);
  assert.equal(document.querySelectorAll('.score-evidence a').length,2);
  assert.doesNotMatch(document.body.textContent,/\b(?:undefined|NaN)\b/);
 }
});

test('Taiwan ROC academic years show Gregorian context and sort chronologically alongside international years',async()=>{
 const {academicYearLabel}=await import('../assets/scores.js');
 for(const locale of ['en','ja','ko','zh-Hant']){
  setLocale(locale);
  assert.match(academicYearLabel(rows[0]),/^2026 \(.+115/);
  assert.equal(academicYearLabel(rows[3]),'2025');
  assert.equal(academicYearLabel({countryCode:'JP',year:'115'}),'115');
  assert.equal(academicYearLabel({countryCode:'TW',year:'2026'}),'2026');
  assert.deepEqual(filterScores(rows).map(row=>row.id),['a','d','c','b']);
  document.body.innerHTML=scoresView(catalog,{},24);
  assert.match(document.querySelector('[data-filter="year"] option[value="115"]').textContent,/2026/);
  assert.match(document.querySelector('.score-row-meta').textContent,/2026/);
 }
});

test('repertoire table keeps comparison fields and actionable evidence in separate labelled columns', () => {
  setLocale('en');
  document.body.innerHTML = scoresView(catalog, {}, 24);
  const table = document.querySelector('table.score-table');
  assert.equal(table.querySelectorAll('thead th[scope="col"]').length, 4);
  assert.match(table.querySelector('caption').textContent, /Competition repertoire/);
  const row = table.querySelector('tbody tr');
  assert.equal(row.children.length, 4);
  assert.match(row.querySelector('.score-main').textContent, /Alpha <b>原曲<\/b>/);
  assert.match(row.querySelector('.score-context').textContent, /2026.*Harmonica solo.*國中/);
  assert.match(row.querySelector('.score-publisher').textContent, /Publisher One/);
  assert.equal(row.querySelectorAll('.score-actions .score-evidence a').length, 2);
  assert.ok(row.querySelector('.score-actions .context-report-link'));
  assert.equal(document.querySelectorAll('tbody tr').length, rows.length);
});

test('collections show only supplied source media and linked original posts, without unsafe or duplicated media', () => {
  setLocale('en');
  const collection = { ...catalog.scoreSources[0], images: ['/assets/poster.webp', 'javascript:alert(1)'], relatedPosts: [
    { url: 'https://example.org/announcement', image: '/assets/poster.webp', text: '原文 <script>unsafe</script>\n' + 'Full announcement. '.repeat(30), publishedAt: '2026-09-23T01:00:00Z' },
    { url: 'https://example.org/announcement', image: '/assets/duplicate.webp', text: 'duplicate' },
    { url: 'javascript:alert(1)', image: '/assets/unsafe.webp', text: 'unsafe linked post' },
  ] };
  document.body.innerHTML = scoreSourcesView({ scoreSources: [collection] });
  assert.equal(document.querySelectorAll('.collection-media img').length, 1);
  assert.equal(document.querySelector('.collection-media img').getAttribute('src'), '/assets/poster.webp');
  assert.equal(document.querySelectorAll('.collection-post').length, 1);
  assert.match(document.querySelector('.collection-post .feed-text').textContent, /<script>unsafe<\/script>/);
  assert.equal(document.querySelector('script'), null);
  assert.equal(document.querySelector('[data-expand-post]').getAttribute('aria-expanded'), 'false');
  assert.equal(document.querySelector('.collection-original-link').href, 'https://example.org/announcement');
  document.body.innerHTML = scoreSourcesView(catalog);
  assert.equal(document.querySelector('.collection-post,.collection-media'), null);
});
