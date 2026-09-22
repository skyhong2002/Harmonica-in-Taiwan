import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost/' });
globalThis.document = dom.window.document;
globalThis.localStorage = dom.window.localStorage;
const {setLocale} = await import('../assets/i18n.js');
const {shortDate, shortDateTime, shortEventDate, timestamp} = await import('../assets/utils.js');
const now = Date.parse('2026-09-23T00:00:00Z');
test('short timestamps use 24-hour time and retain full accessible dates', () => {
 setLocale('en');
 const options = {now,timeZone:'Asia/Taipei'};
 assert.equal(shortDateTime('2026-09-22T10:00:00Z',options),'Sep 22 · 18:00');
 assert.equal(shortDateTime('2026-09-22T16:00:00Z',options),'Sep 23 · 00:00');
 document.body.innerHTML=timestamp('2026-09-22T10:00:00Z',options);
 const time=document.querySelector('time');
 assert.equal(time.textContent,'Sep 22 · 18:00');
 assert.equal(time.dateTime,'2026-09-22T10:00:00.000Z');
 assert.match(time.title,/2026.*18:00.*GMT\+8/);
 assert.equal(time.getAttribute('aria-label'),time.title);
 assert.equal(shortDate('2018-09-22',options),'Sep 22, 2018');
 assert.equal(shortDate('2027-01-01',{now:Date.parse('2027-01-01T01:00:00Z'),timeZone:'America/Los_Angeles'}),'Jan 1, 2027');
});
test('event ranges share a date while preserving local zones and unknown ends', () => {
 setLocale('en');
 const event={start:'2026-09-25T12:30:00Z',end:'2026-09-25T13:30:00Z',timezone:'Asia/Taipei'};
 assert.equal(shortEventDate(event,{now}),'Sep 25 · 20:30–21:30');
 assert.equal(shortEventDate({...event,endEstimated:true},{now}),'Sep 25 · 20:30');
 assert.equal(shortEventDate({...event,timezone:'America/Los_Angeles'},{now}),'Sep 25 · 05:30–06:30');
 assert.equal(shortEventDate({...event,end:'invalid'},{now}),'Sep 25 · 20:30');
});
test('civil dates preserve exclusive ends and both years across New Year', () => {
 setLocale('en');
 for(const timezone of ['Asia/Taipei','America/Los_Angeles','America/New_York']) {
  assert.equal(shortEventDate({start:'2026-03-07',end:'2026-03-10',allDay:true,timezone},{now}),'Mar 7 – Mar 9');
  assert.equal(shortEventDate({start:'2026-03-07',end:'2026-03-08',allDay:true,timezone},{now}),'Mar 7');
  assert.equal(shortEventDate({start:'2026-12-31',end:'2027-01-02',allDay:true,timezone},{now}),'Dec 31, 2026 – Jan 1, 2027');
 }
 assert.equal(shortEventDate({start:'2026-12-31T23:00:00Z',end:'2027-01-01T01:00:00Z',timezone:'UTC'},{now}),'Dec 31, 2026 · 23:00 – Jan 1, 2027 · 01:00');
});
test('DST folds and jumps retain distinguishing offsets', () => {
 setLocale('en');
 assert.equal(shortEventDate({start:'2026-11-01T05:30:00Z',end:'2026-11-01T06:30:00Z',timezone:'America/New_York'},{now}),'Nov 1 · 01:30 GMT-4–01:30 GMT-5');
 assert.equal(shortEventDate({start:'2026-03-08T06:30:00Z',end:'2026-03-08T07:30:00Z',timezone:'America/New_York'},{now}),'Mar 8 · 01:30 GMT-5–03:30 GMT-4');
});
test('four locales retain localized dates without AM/PM or redundant offsets', () => {
 const expected={'en':'Sep 22','zh-Hant':'9月22日',ja:'9月22日',ko:'9월 22일'};
 for(const [locale,label] of Object.entries(expected)) {
  setLocale(locale);
  assert.equal(shortDateTime('2026-09-22T10:00:00Z',{now,timeZone:'Asia/Taipei'}),`${label} · 18:00`);
 }
 setLocale('en');
 assert.equal(shortDateTime('2026-09-22T10:00:00Z',{now,timeZone:'invalid'}),'Sep 22 · 10:00');
 for(const value of [null,undefined,'invalid','2026-02-30']) assert.doesNotMatch(timestamp(value,{now}),/<time|1970|Invalid Date/);
});
