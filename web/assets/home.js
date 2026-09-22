import { getLocale } from './i18n.js';
import { link, esc, icon, timestamp } from './utils.js';
import { storiesView } from './stories.js';
import { timelineView } from './timeline.js';
import { googleCalendarView } from './google-calendar.js';
const labels = {
  en: { home: 'Home', stories: 'Stories from the past 24 hours', calendar: 'Harmonica event calendar', feed: 'Latest public posts', full: 'Open the full feed', events: 'Browse event list', subscriptions: 'Calendar subscriptions' },
  'zh-Hant': { home: '首頁', stories: '近 24 小時限動', calendar: '公開口琴活動行事曆', feed: '最新公開貼文', full: '開啟完整動態河道', events: '瀏覽活動清單', subscriptions: '訂閱行事曆' },
  ja: { home: 'ホーム', stories: '過去24時間のストーリー', calendar: 'ハーモニカイベントカレンダー', feed: '最新の公開投稿', full: '投稿フィードを開く', events: 'イベント一覧', subscriptions: 'カレンダーを購読' },
  ko: { home: '홈', stories: '최근 24시간 스토리', calendar: '하모니카 행사 달력', feed: '최신 공개 게시물', full: '전체 소식 피드 보기', events: '행사 목록 보기', subscriptions: '달력 구독' },
};
export function observatoryHome(catalog, state, following, limit = 24) {
  const w = labels[getLocale()] || labels.en;
  const params = new URLSearchParams({lang:getLocale()});
  for (const key of ['q','country','platform','type','kind','followed']) if (state[key]) params.set(key,state[key]===true?'1':state[key]);
  const updated = catalog.generatedAt ? `<span class="home-updated">${timestamp(catalog.generatedAt)}</span>` : '';
  return `<div class="observatory-home"><h1 class="sr-only">${esc(w.home)}</h1>
    <section class="home-stories home-band" aria-labelledby="home-stories-title"><div class="home-section-inner"><header class="home-section-heading"><h2 id="home-stories-title">${esc(w.stories)}</h2>${updated}</header>${storiesView(catalog)}</div></section>
    <section class="home-calendar home-band" aria-labelledby="home-calendar-title"><div class="home-section-inner"><header class="home-section-heading"><h2 id="home-calendar-title">${esc(w.calendar)}</h2><div>${link('/events/',esc(w.events),'text-link')}${link('/feeds/',esc(w.subscriptions),'text-link')}</div></header>${googleCalendarView(catalog)}</div></section>
    <section class="home-posts home-band" aria-labelledby="home-posts-title"><div class="home-section-inner"><header class="home-section-heading"><h2 id="home-posts-title">${esc(w.feed)}</h2>${link('/post/?'+params,esc(w.full)+icon('arrow'),'text-link')}</header>${timelineView(catalog,state,following,limit)}</div></section>
  </div>`;
}
