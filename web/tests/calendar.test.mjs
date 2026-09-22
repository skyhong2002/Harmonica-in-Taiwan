import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {calendarView,bindCalendar,calendarEventRange,calendarEventsOnDay,normalizeCalendarState,validCivilDate} from '../assets/calendar.js';
import {setLocale} from '../assets/i18n.js';

const events=[
 {id:'multi',title:'Three-day festival',countryCode:'US',start:'2026-03-07',end:'2026-03-10',allDay:true,timezone:'America/Los_Angeles',url:'https://example.com/festival'},
 {id:'late',title:'Night concert',countryCode:'US',start:'2026-03-08T23:30:00-07:00',end:'2026-03-09T00:00:00-07:00',timezone:'America/Los_Angeles',url:'https://example.com/night'},
 {id:'dst',title:'DST overnight',countryCode:'US',start:'2026-03-07T23:30:00-08:00',end:'2026-03-08T03:30:00-07:00',timezone:'America/Los_Angeles'},
 {id:'jp',title:'日本の演奏会',countryCode:'JP',start:'2026-03-09T01:00:00+09:00',end:'2026-03-09T02:00:00+09:00',timezone:'Asia/Tokyo'},
 {id:'unknown',title:'Unknown region',start:'2026-03-09',allDay:true},
];
const catalog={events,countries:[{code:'US'},{code:'JP'}]};
function dom(){const {window}=new JSDOM('<main></main>',{url:'https://example.com/?lang=en'});for(const key of ['window','document','location','localStorage'])Object.defineProperty(globalThis,key,{value:key==='window'?window:window[key],configurable:true});return window;}

test('calendar event dates retain event-local days, DST, exclusive ends and unknown dates',()=>{
 assert.deepEqual(calendarEventRange(events[0]),{start:'2026-03-07',end:'2026-03-09'});
 assert.deepEqual(calendarEventRange(events[1]),{start:'2026-03-08',end:'2026-03-08'});
 assert.deepEqual(calendarEventRange(events[2]),{start:'2026-03-07',end:'2026-03-08'});
 assert.deepEqual(calendarEventRange(events[3]),{start:'2026-03-09',end:'2026-03-09'});
 assert.deepEqual(calendarEventRange({start:'2026-11-01T00:30:00-04:00',end:'2026-11-01T02:30:00-05:00',timezone:'America/New_York'}),{start:'2026-11-01',end:'2026-11-01'});
 assert.equal(calendarEventsOnDay(events,'2026-03-10').length,0);
 assert.equal(calendarEventsOnDay(events,'2026-03-09','JP').length,1);
 assert.equal(calendarEventsOnDay(events,'2026-03-09','UNKNOWN')[0].id,'unknown');
 assert.equal(calendarEventsOnDay(events,'2026-03-09','TW').length,0);
 assert.equal(calendarEventRange({start:''}),null);
 assert.equal(calendarEventRange({start:'2026-02-30'}),null);
 assert.equal(validCivilDate('2024-02-29'),true);
 assert.equal(validCivilDate('2026-02-29'),false);
});

test('calendar controls navigate months and days, preserve country and emit independent URL state',()=>{
 const window=dom(),root=document.querySelector('main'),patches=[];
 setLocale('en');const state={month:'2026-03',day:'2026-03-08',calendarCountry:'US',country:'JP'};
 root.innerHTML=calendarView(catalog,state);const cleanup=bindCalendar(root,{catalog,state,onStateChange:p=>patches.push(p)});
 assert.equal(root.querySelectorAll('.calendar-day').length,42);
 assert.equal(root.querySelectorAll('.calendar-day[tabindex="0"]').length,1);
 assert.equal(root.querySelectorAll('.calendar-agenda .event-card').length,3);
 root.querySelector('[data-calendar-day="2026-03-09"]').click();
 assert.equal(root.querySelectorAll('.calendar-agenda .event-card').length,1);
 assert.equal(patches.at(-1).day,'2026-03-09');
 const country=root.querySelector('[data-calendar-country]');country.value='JP';country.dispatchEvent(new window.Event('change',{bubbles:true}));
 assert.match(root.querySelector('.calendar-agenda').textContent,/日本の演奏会/);
 assert.equal(patches.at(-1).calendarCountry,'JP');assert.equal(patches.at(-1).country,undefined);
 root.querySelector('[data-calendar-move="1"]').click();assert.equal(patches.at(-1).month,'2026-04');assert.equal(patches.at(-1).calendarCountry,'JP');assert.ok(root.querySelector('.calendar-month-empty'));
 root.querySelector('[data-calendar-move="-1"]').click();assert.equal(patches.at(-1).month,'2026-03');
 const input=root.querySelector('[data-calendar-month]');input.value='2026-12';input.dispatchEvent(new window.Event('change',{bubbles:true}));assert.equal(patches.at(-1).day,'2026-12-01');
 const year=root.querySelector('[data-calendar-year]');year.value='2024';year.dispatchEvent(new window.Event('change',{bubbles:true}));assert.equal(patches.at(-1).month,'2024-12');
 root.querySelector('[data-calendar-today]').click();assert.equal(patches.at(-1).day,normalizeCalendarState().day);assert.equal(patches.at(-1).calendarCountry,'JP');
 cleanup();window.close();
});

test('keyboard navigation crosses month boundaries, keeps focus and handles leap-year days',()=>{
 const window=dom(),root=document.querySelector('main'),patches=[];const state={month:'2024-02',day:'2024-02-29'};
 root.innerHTML=calendarView(catalog,state);const cleanup=bindCalendar(root,{catalog,state,onStateChange:p=>patches.push(p)});
 root.querySelector('[data-calendar-day="2024-02-29"]').dispatchEvent(new window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 assert.equal(patches.at(-1).day,'2024-03-01');assert.equal(document.activeElement.dataset.calendarDay,'2024-03-01');
 document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown',{key:'PageUp',bubbles:true}));assert.equal(patches.at(-1).day,'2024-02-01');
 document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown',{key:'End',bubbles:true}));assert.equal(patches.at(-1).day,'2024-02-03');
 cleanup();window.close();
});

test('month grid and agenda labels support four languages without translating original event titles',()=>{
 const window=dom();
 for(const [locale,title] of [['en','Calendar'],['zh-Hant','行事曆'],['ja','カレンダー'],['ko','달력']]){
  setLocale(locale);const html=calendarView(catalog,{month:'2026-03',day:'2026-03-09',calendarCountry:'JP'});
  assert.ok(html.includes(title));assert.ok(html.includes('日本の演奏会'));assert.ok(!html.includes('undefined'));assert.ok(html.includes('value="JP" selected'));
 }
 window.close();
});
