import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { reportLink, submissionContext, contextNote } from '../assets/reporting.js';
import { setLocale } from '../assets/i18n.js';
import { submitView, syncCommunityUi } from '../assets/community.js';

function browser(search='') {
  const {window}=new JSDOM('<main></main>',{url:'https://harmonica.observe.tw/submit/'+search});
  for (const key of ['window','document','location','localStorage']) Object.defineProperty(globalThis,key,{configurable:true,value:key==='window'?window:window[key]});
  return window;
}
const catalog={countries:[{code:'JP'},{code:'TW'},{code:'INTERNATIONAL'}]};

test('report links carry only public context with localized labels and safe source URLs',()=>{
  const window=browser();
  const labels={en:'Report','zh-Hant':'回報資料',ja:'情報を報告',ko:'정보 신고'};
  for (const [locale,label] of Object.entries(labels)) {
    setLocale(locale);
    const row={name:'Duo <North> & "South"',url:'/source/duo/',countryCode:'jp',token:'PRIVATE',note:'PRIVATE'};
    document.querySelector('main').innerHTML=reportLink(row);
    const anchor=document.querySelector('a');
    assert.equal(anchor.textContent,label);
    assert.equal(anchor.getAttribute('aria-label'),label+': '+row.name);
    const url=new URL(anchor.href);
    assert.equal(url.pathname,'/submit/');
    assert.equal(url.searchParams.get('reportUrl'),'https://harmonica.observe.tw/source/duo/');
    assert.equal(url.searchParams.get('reportName'),row.name);
    assert.equal(url.searchParams.get('reportCountry'),'JP');
    assert.equal(url.searchParams.get('lang'),locale);
    assert.ok(!anchor.outerHTML.includes('PRIVATE'));
    assert.deepEqual([...url.searchParams.keys()].sort(),['lang','reportCountry','reportName','reportUrl']);
    assert.equal(document.querySelector('script'),null);
  }
  assert.equal(reportLink({url:'javascript:alert(1)'}),'');
  assert.equal(reportLink({url:'//evil.example/path'}),'');
  assert.equal(reportLink({url:'https://user:pass@evil.example/path'}),'');
  window.close();
});

test('context reader supports current and legacy report links without assuming a country',()=>{
  const window=browser();
  assert.deepEqual(submissionContext('?reportUrl=%2Fsource%2Fduo%2F&reportName=Duo&reportCountry=JP'),{url:'https://harmonica.observe.tw/source/duo/',name:'Duo',countryCode:'JP'});
  assert.deepEqual(submissionContext('?source=https%3A%2F%2Fexample.com%2Fpost&name=Original&countryCode=kr&desired=untrusted'),{url:'https://example.com/post',name:'Original',countryCode:'KR'});
  assert.deepEqual(submissionContext('?url=https%3A%2F%2Fexample.com%2Fpost&name=Unknown&countryCode=International'),{url:'https://example.com/post',name:'Unknown',countryCode:''});
  assert.deepEqual(submissionContext(''),{url:'',name:'',countryCode:''});
  assert.equal(submissionContext('?reportUrl=javascript%3Aalert(1)').url,'');
  assert.equal(submissionContext('?reportUrl=https%3A%2F%2Fu%3Ap%40example.com').url,'');
  assert.equal(submissionContext('?reportCountry=TW%22%3E%3Cscript%3E').countryCode,'');
  assert.equal(submissionContext('?name='+encodeURIComponent('x'.repeat(3000))).name.length,500);
  window.close();
});

test('submission form prefills escaped context once and background refresh preserves user edits and focus',()=>{
  const original='Concert </textarea><script>bad()</script>';
  const search='?'+new URLSearchParams({reportUrl:'https://example.com/post?a=1&b=2',reportName:original,reportCountry:'JP'});
  const window=browser(search);
  for (const locale of ['en','zh-Hant','ja','ko']) {
    setLocale(locale);
    document.querySelector('main').innerHTML=submitView(catalog);
    const form=document.querySelector('#submission-form');
    assert.equal(form.elements.url.value,'https://example.com/post?a=1&b=2');
    assert.equal(form.elements.countryCode.value,'JP');
    assert.equal(form.elements.note.value,contextNote(original));
    assert.equal(document.querySelector('script'),null);
    assert.ok(form.elements.url.checkValidity());
    form.elements.note.value='My correction draft';
    form.elements.note.focus();
    syncCommunityUi();
    assert.equal(form.elements.note.value,'My correction draft');
    assert.equal(document.activeElement,form.elements.note);
  }
  window.history.replaceState(null,'','/submit/?reportUrl=https%3A%2F%2Fexample.com&reportCountry=ZZ');
  document.querySelector('main').innerHTML=submitView(catalog);
  assert.equal(document.querySelector('#submission-country').value,'');
  window.close();
});

test('form errors identify and focus the affected field; success persists and owns focus',async()=>{
  const window=browser();
  setLocale('en');
  const {contributeView,handleForm,refreshCommunity}=await import('../assets/community.js');
  const originalFetch=globalThis.fetch, originalFormData=globalThis.FormData;
  globalThis.FormData=window.FormData;
  let fail=true, posts=0, release;
  globalThis.fetch=async(path,options={})=>{
    if(options.method==='POST') {
      posts++;
      if(release) await new Promise(resolve=>release=resolve);
      return {ok:!fail,json:async()=>fail?{code:'invalid_token'}:{}};
    }
    return {ok:true,json:async()=>path.includes('session')?{csrfToken:'mock',contributions:[],submissions:[]}:{}};
  };
  try {
    await refreshCommunity();
    const render=()=>document.querySelector('main').innerHTML=contributeView();
    render();
    document.body.insertAdjacentHTML('afterbegin','<select id="language-select"><option>English</option></select>');
    let form=document.querySelector('form');
    form.elements.name.value='My shared quota';form.elements.token.value='mock-credential-not-real';form.elements.budgetUsd.value='1';form.elements.consent.checked=true;
    await handleForm(form,render);
    assert.equal(document.activeElement,form.elements.token);
    assert.equal(form.elements.token.getAttribute('aria-invalid'),'true');
    assert.match(form.elements.token.getAttribute('aria-describedby'),/token-hint form-message/);
    assert.equal(form.elements.token.value,'');
    assert.equal(form.elements.name.value,'My shared quota');
    assert.ok(document.querySelector('#form-message').textContent.includes('verify'));
    fail=false;release=true;
    form.elements.token.value='mock-credential-not-real';
    const pending=handleForm(form,render);
    assert.equal(form.getAttribute('aria-busy'),'true');
    assert.equal(document.querySelector('#language-select').disabled,true);
    syncCommunityUi();
    assert.equal(form.querySelector('[type=submit]').disabled,true);
    await handleForm(form,render);
    assert.equal(posts,2,'repeated activation cannot submit a pending form twice');
    release();await pending;
    assert.equal(document.activeElement.id,'form-message');
    assert.match(document.activeElement.textContent,/contribution is active/);
    syncCommunityUi();
    assert.match(document.querySelector('#form-message').textContent,/contribution is active/);
    assert.equal(form.getAttribute('aria-busy'),null);
    assert.equal(document.querySelector('#language-select').disabled,false);
  } finally {globalThis.fetch=originalFetch;globalThis.FormData=originalFormData;window.close();}
});

test('withdrawal dialog names the contribution and supports cancel, completion, and repeat protection',async()=>{
  const window=browser();setLocale('en');
  const {contributeView,refreshCommunity,withdraw}=await import('../assets/community.js');
  const originalFetch=globalThis.fetch;
  let withdrawn=false,deletes=0;
  globalThis.fetch=async(path,options={})=>{
    if(options.method==='DELETE'){deletes++;withdrawn=true;return{ok:true,json:async()=>({})};}
    return{ok:true,json:async()=>path.includes('session')?{csrfToken:'mock',contributions:[{id:'one',name:'Japan contribution <safe>',status:withdrawn?'revoked':'active',budgetUsd:1}],submissions:[]}:{}};
  };
  try {
    await refreshCommunity();
    const render=()=>document.querySelector('main').innerHTML=contributeView();render();
    document.body.insertAdjacentHTML('beforeend','<dialog id="confirm-dialog"></dialog>');
    const dialog=document.querySelector('dialog');
    dialog.showModal=()=>{dialog.open=true};
    const close=value=>{dialog.returnValue=value;dialog.open=false;dialog.dispatchEvent(new window.Event('close'));};
    let pending=withdraw('one',render);
    assert.equal(dialog.getAttribute('aria-labelledby'),'withdraw-dialog-title');
    assert.match(document.querySelector('#withdraw-dialog-title').textContent,/Japan contribution <safe>/);
    assert.equal(document.querySelector('safe'),null);
    close('cancel');await pending;assert.equal(deletes,0);
    pending=withdraw('one',render);
    await withdraw('one',render);
    close('confirm');await pending;
    assert.equal(deletes,1);
    assert.equal(document.activeElement.id,'withdraw-message');
    assert.match(document.activeElement.textContent,/withdrawn/);
    assert.equal(document.querySelector('[data-withdraw]'),null);
  } finally {globalThis.fetch=originalFetch;window.close();}
});
