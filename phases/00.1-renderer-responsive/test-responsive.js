// Phase 0.1 — Renderer responsive test
// Verifies that the circuit map and panels render correctly at various container widths
// without distortion, overflow, or clipped labels.

import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HTML_PATH = path.resolve(__dirname, '../../dist/compare.html');

const TEST_WIDTHS = [320, 768, 1024, 1440, 2000];

test.describe('Phase 0.1 — Renderer responsive', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`file://${HTML_PATH}`);
  });

  for (const width of TEST_WIDTHS) {
    test(`renders correctly at ${width}px container width`, async ({ page }) => {
      // Set viewport to accommodate the test width
      await page.setViewportSize({ width: width + 100, height: 1200 });

      // Wait for the page to load
      await page.waitForSelector('#circuit-map-panel');

      // Get the circuit map panel and SVG
      const mapPanel = page.locator('#circuit-map-panel');
      const mapSvg = page.locator('#circuit-map-svg');

      // Wait for SVG to be rendered
      await mapSvg.waitFor({ state: 'visible' });

      // Get actual rendered dimensions
      const mapPanelBox = await mapPanel.boundingBox();
      const mapSvgBox = await mapSvg.boundingBox();

      // Map panel should fill container width (within 10% tolerance for margins)
      expect(mapPanelBox.width).toBeGreaterThanOrEqual(width * 0.9);
      expect(mapPanelBox.height).toBeGreaterThanOrEqual(420); // minimum height

      // SVG should fill the panel
      expect(mapSvgBox.width).toBeCloseTo(mapPanelBox.width, -1); // within 10px
      expect(mapSvgBox.height).toBeCloseTo(mapPanelBox.height, -1);

      // Check for overflow - SVG content should be visible
      const trackOutline = page.locator('#track-outline');
      await trackOutline.waitFor({ state: 'visible' });

      // Get the points attribute to verify track is rendered
      const points = await trackOutline.getAttribute('points');
      expect(points).toBeTruthy();
      expect(points.split(' ').length).toBeGreaterThan(10); // Should have multiple points

      // Take a screenshot for visual verification
      await expect(page).toHaveScreenshot(`responsive-${width}px.png`, {
        fullPage: false,
        maxDiffPixels: 100, // Allow minor anti-aliasing differences
      });
    });
  }

  test('panels render at different widths without horizontal overflow', async ({ page }) => {
    for (const width of TEST_WIDTHS) {
      await page.setViewportSize({ width: width + 100, height: 1200 });
      await page.goto(`file://${HTML_PATH}`);
      await page.waitForSelector('#panels');

      // Check that panels container doesn't overflow horizontally
      const panelsContainer = page.locator('#panels');
      const panelsBox = await panelsContainer.boundingBox();

      // Panels should fit within viewport width
      expect(panelsBox.width).toBeLessThanOrEqual(width + 1); // 1px tolerance
    }
  });
});
