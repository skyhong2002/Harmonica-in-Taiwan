import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { setLocale } from '../assets/i18n.js';
import { postDisplayText } from '../assets/utils.js';

test('only exact generated Instagram story labels translate; authored content stays original', () => {
  const {window} = new JSDOM('', {url: 'https://example.com'});
  Object.assign(globalThis, {window, document:window.document, location:window.location, localStorage:window.localStorage});
  const story = {isStory:true,platform:'instagram'};
  const expected = {en:'Instagram story @artist.name', 'zh-Hant':'Instagram 限時動態 @artist.name', ja:'Instagram ストーリー @artist.name', ko:'Instagram 스토리 @artist.name'};
  for (const [locale,label] of Object.entries(expected)) {
    setLocale(locale);
    assert.equal(postDisplayText(story,'Instagram story @artist.name'),label);
    assert.equal(postDisplayText(story,'Instagram story @artist.name: my concert'), 'Instagram story @artist.name: my concert');
    assert.equal(postDisplayText({...story,isStory:false},'Instagram story @artist.name'),'Instagram story @artist.name');
    assert.equal(postDisplayText(story,'原始貼文\nOriginal post'),'原始貼文\nOriginal post');
  }
  window.close();
});
