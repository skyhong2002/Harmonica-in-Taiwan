import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<html><body></body></html>', { url: 'https://harmonica.observe.tw/' });
globalThis.document = dom.window.document;
globalThis.localStorage = dom.window.localStorage;
const { setLocale } = await import('../assets/i18n.js');
const { sourceDetail, togglePostExpansion } = await import('../assets/views.js');
const source = { id: 's', name: 'Source original', countryCode: 'JP', url: '/source/s/', summary: 'Original biography', links: [] };
const original = 'Original long text <literal> & details\n'.repeat(12);
const posts = Array.from({ length: 27 }, (_, index) => ({
  id: `p${index}`, sourceId: 's', text: original + index,
  url: `https://example.org/post/${index}`, image: `https://example.org/media/${index}.jpg`,
  publishedAt: '2026-09-22T10:00:00Z', platform: 'instagram',
}));
const catalog = { sources: [source], posts: [...posts, { sourceId: 'other', text: 'Unrelated post' }], events: [] };

test('source update layout retains whole ordered cards, original content and existing actions', () => {
  setLocale('en');
  document.body.innerHTML = sourceDetail(source, catalog, new Set(['s']));
  const river = document.querySelector('.org-page > .source-updates-grid');
  assert.ok(river);
  const cards = [...river.querySelectorAll(':scope > .post-card')];
  assert.equal(cards.length, 24);
  assert.equal(document.querySelectorAll('.source-profile').length, 1);
  assert.equal(river.querySelector('.source-profile'), null);
  assert.equal(river.textContent.includes('Unrelated post'), false);
  cards.forEach((card, index) => {
    assert.equal(card.querySelector('.feed-text').textContent, original + index);
    assert.equal(card.querySelector('.feed-img').getAttribute('src'), posts[index].image);
    assert.equal(card.querySelector('[data-share]').dataset.share, posts[index].url);
    assert.equal(card.querySelector('[data-follow]').getAttribute('aria-pressed'), 'true');
    assert.equal(card.querySelector('.feed-original').getAttribute('href'), posts[index].url);
    assert.ok(card.querySelector('[data-report]') || card.querySelector('a[href*="/submit/"]'));
    assert.equal(card.querySelector('literal'), null);
  });
  const expand = cards[0].querySelector('[data-expand-post]');
  togglePostExpansion(expand);
  assert.equal(expand.getAttribute('aria-expanded'), 'true');
  assert.ok(cards[0].querySelector('.feed-text').classList.contains('is-expanded'));
  togglePostExpansion(expand);
  assert.equal(expand.getAttribute('aria-expanded'), 'false');
  assert.ok(document.querySelector('[data-action="more"]'));
  document.body.innerHTML = sourceDetail(source, catalog, new Set(), 48);
  assert.equal(document.querySelectorAll('.source-updates-grid > .post-card').length, 27);
  assert.equal(document.querySelector('[data-action="more"]'), null);
});

test('an empty source retains one empty state without fabricated cards', () => {
  document.body.innerHTML = sourceDetail(source, { sources: [source], posts: [] }, new Set());
  assert.equal(document.querySelectorAll('.source-updates-grid > .empty-state').length, 1);
  assert.equal(document.querySelector('.source-updates-grid > .post-card'), null);
});
