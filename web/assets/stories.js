import { t, getLocale, locales } from './i18n.js';
import { esc, safeUrl, image, link, initials, date } from './utils.js';

const words = {
  empty: ['No active stories have been retrieved yet', '尚未取得有效限動', '有効なストーリーはまだ取得できていません', '아직 유효한 스토리를 가져오지 못했습니다'],
  preview: ['Story preview', '限動預覽', 'ストーリープレビュー', '스토리 미리보기'],
  missing: ['Preview unavailable', '預覽目前無法載入', 'プレビューを読み込めません', '미리보기를 불러올 수 없습니다'],
  expires: ['Expires', '有效至', '公開期限', '만료'],
  browse: ['Browse stories', '瀏覽限時動態', 'ストーリーを見る', '스토리 탐색'],
};
const word = key => words[key][locales.indexOf(getLocale())] || words[key][0];

// Unknown or archived records belong in history, never in this live strip.
export function activeStories(catalog, now = Date.now()) {
  return (catalog.stories || []).filter(story => story.sourceAvailable !== false &&
    !['expired', 'unknown', 'archived'].includes(story.storyState) &&
    Number.isFinite(Date.parse(story.expiresAt)) && Date.parse(story.expiresAt) > now);
}

function storyCard(story, sources) {
  const source = sources.find(item => item.id === story.sourceId);
  const name = story.sourceName || source?.name || t('source');
  const label = `${name} · ${word('preview')}`;
  const video = safeUrl(story.videoUrl), poster = safeUrl(story.image);
  const picture = image(poster, 'ob-story-image', label);
  const media = video
    ? `<video class="ob-story-image" controls playsinline preload="none" ${poster ? `poster="${esc(poster)}"` : ''} aria-label="${esc(label)}"><source src="${esc(video)}"></video>`
    : link(story.url, picture, 'ob-story-media-link', `aria-label="${esc(name + ' · ' + t('original'))}"`);
  const published = Number.isFinite(Date.parse(story.publishedAt))
    ? `<time datetime="${esc(story.publishedAt)}">${esc(date(story.publishedAt, { year: undefined, hour: '2-digit', minute: '2-digit' }))}</time>` : '';
  // Prefer the catalog's cached avatar to an expiring social-CDN address.
  const avatar = image(source?.avatar || story.avatar, '', '');
  return `<article class="ob-story-card" data-story-id="${esc(story.id || story.url || '')}" data-story-expires="${esc(story.expiresAt)}"><div class="ob-story-thumb">${media}<span class="ob-story-fallback">${esc(word('missing'))}</span><span class="ob-story-rule" aria-hidden="true"></span><div class="ob-story-header"><span class="ob-story-avatar"><span aria-hidden="true">${esc(initials(name))}</span>${avatar}</span><div class="ob-story-identity"><strong title="${esc(name)}">${esc(name)}</strong>${published}</div></div><div class="ob-story-footer"><time datetime="${esc(story.expiresAt)}">${esc(word('expires'))} ${esc(date(story.expiresAt, { year: undefined, hour: '2-digit', minute: '2-digit' }))}</time>${link(story.url, esc(t('original')), 'ob-story-original')}</div></div></article>`;
}

export function storiesView(catalog) {
  const stories = activeStories(catalog);
  return `<section class="ob-stories" aria-label="${esc(t('stories'))}"><div class="ob-story-strip" tabindex="0" role="region" aria-label="${esc(word('browse'))}">${stories.length ? stories.map(story => storyCard(story, catalog.sources || [])).join('') : `<p class="ob-story-empty" role="status">${esc(word('empty'))}</p>`}</div></section>`;
}

export function bindStories(root, { catalog } = {}) {
  const strips = [...root.querySelectorAll('.ob-story-strip')];
  if (!catalog || !strips.length) return () => {};
  let timer;
  function expire() {
    let next = Infinity;
    for (const strip of strips) {
      for (const card of strip.querySelectorAll('[data-story-expires]')) {
        const expiry = Date.parse(card.dataset.storyExpires);
        if (expiry <= Date.now()) card.remove();
        else next = Math.min(next, expiry);
      }
      if (!strip.querySelector('.ob-story-card') && !strip.querySelector('.ob-story-empty')) {
        strip.innerHTML = `<p class="ob-story-empty" role="status">${esc(word('empty'))}</p>`;
      }
    }
    if (Number.isFinite(next)) timer = setTimeout(expire, Math.min(2147483647, Math.max(1, next - Date.now() + 10)));
  }
  function keydown(event) {
    if (!event.target.matches('.ob-story-strip') || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const strip = event.target;
    event.preventDefault();
    strip.scrollLeft += (event.key === 'ArrowRight' ? 1 : -1) * ((strip.querySelector('.ob-story-card')?.getBoundingClientRect().width || 180) + 12);
  }
  function mediaError(event) {
    if (event.target.matches('.ob-story-image')) event.target.closest('.ob-story-thumb')?.classList.add('ob-story-media-failed');
    if (event.target.matches('.ob-story-avatar img')) event.target.hidden = true;
  }
  root.addEventListener('keydown', keydown);
  root.addEventListener('error', mediaError, true);
  expire();
  return () => { clearTimeout(timer); root.removeEventListener('keydown', keydown); root.removeEventListener('error', mediaError, true); };
}
