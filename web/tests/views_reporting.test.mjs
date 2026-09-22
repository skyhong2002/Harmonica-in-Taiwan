import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { setLocale } from '../assets/i18n.js';
import { sourceCard, sourceDetail, postCard, eventCard } from '../assets/views.js';
import { submissionContext } from '../assets/reporting.js';

const source={id:'jp-1',name:'日本の口琴 <Original>',countryCode:'JP',type:'artist',url:'/source/japan-original/',links:[{url:'https://example.com/artist',label:'Original'}]};
const post={id:'post-1',sourceId:source.id,title:'Original post & announcement',text:'Original source text',url:'https://example.com/post',platform:'instagram',publishedAt:'2026-01-01'};
const event={id:'event-1',title:'Concert',countryCode:'KR',sourceUrl:'https://example.com/event',start:'2099-01-01',allDay:true,timezone:'Asia/Seoul'};

test('source rows, source profiles, posts and events report their own exact public context',()=>{
  const {window}=new JSDOM('<main></main>',{url:'https://harmonica.observe.tw/'});
  for (const key of ['location','document','localStorage']) Object.defineProperty(globalThis,key,{configurable:true,value:window[key]});
  const root=window.document.querySelector('main');
  for (const locale of ['en','zh-Hant','ja','ko']) {
    setLocale(locale);
    const cases=[
      [sourceCard(source),'.src-links .context-report-link','https://harmonica.observe.tw/source/japan-original/',source.name,'JP'],
      [sourceDetail(source,{sources:[source],posts:[],events:[]},new Set()),'.source-profile .context-report-link','https://harmonica.observe.tw/source/japan-original/',source.name,'JP'],
      [postCard(post,[source]),'.feed-actions .context-report-link',post.url,post.title,'JP'],
      [eventCard(event),'.card-bottom .context-report-link',event.sourceUrl,event.title,'KR'],
    ];
    for (const [html,selector,url,name,countryCode] of cases) {
      root.innerHTML=html;
      const anchor=root.querySelector(selector);
      assert.ok(anchor,selector);
      const query=new URL(anchor.href).search;
      assert.deepEqual(submissionContext(query),{url,name,countryCode});
      assert.equal(new URL(anchor.href).searchParams.get('lang'),locale);
      assert.equal(root.querySelector('script'),null);
    }
  }
  root.innerHTML=eventCard({...event,countryCode:undefined});
  assert.equal(submissionContext(new URL(root.querySelector('.context-report-link').href).search).countryCode,'');
  root.innerHTML=postCard({...post,url:'javascript:alert(1)'},[source]);
  assert.equal(root.querySelector('.context-report-link'),null);
  window.close();
});
