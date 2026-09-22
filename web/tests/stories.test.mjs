import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { activeStories, storiesView, bindStories } from '../assets/stories.js';
import { setLocale } from '../assets/i18n.js';

const localeDocument = new JSDOM('', { url: 'https://example.org/' });
Object.defineProperty(globalThis, 'document', { value: localeDocument.window.document, configurable: true });
Object.defineProperty(globalThis, 'localStorage', { value: localeDocument.window.localStorage, configurable: true });

const story = { id: 'live', sourceId: 'source', sourceName: '原始 <b>名稱</b>', image: '/assets/story.webp', url: 'https://example.org/story', avatar: 'https://example.org/expired-avatar.jpg', expiresAt: '2099-01-01T00:00:00Z', publishedAt: '2026-09-23T00:00:00Z', storyState: 'active' };
const catalog = { sources: [{ id: 'source', avatar: '/assets/cached-avatar.webp' }], stories: [story] };

test('stories use only currently verifiable active records and preserve safe original media in four locales', () => {
  const data = { ...catalog, stories: [story,
    { ...story, id: 'expired', expiresAt: '2000-01-01' },
    { ...story, id: 'unknown', expiresAt: '' },
    { ...story, id: 'archived', storyState: 'archived' },
    { ...story, id: 'removed', sourceAvailable: false },
  ] };
  assert.deepEqual(activeStories(data).map(s => s.id), ['live']);
  for (const [locale, expiry] of [['en', 'Expires'], ['zh-Hant', '有效至'], ['ja', '公開期限'], ['ko', '만료']]) {
    setLocale(locale);
    const dom = new JSDOM(storiesView(data));
    const root = dom.window.document;
    assert.equal(root.querySelectorAll('.ob-story-card').length, 1);
    assert.equal(root.querySelector('.ob-story-image').getAttribute('src'), story.image);
    assert.equal(root.querySelector('.ob-story-avatar img').getAttribute('src'), '/assets/cached-avatar.webp');
    assert.equal(root.querySelector('.ob-story-original').getAttribute('href'), story.url);
    assert.equal(root.querySelector('.ob-story-identity strong').textContent, story.sourceName);
    assert.equal(root.querySelectorAll('b').length, 0);
    assert.ok(root.querySelector('.ob-story-footer').textContent.includes(expiry));
    assert.equal(root.querySelector('[role="progressbar"]'), null, 'decorative legacy rule makes no fake progress claim');
    dom.window.close();
  }
});

test('unsafe media and unknown sources remain honest; video playback requires user action', () => {
  setLocale('en');
  const dom = new JSDOM(storiesView({ stories: [
    { ...story, sourceId: '', sourceName: '', image: 'javascript:alert(1)', url: 'javascript:alert(1)' },
    { ...story, id: 'video', videoUrl: 'https://example.org/video.mp4' },
  ] }));
  const root = dom.window.document;
  assert.equal(root.querySelector('.ob-story-card').querySelector('a'), null);
  assert.equal(root.querySelector('.ob-story-card').querySelector('.ob-story-image'), null);
  assert.ok(root.querySelector('.ob-story-fallback').textContent.includes('unavailable'));
  const video = root.querySelector('video');
  assert.ok(video.hasAttribute('controls')); assert.ok(!video.hasAttribute('autoplay'));
  assert.equal(video.getAttribute('poster'), story.image);
  dom.window.close();
});

test('empty state describes retrieval status without claiming sources published nothing', () => {
  for (const [locale, message] of [['en', 'No active stories have been retrieved yet'], ['zh-Hant', '尚未取得有效限動'], ['ja', '有効なストーリーはまだ取得できていません'], ['ko', '아직 유효한 스토리를 가져오지 못했습니다']]) {
    setLocale(locale);
    assert.ok(storiesView({ stories: [] }).includes(message));
  }
});

test('expiry removes only expired cards, keeps live playback nodes, and preserves archive data', async () => {
  setLocale('en');
  const expires = { ...story, id: 'ending', expiresAt: new Date(Date.now() + 60).toISOString() };
  const data = { ...catalog, stories: [expires, story], posts: [expires] };
  const dom = new JSDOM(`<main>${storiesView(data)}</main>`, { pretendToBeVisual: true });
  const root = dom.window.document.querySelector('main');
  const kept = root.querySelector('[data-story-id="live"]');
  const cleanup = bindStories(root, { catalog: data });
  const strip = root.querySelector('.ob-story-strip');
  strip.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }));
  assert.ok(strip.scrollLeft > 0);
  await new Promise(resolve => setTimeout(resolve, 120));
  assert.equal(root.querySelector('[data-story-id="ending"]'), null);
  assert.equal(root.querySelector('[data-story-id="live"]'), kept);
  assert.equal(data.posts.length, 1); assert.equal(data.stories.length, 2);
  cleanup(); dom.window.close();
});
