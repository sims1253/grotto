"""Capture the review pages with Playwright (an optional local review dependency).

Run with a Python that has playwright installed: python3 scripts/capture_studies.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/grotto-studies'
with sync_playwright() as p:
    shells = sorted((Path.home() / '.cache/ms-playwright').glob('chromium_headless_shell-*/*/chrome-headless-shell'))
    browser = p.chromium.launch(**({'executable_path': str(shells[-1])} if shells else {}))
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto((OUT / 'comparison.html').as_uri())
    for variant in ('day', 'night'):
        page.select_option('#variant', variant)
        for lang in ('typescript', 'python', 'r', 'json', 'css'):
            page.select_option('#language', lang)
            assert page.locator('article:not([hidden])').count() == 4
            page.evaluate('window.scrollTo(0, 0)')
            page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            if lang in ('typescript', 'r', 'json'):
                page.locator('main').screenshot(path=str(OUT / f'{variant}-{lang}.png'))
        page.select_option('#layout', 'pair')
        page.select_option('#left', 'pergola')
        for name in ('tansy', 'fig', 'rainstone', 'lantern'):
            page.select_option('#right', name)
            cards = page.locator('article:not([hidden])')
            assert cards.count() == 2
            assert all(card.get_attribute('data-variant') == variant for card in cards.all())
        page.select_option('#layout', 'all')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.keyboard.press('Tab')
    assert page.evaluate("document.activeElement.tagName !== 'BODY'")
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.goto((OUT / 'role-specimens.html').as_uri())
    for view in ('deutan', 'tritan'):
        page.select_option('#view', view)
        for variant in ('day', 'night'):
            page.locator(f'#{variant}-r').screenshot(path=str(OUT / f'{variant}-states-{view}.png'))
    assert not errors, errors
    browser.close()
print('All eight themes render in five languages; pair comparison, state simulations and mobile layout checked.')
