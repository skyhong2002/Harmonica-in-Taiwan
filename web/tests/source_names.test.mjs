import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<html><body></body></html>', {url:'http://localhost/'});
globalThis.document=dom.window.document;
globalThis.localStorage=dom.window.localStorage;
const {setLocale}=await import('../assets/i18n.js');
const {sourceNameRows,sourceNamesMarkup,sourceNameText,sourceTypesMarkup}=await import('../assets/source-names.js');
const {sourceCard,sourceDetail,sortSources}=await import('../assets/views.js');
const source={id:'example',name:'原始名',nameEn:'Original Name',type:'學校社團',names:{original:'原始名','zh-Hant':'中文名',en:'English Name',ja:'日本語名',ko:'한국어 이름'},links:[]};

test('directory shows reading-language, Chinese, English and original names without repeating identical values',()=>{
 for(const locale of ['en','zh-Hant','ja','ko']){
  setLocale(locale);
  const rows=sourceNameRows(source);
  assert.equal(rows[0].text,source.names[locale]);
  for(const value of ['原始名','中文名','English Name',source.names[locale]]) assert.ok(rows.some(row=>row.text===value));
  document.body.innerHTML=sourceCard(source,new Set(),{posts:[]});
  assert.ok(document.querySelector('.source-names').textContent.includes(source.names[locale]));
 }
 const rows=sourceNameRows({...source,names:{original:'Same','zh-Hant':'Same',en:' SAME ',ja:'Same'}},'ja');
 assert.equal(rows.length,1);
 assert.equal(rows[0].text,'Same');
 assert.deepEqual(rows[0].languages,['ja','original','zh-Hant','en']);
});

test('names are escaped, never invented from missing language data, and all translations are searchable',()=>{
 setLocale('ja');
 const input={name:'<img src=x onerror=alert(1)>',nameEn:'Name & Co'};
 document.body.innerHTML=sourceNamesMarkup(input);
 assert.equal(document.querySelector('img'),null);
 assert.match(document.body.textContent,/<img src=x onerror=alert\(1\)>/);
 assert.equal(sourceNameRows(input)[0].text,input.name);
 assert.equal(sourceNameRows(input).length,2);
 assert.match(sourceNameText(source),/한국어 이름/);
 assert.match(sourceNameText(source),/中文名/);
});

test('type labels retain original category alongside Chinese English and reading-language labels',()=>{
 for(const [locale,current] of [['en','Club'],['zh-Hant','社團'],['ja','クラブ'],['ko','동아리']]){
  setLocale(locale);document.body.innerHTML=sourceTypesMarkup(source);
  for(const value of [current,'Club','社團','學校社團'])assert.ok(document.body.textContent.includes(value));
 }
 document.body.innerHTML=sourceTypesMarkup({...source,type:'Unknown original category'});
 assert.match(document.body.textContent,/Unknown original category/);
});

test('source details preserve multilingual names, reference notice and sort by the visible locale name',()=>{
 setLocale('ja');
 document.body.innerHTML=sourceDetail(source,{sources:[source],posts:[]},new Set());
 assert.equal(document.querySelector('h1').textContent,'日本語名');
 for(const value of ['原始名','中文名','English Name'])assert.ok(document.querySelector('.source-profile').textContent.includes(value));
 assert.match(document.querySelector('.source-translation-note').textContent,/参考訳/);
 const rows=[{...source,id:'z',names:{original:'A',ja:'Z'}},{...source,id:'a',names:{original:'Z',ja:'A'}}];
 assert.deepEqual(sortSources(rows).map(row=>row.id),['a','z']);
});


test('recorded names are not presented as verified official-language names',()=>{
 for(const [locale,label] of [['zh-Hant','收錄原名'],['en','Recorded name'],['ja','登録名'],['ko','등록 이름']]){
  setLocale(locale);
  document.body.innerHTML=sourceCard(source,new Set(),{posts:[]});
  assert.ok(document.querySelector('.source-names').textContent.includes(label));
  assert.equal(source.names.original,'原始名');
 }
});


test('type provenance is labelled as the original category rather than a recorded name',()=>{
 for(const [locale,label] of [['zh-Hant','原始類型'],['en','Original type'],['ja','元の分類'],['ko','원래 유형']]){
  setLocale(locale);document.body.innerHTML=sourceTypesMarkup(source);
  assert.ok(document.body.textContent.includes(label));
 }
});
