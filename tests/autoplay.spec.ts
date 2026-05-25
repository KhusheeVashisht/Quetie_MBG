import { expect, test } from '@playwright/test';

test.describe('Autoplay smoke tests', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => {
      console.log(`[page:${msg.type()}] ${msg.text()}`);
    });
    await page.goto('http://127.0.0.1:8000/');
    await page.waitForFunction(() => !!window['app'] && !!window['api']);
  });

  test('YouTube -> direct mp4 -> article -> unsupported queue flow stays consistent', async ({ page }) => {
    await page.evaluate(() => {
      window.__mockQueue = [
        { id: 101, url: 'https://youtu.be/dQw4w9WgXcQ', status: 'pending', clip_title: 'yt' },
        { id: 102, url: 'https://example.com/video.mp4', status: 'pending', clip_title: 'mp4' },
        { id: 103, url: 'https://example.com/article', status: 'pending', clip_title: 'article' },
        { id: 104, url: 'https://unsupported.example', status: 'pending', clip_title: 'unsupported' },
      ];

      window.__mockCalls = { markPlaying: 0, markCompleted: 0, detectContent: [] };

      window.api.detectContent = (url) => {
        const playable = /youtube|youtu|mp4|webm|ogg|mov|m4v/i.test(url);
        window.__mockCalls.detectContent.push({ url, playable });
        return Promise.resolve({ playable });
      };
      window.api.checkEmbed = () => Promise.resolve({ embeddable: true });
      window.api.markCompleted = (id) => {
        window.__mockCalls.markCompleted += 1;
        const entry = window.__mockQueue.find(x => x.id === id);
        if (entry) entry.status = 'completed';
        return Promise.resolve({ ok: true });
      };
      window.api.markPlaying = (id) => {
        window.__mockCalls.markPlaying += 1;
        window.__mockQueue.forEach(entry => {
          if (String(entry.status || '').toLowerCase() === 'playing') {
            entry.status = 'pending';
          }
        });
        const entry = window.__mockQueue.find(x => x.id === id);
        if (entry) entry.status = 'playing';
        return Promise.resolve({ ok: true });
      };
      window.api.getQueue = () =>
        Promise.resolve({
          entries: window.__mockQueue.filter(x => String(x.status || '').toLowerCase() === 'pending'),
        });
      window.api.getCurrentPlaying = () =>
        Promise.resolve({
          entry: window.__mockQueue.find(x => String(x.status || '').toLowerCase() === 'playing') || null,
        });
      window.api.getSettings = () => Promise.resolve({ settings: { autoplay_enabled: true } });

      window.app.autoplayEnabled = true;
      window.app.settings = { autoplay_enabled: true };
      window.app.loadDashboard = async function () {};
      window.app.showToast = function () {};
      window.app.loadQueue = async function () {
        this.allQueueEntries = window.__mockQueue.slice();
        const current = window.__mockQueue.find(x => String(x.status || '').toLowerCase() === 'playing') || null;
        this.renderCurrentPlaying(current);
      };
      window.app.playEntry = async function (id) {
        await window.api.markPlaying(id);
        await this.loadQueue();
      };
      window.__simulateEndForCurrent = () => {
        setTimeout(() => {
          if (window.app && typeof window.app.handleMediaEnded === 'function') {
            window.app.handleMediaEnded();
          }
        }, 50);
      };
    });

    await page.evaluate(() => window.app.playEntry(101));
    await page.evaluate(() => window.__simulateEndForCurrent());
    await page.waitForTimeout(350);

    const afterFirst = await page.evaluate(() => ({
      calls: window.__mockCalls,
      queue: window.__mockQueue.slice(),
      currentId: window.app.currentPlayingEntryId,
    }));
    expect(afterFirst.calls.markPlaying).toBeGreaterThanOrEqual(2);
    expect(afterFirst.queue.find(q => q.id === 101)?.status).toBe('completed');
    expect(afterFirst.queue.find(q => q.id === 102)?.status).toBe('playing');
    expect(afterFirst.currentId).toBe(102);

    await page.waitForTimeout(900);
    await page.evaluate(() => window.__simulateEndForCurrent());
    await page.waitForTimeout(350);

    const afterSecond = await page.evaluate(() => ({
      calls: window.__mockCalls,
      queue: window.__mockQueue.slice(),
    }));
    expect(afterSecond.queue.find(q => q.id === 102)?.status).toBe('completed');
    expect(afterSecond.queue.find(q => q.id === 103)?.status).toBe('pending');
    expect(afterSecond.queue.find(q => q.id === 104)?.status).toBe('pending');

    await page.evaluate(() => window.app.playEntry(103));
    await page.waitForTimeout(200);
    await page.evaluate(() => window.app.completeCurrentEntry(window.app.currentPlayingEntryId));
    await page.waitForTimeout(350);

    const afterManualSkip = await page.evaluate(() => ({
      calls: window.__mockCalls,
      queue: window.__mockQueue.slice(),
      currentId: window.app.currentPlayingEntryId,
    }));
    expect(afterManualSkip.calls.markCompleted).toBeGreaterThanOrEqual(3);
    expect(afterManualSkip.queue.find(q => q.id === 103)?.status).toBe('completed');
    expect(afterManualSkip.queue.find(q => q.id === 104)?.status).toBe('playing');
    expect(afterManualSkip.currentId).toBe(104);

    const diag = await page.evaluate(() => window.__getDiagnostics());
    expect(diag.counters.videos).toBeLessThanOrEqual(1);
    expect(diag.counters.iframes).toBeLessThanOrEqual(1);
    expect(diag.counters.eventAdd - diag.counters.eventRemove).toBeLessThanOrEqual(6);
  });

  test('rapid manual skip spam does not create duplicate advances', async ({ page }) => {
    await page.evaluate(() => {
      window.__mockQueue = [
        { id: 201, url: 'https://example.com/video.mp4', status: 'pending' },
        { id: 202, url: 'https://example.com/video2.mp4', status: 'pending' },
      ];
      window.__mockCalls = { markPlaying: 0, markCompleted: 0 };

      window.api.markCompleted = (id) => {
        window.__mockCalls.markCompleted += 1;
        const entry = window.__mockQueue.find(x => x.id === id);
        if (entry) entry.status = 'completed';
        return Promise.resolve({ ok: true });
      };
      window.api.markPlaying = (id) => {
        window.__mockCalls.markPlaying += 1;
        window.__mockQueue.forEach(entry => {
          if (String(entry.status || '').toLowerCase() === 'playing') {
            entry.status = 'pending';
          }
        });
        const entry = window.__mockQueue.find(x => x.id === id);
        if (entry) entry.status = 'playing';
        return Promise.resolve({ ok: true });
      };
      window.api.getQueue = () =>
        Promise.resolve({
          entries: window.__mockQueue.filter(x => String(x.status || '').toLowerCase() === 'pending'),
        });
      window.app.autoplayEnabled = true;
      window.app.settings = { autoplay_enabled: true };
      window.app.loadDashboard = async function () {};
      window.app.showToast = function () {};
      window.app.loadQueue = async function () {
        this.allQueueEntries = window.__mockQueue.slice();
        const current = window.__mockQueue.find(x => String(x.status || '').toLowerCase() === 'playing') || null;
        this.renderCurrentPlaying(current);
      };
      window.app.playEntry = async function (id) {
        await window.api.markPlaying(id);
        await this.loadQueue();
      };
    });

    await page.evaluate(() => window.app.playEntry(201));
    await page.evaluate(() => {
      for (let i = 0; i < 6; i += 1) {
        if (window.app && window.app.completeCurrentEntry) {
          window.app.completeCurrentEntry(window.app.currentPlayingEntryId);
        }
      }
    });
    await page.waitForTimeout(500);

    const state = await page.evaluate(() => ({
      calls: window.__mockCalls,
      queue: window.__mockQueue.slice(),
      currentId: window.app.currentPlayingEntryId,
    }));
    expect(state.calls.markCompleted).toBeGreaterThanOrEqual(1);
    expect(state.calls.markPlaying).toBeLessThanOrEqual(3);
    expect(state.queue.find(q => q.id === 202)?.status).toBe('playing');
    expect(state.currentId).toBe(202);

    const diag = await page.evaluate(() => window.__getDiagnostics());
    expect(diag.counters.videos).toBeLessThanOrEqual(1);
    expect(diag.counters.iframes).toBeLessThanOrEqual(1);
    expect(diag.counters.eventAdd - diag.counters.eventRemove).toBeLessThanOrEqual(6);
  });
});
