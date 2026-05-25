Autoplay Smoke Tests
====================

These Playwright tests exercise the dashboard autoplay flow in a lightweight, isolated manner by injecting a mock queue and API into the page. They do not require real authentication or modify production data.

Prerequisites
- Node.js (for Playwright test runner)
- Python available as `py -3` on Windows for the built-in test web server command

Install and run

```bash
# from workspace root
npm install
# then run tests
npm run test:autoplay
```

Notes
- Playwright will start the local web server automatically through `playwright.config.ts`.
- Tests inject `window.api` and `window.__mockQueue` into the page and call `app` methods directly.
- They capture page console logs to the test runner output for diagnostics.
