"""Capture and check the vivid comparison with a local Python Playwright install."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/vivid-studies'
with sync_playwright() as p:
    shells = sorted((Path.home() / '.cache/ms-playwright').glob('chromium_headless_shell-*/*/chrome-headless-shell'))
    browser = p.chromium.launch(**({'executable_path': str(shells[-1])} if shells else {}))
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto((OUT / 'comparison.html').as_uri())
    for variant in ('day', 'night'):
        for lang in ('typescript', 'python', 'r', 'json', 'css'):
            page.goto('about:blank')
            page.goto((OUT / 'comparison.html').as_uri())
            page.select_option('#variant', variant)
            page.select_option('#language', lang)
            assert page.locator('section:not([hidden]) article').count() == 6
            page.evaluate('window.scrollTo(0,0)')
            page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
            if lang in ('typescript', 'r', 'json'):
                page.locator('section:not([hidden])').screenshot(path=str(OUT / f'{variant}-{lang}.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    browser.close()
print('Vivid comparison: two variants, five languages, no JS errors or mobile overflow.')
