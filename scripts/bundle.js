/**
 * Build pipeline for dist/compare.html — standalone single file that works via file://.
 *
 * Handles every state:
 * - Step 1 (monolith, no modules): Copies web/compare.html as-is
 * - Step 2+ (CSS extracted): Inlines web/css/styles.css into <style> block
 * - Step 3+ (JS modules extracted): Bundles relative imports via esbuild with external: ['https://*']
 * - Step 10+ (main.js entry point): Bundles web/js/main.js as the single script
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const WEB_DIR = path.join(ROOT, 'web');
const DIST_DIR = path.join(ROOT, 'dist');
const HTML_FILE = path.join(WEB_DIR, 'compare.html');
const CSS_FILE = path.join(WEB_DIR, 'css', 'styles.css');
const JS_DIR = path.join(WEB_DIR, 'js');
const MAIN_JS = path.join(JS_DIR, 'main.js');
const OUTPUT_FILE = path.join(DIST_DIR, 'compare.html');

// Ensure dist directory exists
fs.mkdirSync(DIST_DIR, { recursive: true });

// Read the source HTML
let html = fs.readFileSync(HTML_FILE, 'utf8');

// Step 2+: Inline CSS if the link tag exists and CSS file exists
const cssLinkPattern = /<link\s+rel="stylesheet"\s+href="css\/styles\.css"\s*>/i;
if (cssLinkPattern.test(html) && fs.existsSync(CSS_FILE)) {
  const cssContent = fs.readFileSync(CSS_FILE, 'utf8');
  html = html.replace(cssLinkPattern, `<style>\n${cssContent}\n</style>`);
  console.log('✓ Inlined CSS from web/css/styles.css');
}

// Step 3+: Bundle JS if main.js exists or if inline script has relative imports
const scriptSrcPattern = /<script\s+type="module"\s+src="js\/main\.js"\s*>/i;
const inlineScriptPattern = /<script\s+type="module">([\s\S]*?)<\/script>/i;

let needsBundling = false;
let jsSource = null;
let jsSourceType = null; // 'file' or 'inline'

if (fs.existsSync(MAIN_JS)) {
  needsBundling = true;
  jsSource = MAIN_JS;
  jsSourceType = 'file';
  console.log('✓ Found web/js/main.js — will bundle');
} else {
  // Check for inline script with relative imports
  const inlineMatch = html.match(inlineScriptPattern);
  if (inlineMatch) {
    const inlineScript = inlineMatch[1];
    if (/\s+from\s+['"]\.\/js\//.test(inlineScript)) {
      needsBundling = true;
      jsSourceType = 'inline';
      console.log('✓ Found inline script with relative imports — will bundle');
    }
  }
}

if (needsBundling) {
  let bundledJs;
  
  if (jsSourceType === 'file') {
    // Bundle main.js via esbuild
    bundledJs = execSync(
      `npx esbuild "${jsSource}" --bundle --format=esm --external:'https://*' --platform=browser`,
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 }
    );
    
    // Replace the script src tag with inline bundled JS
    html = html.replace(scriptSrcPattern, `<script type="module">\n${bundledJs}\n</script>`);
    console.log('✓ Bundled web/js/main.js with esbuild');
    
  } else if (jsSourceType === 'inline') {
    // Extract inline script to temp file, bundle, then replace
    const tempFile = path.join(DIST_DIR, '_temp_bundle.js');
    const inlineMatch = html.match(inlineScriptPattern);
    const inlineScript = inlineMatch[1];
    
    fs.writeFileSync(tempFile, inlineScript, 'utf8');
    
    bundledJs = execSync(
      `npx esbuild "${tempFile}" --bundle --format=esm --external:'https://*' --platform=browser`,
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 }
    );
    
    fs.unlinkSync(tempFile);
    
    html = html.replace(inlineScriptPattern, `<script type="module">\n${bundledJs}\n</script>`);
    console.log('✓ Bundled inline script with esbuild');
  }
}

// Remove module-load fallback <script> if present (added in Step 10)
const fallbackPattern = /<script>\s*\/\/ Fallback for module load failure[\s\S]*?<\/script>/i;
if (fallbackPattern.test(html)) {
  html = html.replace(fallbackPattern, '');
  console.log('✓ Removed module-load fallback script');
}

// Write the output
fs.writeFileSync(OUTPUT_FILE, html, 'utf8');

console.log(`✓ Wrote ${OUTPUT_FILE}`);
console.log('✓ Build complete');
