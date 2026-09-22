import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {timelinePosts,timelineCard,timelineView,bindTimeline} from '../assets/timeline.js';
import {togglePostExpansion} from '../assets/views.js';
import {setLocale} from '../assets/i18n.js';
const catalog={sources:[{id:'jp',name:'日本の口琴',countryCode:'JP'},{id:'tw',name:'臺灣口琴社',countryCode:'TW'}],countries:[{code:'JP'},{code:'TW'}],events:[],posts:Array.from({length:61},(_,i)=>({id:'p'+i,sourceId:i%2?'jp':'tw',sourceName:i%2?'日本の口琴':'臺灣口琴社',countryCode:i%2?'JP':'TW',text:'Original '+i+'\n'+('完整原文 '.repeat(60)),platform:i%2?'instagram':'facebook',publishedAt:new Date(Date.UTC(2026,8,23,0,-i)).toISOString(),url:'https://example.com/post/'+i,image:i%3?'':'/assets/test.webp',isStory:i===60,storyState:i===60?'expired':undefined}))};
function setup(width=1440){const{window}=new JSDOM('<main></main>',{url:'https://example.com/?lang=en',pretendToBeVisual:true});for(const key of ['window','document','location','localStorage'])Object.defineProperty(globalThis,key,{value:key==='window'?window:window[key],configurable:true});window.innerWidth=width;window.scrollBy=()=>{};window.HTMLElement.prototype.getBoundingClientRect=function(){const height=this.classList.contains('feed-river-column')?[...this.children].reduce((sum,n)=>sum+100+(Number(n.dataset.timelineIndex)%3)*20,0):100;return{height,width:300,top:0,bottom:height};};return window;}

test('one chronological timeline excludes stories by default and filters country, platform and follows independently',()=>{
 assert.equal(timelinePosts(catalog,{}).length,60);
 assert.deepEqual(timelinePosts(catalog,{kind:'stories'}).map(p=>p.id),['p60']);
 assert.equal(timelinePosts(catalog,{country:'JP',platform:'instagram'}).length,30);
 assert.equal(timelinePosts(catalog,{country:'JP',platform:'facebook'}).length,0);
 assert.equal(timelinePosts(catalog,{kind:'following'},new Set(['tw'])).length,30);
 const reversed={...catalog,posts:[...catalog.posts].reverse()};assert.equal(timelinePosts(reversed,{})[0].id,'p0');
});

test('original image-first cards preserve escaped full original, source, follow/share/report and archive status',()=>{
 const window=setup();setLocale('en');const html=timelineCard({...catalog.posts[0],text:'<script>alert(1)</script>'+catalog.posts[0].text},catalog.sources,new Set(['tw']));
 document.querySelector('main').innerHTML=html;const card=document.querySelector('.home-feed-card');
 assert.ok(card.querySelector('.home-feed-thumb'));assert.ok(card.querySelector('.feed-text').textContent.includes('<script>alert(1)</script>'));assert.equal(card.querySelectorAll('script').length,0);
 assert.ok([...card.querySelector('.home-feed-body').children].indexOf(card.querySelector('.home-feed-thumb'))<[...card.querySelector('.home-feed-body').children].indexOf(card.querySelector('.feed-text')));
 assert.equal(card.querySelector('[data-follow]').getAttribute('aria-pressed'),'true');assert.ok(card.querySelector('[data-share]'));assert.ok(card.querySelector('a[href^="/submit/"]'));assert.match(timelineCard(catalog.posts[60],catalog.sources),/story-expired/);
 window.close();
});

test('original shortest-column layout uses 3 desktop columns and 1 mobile with no duplicate posts; expansion remains functional',async()=>{
 const window=setup(),root=document.querySelector('main');root.innerHTML=timelineView(catalog,{},new Set());
 const click=e=>{const b=e.target.closest('[data-expand-post]');if(b)togglePostExpansion(b);};root.addEventListener('click',click);
 const cleanup=bindTimeline(root);let cols=root.querySelectorAll('.feed-river-column');assert.equal(cols.length,3);assert.ok([...cols].every(n=>n.children.length>0));assert.equal(root.querySelectorAll('.home-feed-card').length,24);
 const button=root.querySelector('[data-expand-post]');button.click();await Promise.resolve();assert.equal(button.getAttribute('aria-expanded'),'true');assert.ok(button.closest('.home-feed-card').querySelector('.feed-text').classList.contains('is-expanded'));
 window.innerWidth=390;window.dispatchEvent(new window.Event('resize'));await new Promise(r=>setTimeout(r,130));cols=root.querySelectorAll('.feed-river-column');assert.equal(cols.length,1);assert.equal(root.querySelectorAll('.home-feed-card').length,24);assert.deepEqual([...cols[0].children].map(n=>Number(n.dataset.timelineIndex)),Array.from({length:24},(_,i)=>i));cleanup();root.removeEventListener('click',click);window.close();
});

test('unavailable images remove only the broken media frame and retain original text/source actions',async()=>{
 const window=setup(),root=document.querySelector('main');root.innerHTML=timelineView(catalog,{},new Set(),3);const cleanup=bindTimeline(root);
 const image=root.querySelector('.home-feed-thumb img'),card=image.closest('.home-feed-card');image.dispatchEvent(new window.Event('error'));await new Promise(r=>setTimeout(r,100));
 assert.equal(card.querySelector('.home-feed-thumb'),null);assert.ok(card.querySelector('.home-feed-body-no-image'));assert.ok(card.querySelector('.feed-text').textContent.includes('完整原文'));assert.ok(card.querySelector('.feed-open-link'));cleanup();window.close();
});

test('autoload starts only after manual load-more and always keeps a manual fallback',()=>{
 const window=setup(),root=document.querySelector('main'),observers=[];window.IntersectionObserver=class{constructor(cb){this.cb=cb;observers.push(this);}observe(node){this.node=node;}disconnect(){this.disconnected=true;}};
 root.innerHTML=timelineView(catalog,{},new Set(),24);let cleanup=bindTimeline(root);assert.equal(observers.length,0);root.querySelector('[data-action="more"]').click();cleanup();
 root.innerHTML=timelineView(catalog,{},new Set(),48);cleanup=bindTimeline(root);assert.equal(observers.length,1);let clicks=0;root.querySelector('[data-action="more"]').addEventListener('click',()=>clicks++);observers[0].cb([{isIntersecting:true}]);assert.equal(clicks,1);assert.equal(observers[0].disconnected,true);cleanup();root.innerHTML=timelineView(catalog,{},new Set(),100);const status=root.querySelector('.feed-load-more-status');status.focus();assert.equal(document.activeElement,status);assert.equal(root.querySelector('[data-action="more"]'),null);window.close();
});

test('timeline controls and actions translate in four languages while original text stays unchanged',()=>{
 const window=setup();for(const locale of ['en','zh-Hant','ja','ko']){setLocale(locale);const html=timelineView(catalog,{country:'JP'},new Set());assert.ok(html.includes('日本の口琴'));assert.ok(html.includes('id="catalog-search"'));assert.ok(html.includes('data-filter="platform"'));assert.ok(html.includes('data-filter="kind"'));assert.ok(!html.includes('undefined'));assert.ok(!html.includes('data-river-column'));}window.close();
});
