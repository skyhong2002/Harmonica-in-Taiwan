import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost/' });
globalThis.document = dom.window.document;
globalThis.localStorage = dom.window.localStorage;
const { setLocale } = await import('../assets/i18n.js');
const { sourceCard, sortSources, postCard, togglePostExpansion } = await import('../assets/views.js');
const sources = [{ id:'a',name:'Alpha',countryCode:'JP',url:'/source/alpha/',updatedAt:'2026-01-01',avatar:'/assets/avatar.webp' },{id:'b',name:'Beta',countryCode:'KR',url:'/source/beta/',updatedAt:'2026-02-01'}];
const catalog = {posts:[{sourceId:'b'},{sourceId:'b'},{sourceId:'a'}]};
test('directory sorting uses real post counts and remains independent of locale and following',()=>{
 setLocale('en');
 assert.deepEqual(sortSources(sources,'posts',true,catalog).map(s=>s.id),['b','a']);
 assert.deepEqual(sortSources(sources,'updated',false,catalog).map(s=>s.id),['a','b']);
 const html=sourceCard(sources[1],new Set(['b']),catalog);
 document.body.innerHTML=html;
 assert.equal(document.querySelector('.src-count').textContent,'2');
 assert.equal(document.querySelector('[data-follow]').getAttribute('aria-pressed'),'true');
 assert.equal(document.querySelector('h3 a').getAttribute('href'),'/source/beta/');
});
test('long original expands and collapses without truncating, duplicating, or interpreting markup',()=>{
 const original='原文 <script>alert(1)</script> & 保持\n'.repeat(20);
 for(const locale of ['en','zh-Hant','ja','ko']){
  setLocale(locale);
  document.body.innerHTML=postCard({sourceId:'a',text:original,url:'https://example.org/post',publishedAt:'2026-01-01',platform:'instagram'},sources);
  const button=document.querySelector('[data-expand-post]'), text=document.querySelector('.feed-text');
  assert.equal(text.textContent,original);
  assert.equal(document.querySelector('script'),null);
  assert.equal(document.querySelectorAll('.feed-text').length,1);
  togglePostExpansion(button);
  assert.equal(button.getAttribute('aria-expanded'),'true');
  assert.ok(text.classList.contains('is-expanded'));
  togglePostExpansion(button);
  assert.equal(button.getAttribute('aria-expanded'),'false');
  assert.ok(!text.classList.contains('is-expanded'));
  assert.equal(text.textContent,original);
 }
});
test('posts use source avatar fallback and link only explicit matching events',()=>{
 setLocale('en');
 const post={sourceId:'a',text:'Original',url:'https://example.org/post',publishedAt:'2026-01-01',platform:'instagram'};
 const events=[{id:'match',title:'Actual linked event',url:post.url,start:'2026-01-01',allDay:true,timezone:'America/Los_Angeles'},{id:'other',title:'Unrelated event',url:'https://example.org/elsewhere',start:'2026-01-01'}];
 document.body.innerHTML=postCard(post,sources,new Set(['a']),events);
 assert.equal(document.querySelector('.feed-avatar-wrap img').getAttribute('src'),sources[0].avatar);
 assert.equal(document.querySelectorAll('.feed-ev').length,1);
 assert.match(document.querySelector('.feed-ev').textContent,/Actual linked event/);
 assert.equal(document.querySelector('[data-share]').dataset.share,post.url);
 assert.equal(document.querySelector('[data-follow]').getAttribute('aria-pressed'),'true');
});
