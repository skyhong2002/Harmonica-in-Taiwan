import { t, getLocale, locales, countryName } from './i18n.js';
import { esc, icon, link, date, number } from './utils.js';
import { eventCard } from './views.js';

const labels = {
  calendar: ['Calendar', '行事曆', 'カレンダー', '달력'],
  previous: ['Previous month', '上個月', '前の月', '이전 달'],
  next: ['Next month', '下個月', '次の月', '다음 달'],
  today: ['Today', '今天', '今日', '오늘'],
  month: ['Month', '月份', '月', '월'],
  emptyDay: ['No events listed for this day.', '這天目前沒有收錄的活動。', 'この日のイベントはまだ登録されていません。', '이 날짜에 등록된 행사가 없습니다.'],
  emptyMonth: ['No events listed this month for this country / region.', '這個月此國家／地區目前沒有收錄的活動。', 'この月・国や地域のイベントはまだ登録されていません。', '이 달에 선택한 국가·지역의 등록된 행사가 없습니다.'],
  eventCount: ['{count} events', '{count} 場活動', '{count}件のイベント', '행사 {count}개'],
  localDates: ['Dates follow each event’s local time zone.', '日期依各活動當地時區顯示。', '日付は各イベントの現地時間に基づきます。', '날짜는 각 행사의 현지 시간대를 따릅니다.'],
  viewEvents: ['All events', '所有活動', 'すべてのイベント', '모든 행사'],
  more: ['+{count} more', '另有 {count} 場', 'ほか{count}件', '외 {count}개'],
};
const c = (key, values = {}) => (labels[key]?.[locales.indexOf(getLocale())] || labels[key]?.[0] || key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '');
const DAY = 86400000;
export function validCivilDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(value + 'T12:00:00Z');
  return Number.isFinite(+parsed) && parsed.toISOString().slice(0, 10) === value;
}
function civilFromInstant(value, timezone) {
  const timestamp = new Date(value);
  if (!Number.isFinite(+timestamp)) return null;
  let formatter;
  try { formatter = new Intl.DateTimeFormat('en-CA-u-ca-gregory-nu-latn', { year:'numeric',month:'2-digit',day:'2-digit', ...(timezone ? {timeZone:timezone} : {}) }); }
  catch { formatter = new Intl.DateTimeFormat('en-CA-u-ca-gregory-nu-latn', {year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'}); }
  const parts = Object.fromEntries(formatter.formatToParts(timestamp).map(p => [p.type,p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}
export function shiftCivilDay(day, delta) {
  return new Date(Date.parse(day + 'T12:00:00Z') + delta * DAY).toISOString().slice(0,10);
}
export function calendarEventRange(event) {
  // Date-only values are civil dates, independent of the viewer's timezone.
  const startCivil = validCivilDate(event.start) ? event.start : null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(event.start || '')) && !startCivil) return null;
  if (!event.start) return null;
  const start = startCivil || civilFromInstant(event.start, event.timezone || 'UTC');
  if (!start) return null;
  let end = start;
  if (event.allDay && validCivilDate(event.end)) {
    // ICS DTEND excludes the final day. Never subtract a day from DTSTART.
    end = event.end > start ? shiftCivilDay(event.end, -1) : start;
  } else if (event.end && Number.isFinite(Date.parse(event.end))) {
    const startAt = Date.parse(event.start), endAt = Date.parse(event.end);
    if (endAt > startAt) end = civilFromInstant(endAt - 1, event.timezone || 'UTC') || start;
  }
  return { start, end: end < start ? start : end };
}
export function normalizeCalendarState(state = {}, now = Date.now()) {
  const today = civilFromInstant(now);
  let day = validCivilDate(state.day) && state.day >= '1900-01-01' && state.day <= '2199-12-31' ? state.day : today;
  let month = /^\d{4}-(0[1-9]|1[0-2])$/.test(state.month || '') && +state.month.slice(0,4) >= 1900 && +state.month.slice(0,4) <= 2199 ? state.month : day.slice(0,7);
  if (day.slice(0,7) !== month) day = month + '-01';
  return { month, day, calendarCountry: typeof state.calendarCountry === 'string' ? state.calendarCountry : '' };
}
export function calendarEventsOnDay(events, day, country = '') {
  return (events || []).filter(event => {
    if (country && (event.countryCode || 'UNKNOWN') !== country) return false;
    const range = calendarEventRange(event);
    return range && range.start <= day && range.end >= day;
  }).sort((a,b) => (Date.parse(a.start) - Date.parse(b.start)) || String(a.title).localeCompare(String(b.title), getLocale()));
}
function monthDates(month) {
  const first = `${month}-01`, weekday = new Date(first + 'T12:00:00Z').getUTCDay();
  // Sunday-first rows match the reference calendar; dates remain civil values.
  const begin = shiftCivilDay(first, -weekday);
  return Array.from({length:42}, (_, i) => shiftCivilDay(begin,i));
}
function monthLabel(month) { return date(month + '-01', {year:'numeric',month:'long',day:undefined}); }
function calendarBody(catalog, state) {
  const events = catalog.events || [], today = civilFromInstant(Date.now());
  const days = monthDates(state.month);
  const eventsByDay = new Map(days.map(day => [day,calendarEventsOnDay(events,day,state.calendarCountry)]));
  const monthEvents = events.filter(event => {
    if (state.calendarCountry && (event.countryCode || 'UNKNOWN') !== state.calendarCountry) return false;
    const range = calendarEventRange(event);
    return range && range.start.slice(0,7) <= state.month && range.end.slice(0,7) >= state.month;
  });
  const countries = new Map((catalog.countries || []).map(row => [row.code,countryName(row.code,row.name)]));
  for (const event of events) if (!countries.has(event.countryCode || 'UNKNOWN')) countries.set(event.countryCode || 'UNKNOWN',countryName(event.countryCode,event.country));
  if (state.calendarCountry && !countries.has(state.calendarCountry)) countries.set(state.calendarCountry,countryName(state.calendarCountry));
  const selectedEvents = calendarEventsOnDay(events,state.day,state.calendarCountry);
  const dayLabel = date(state.day,{year:'numeric',month:'long',day:'numeric',weekday:'long'});
  return `<header class="calendar-heading"><h2>${c('calendar')}</h2>${link('/events/',c('viewEvents'),'text-link')}</header><div class="calendar-toolbar"><div class="calendar-month-nav"><button type="button" data-calendar-move="-1" aria-label="${c('previous')}" ${state.month === '1900-01' ? 'disabled' : ''}>${icon('chevron')}</button><h3 aria-live="polite">${esc(monthLabel(state.month))}</h3><button type="button" data-calendar-move="1" aria-label="${c('next')}" ${state.month === '2199-12' ? 'disabled' : ''}>${icon('chevron')}</button><button type="button" class="calendar-today" data-calendar-today>${c('today')}</button></div><div class="calendar-selectors"><label class="calendar-month-input"><span>${c('month')}</span><input type="number" min="1900" max="2199" step="1" data-calendar-year value="${state.month.slice(0,4)}" aria-label="${t('year')}"><select data-calendar-month aria-label="${c('month')}">${Array.from({length:12},(_,i)=>{const value=state.month.slice(0,4)+'-'+String(i+1).padStart(2,'0');return `<option value="${value}" ${value === state.month ? 'selected' : ''}>${esc(date(value+'-01',{month:'long',year:undefined,day:undefined}))}</option>`;}).join('')}</select></label><label><span>${t('country')}</span><select data-calendar-country><option value="">${t('allCountries')}</option>${[...countries].map(([code,label])=>`<option value="${esc(code)}" ${code === state.calendarCountry ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label></div></div><p class="calendar-timezone-note">${c('localDates')}</p><div class="calendar-layout"><div class="calendar-month-panel"><div class="calendar-weekdays" aria-hidden="true">${Array.from({length:7},(_,i)=>`<span>${esc(date(`2023-01-0${i+1}`,{weekday:'short',year:undefined,month:undefined,day:undefined}))}</span>`).join('')}</div><div class="calendar-grid" role="group" aria-label="${esc(monthLabel(state.month))}">${days.map(day => {
    const rows = eventsByDay.get(day), isToday = day === today, selected = day === state.day;
    return `<button type="button" class="calendar-day${day.slice(0,7) !== state.month ? ' other-month' : ''}${isToday ? ' today' : ''}${selected ? ' selected' : ''}" data-calendar-day="${day}" aria-pressed="${selected}" ${isToday ? 'aria-current="date"' : ''} aria-label="${esc(date(day))} · ${esc(c('eventCount',{count:number(rows.length)}))}" tabindex="${selected ? '0' : '-1'}"><span class="calendar-day-number">${number(Number(day.slice(8)))}</span>${rows.length ? `<span class="calendar-day-count" aria-hidden="true">${number(rows.length)}</span>` : ''}<span class="calendar-day-events" aria-hidden="true">${rows.slice(0,2).map(event=>`<span class="calendar-event-chip" title="${esc(event.title)}">${esc(event.title)}</span>`).join('')}${rows.length > 2 ? `<span class="calendar-extra">${c('more',{count:number(rows.length-2)})}</span>` : ''}</span></button>`;
  }).join('')}</div>${monthEvents.length ? '' : `<p class="calendar-month-empty" role="status">${c('emptyMonth')}</p>`}</div><section class="calendar-agenda" aria-label="${esc(dayLabel)}"><header><h3>${esc(dayLabel)}</h3><span class="calendar-agenda-count">${c('eventCount',{count:number(selectedEvents.length)})}</span></header><div class="calendar-agenda-events" aria-live="polite">${selectedEvents.length ? selectedEvents.map(eventCard).join('') : `<p class="calendar-day-empty">${c('emptyDay')}</p>`}</div></section></div>`;
}
export function calendarView(catalog, state = {}) {
  return `<section class="observatory-calendar" data-calendar>${calendarBody(catalog,normalizeCalendarState(state))}</section>`;
}
export function bindCalendar(root, {catalog,state = {},onStateChange = () => {}} = {}) {
  const calendar = root.querySelector('[data-calendar]');
  if (!calendar || !catalog) return () => {};
  let selected = normalizeCalendarState(state);
  function redraw(next, focusSelector) {
    selected = normalizeCalendarState(next);
    calendar.innerHTML = calendarBody(catalog,selected);
    onStateChange({...selected});
    if (focusSelector) calendar.querySelector(focusSelector)?.focus({preventScroll:true});
  }
  function moveMonth(amount, selector) {
    const base = new Date(selected.month+'-01T12:00:00Z');
    base.setUTCMonth(base.getUTCMonth()+amount);
    const month = base.toISOString().slice(0,7);
    if (month < '1900-01' || month > '2199-12') return;
    const end = new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth()+1,0,12)).getUTCDate();
    redraw({...selected,month,day:month+'-'+String(Math.min(Number(selected.day.slice(8)),end)).padStart(2,'0')},selector);
  }
  function click(event) {
    const button = event.target.closest('button');
    if (!button || !calendar.contains(button)) return;
    if (button.dataset.calendarDay) redraw({...selected,month:button.dataset.calendarDay.slice(0,7),day:button.dataset.calendarDay},`[data-calendar-day="${button.dataset.calendarDay}"]`);
    else if (button.hasAttribute('data-calendar-move')) moveMonth(Number(button.dataset.calendarMove),`[data-calendar-move="${button.dataset.calendarMove}"]`);
    else if (button.hasAttribute('data-calendar-today')) {
      const day = civilFromInstant(Date.now());
      redraw({...selected,month:day.slice(0,7),day},'[data-calendar-today]');
    }
  }
  function change(event) {
    if (event.target.hasAttribute('data-calendar-country')) redraw({...selected,calendarCountry:event.target.value},'[data-calendar-country]');
    if (event.target.hasAttribute('data-calendar-year')) {
      const year = Number(event.target.value);
      if (Number.isInteger(year) && year >= 1900 && year <= 2199) {
        const month = String(year)+'-'+selected.month.slice(5);
        redraw({...selected,month,day:month+'-01'},'[data-calendar-year]');
      } else event.target.value = selected.month.slice(0,4);
    }
    if (event.target.hasAttribute('data-calendar-month')) {
      const value = event.target.value;
      if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value) && value >= '1900-01' && value <= '2199-12') redraw({...selected,month:value,day:value+'-01'},'[data-calendar-month]');
    }
  }
  function keydown(event) {
    const button = event.target.closest('[data-calendar-day]');
    if (!button) return;
    const delta = {ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[event.key];
    if (delta) {
      event.preventDefault();
      const day = shiftCivilDay(button.dataset.calendarDay,delta);
      if (day.slice(0,7) < '1900-01' || day.slice(0,7) > '2199-12') return;
      redraw({...selected,month:day.slice(0,7),day},`[data-calendar-day="${day}"]`);
    } else if (event.key === 'PageUp' || event.key === 'PageDown') {
      event.preventDefault();moveMonth(event.key === 'PageUp' ? -1 : 1);
      calendar.querySelector('[data-calendar-day][aria-pressed="true"]')?.focus({preventScroll:true});
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      const weekday = new Date(button.dataset.calendarDay+'T12:00:00Z').getUTCDay();
      const day = shiftCivilDay(button.dataset.calendarDay,event.key === 'Home' ? -weekday : 6-weekday);
      if (day < '1900-01-01' || day > '2199-12-31') return;
      redraw({...selected,month:day.slice(0,7),day},`[data-calendar-day="${day}"]`);
    }
  }
  calendar.addEventListener('click',click);calendar.addEventListener('change',change);calendar.addEventListener('keydown',keydown);
  return () => {calendar.removeEventListener('click',click);calendar.removeEventListener('change',change);calendar.removeEventListener('keydown',keydown);};
}
