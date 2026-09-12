"""End-to-end ORB dashboard checks against a running server.

python3 web_app/tests/browser_smoke.py
Optional: ORB_BASE_URL / ORB_BROWSER_PATH (a Chromium executable).
Screenshots are scratch artifacts under .cache/orb-dashboard, not deliverables.
"""
from pathlib import Path
import json
import os
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
ARTIFACTS=ROOT/'.cache/orb-dashboard'
ARTIFACTS.mkdir(parents=True,exist_ok=True)
BASE=os.getenv('ORB_BASE_URL','http://127.0.0.1:8000')


def main():
    errors=[]
    with sync_playwright() as p:
        launch={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote']}
        if os.getenv('ORB_BROWSER_PATH'):
            launch['executable_path']=os.environ['ORB_BROWSER_PATH']
        browser=p.chromium.launch(**launch)
        context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
        page=context.new_page()
        page.set_default_timeout(10000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and '422' not in m.text else None)
        page.goto(BASE,wait_until='networkidle')
        expect(page.get_by_role('heading',name='Opening Range Breakout',exact=True)).to_be_visible()
        expect(page.locator('.stat-card').nth(1)).to_contain_text('10.37')
        expect(page.locator('.break-even-line')).to_contain_text('41.25%')
        assert page.evaluate('document.fonts.check("400 12px Inter")')
        page.locator('[data-chart=model]').hover()
        expect(page.locator('.chart-tooltip')).to_be_visible()
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'overview-desktop.png'),full_page=True)

        # Draft controls cannot silently rewrite a completed result.
        page.locator('.nav-link[data-route=lab]').click()
        expect(page.get_by_role('heading',name='Stress-test the possibilities')).to_be_visible()
        page.locator('#param-win_rate').evaluate('(el)=>{el.value=50;el.dispatchEvent(new Event("input",{bubbles:true}));}')
        expect(page.locator('#draft-status')).to_contain_text('Changed inputs')
        expect(page.locator('.lab-results .stat-card').nth(1)).to_contain_text('10.37')
        page.locator('#run-scenario').click()
        expect(page.locator('.lab-results .stat-card').nth(1)).to_contain_text('24.47')
        expect(page.locator('#draft-status')).to_contain_text('Results match')
        page.locator('#lab-preset').select_option('combined')
        page.locator('#run-scenario').click()
        expect(page.locator('.lab-results .stat-card').nth(1)).to_contain_text('17.23')
        expect(page.locator('.lab-results .stat-card').nth(2)).to_contain_text('27.60')
        page.locator('[data-action=heat-cell][data-p="45"][data-f="0.5"]').click()
        expect(page.locator('.lab-results .stat-card').nth(1)).to_contain_text('10.37')
        page.locator('[data-action=chart-mode][data-mode=drawdown]').click()
        expect(page.get_by_role('heading',name='Simulated drawdown paths')).to_be_visible()
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'lab-desktop.png'),full_page=True)
        page.locator('[data-action=chart-mode][data-mode=equity]').click()

        # Actual browser downloads contain the model's explicit provenance.
        page.locator('[data-action=export-menu]').click()
        with page.expect_download() as downloaded:
            page.locator('[data-action=export-json]').click()
        download=downloaded.value
        destination=ARTIFACTS/'export-test.json';download.save_as(str(destination))
        assert json.loads(destination.read_text())['evidence']=='ILLUSTRATIVE'
        page.locator('[data-action=export-menu]').click()
        with page.expect_download() as downloaded:
            page.locator('[data-action=export-csv]').click()
        downloaded.value.save_as(str(ARTIFACTS/'export-test.csv'))
        assert 'ILLUSTRATIVE' in (ARTIFACTS/'export-test.csv').read_text()
        page.locator('[data-action=export-menu]').click()

        page.locator('.nav-link[data-route=research]').click()
        expect(page.locator('.table-card tbody tr')).to_have_count(7)
        page.locator('[data-action=research-filter][data-id="2"]').click()
        expect(page.locator('.table-card tbody tr')).to_have_count(2)
        page.locator('.table-card [data-action=source][data-id="2"]').first.click()
        expect(page.locator('#detail-dialog')).to_be_visible()
        expect(page.locator('#detail-dialog')).to_contain_text('Opening-direction entry is not breakout-stop entry')
        page.locator('[data-action=close-dialog]').click()
        page.locator('#source-search').fill('Holmberg')
        expect(page.locator('.source-card')).to_have_count(1)
        page.locator('#source-search').fill('')
        page.locator('#timeframe-metric').select_option('mdd_pct')
        expect(page.locator('.timeframe-row').nth(2)).to_contain_text('35.0%')
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'research-desktop.png'),full_page=True)

        page.locator('.nav-link[data-route=strategy2]').click()
        expect(page.get_by_role('heading',name='Strategy 2 - Statistical Z-Score Mean Reversion',exact=True)).to_be_visible()
        expect(page.locator('.strategy2-status-grid')).to_contain_text('NOT RUN')
        expect(page.locator('.practitioner-table tbody tr')).to_have_count(8)
        expect(page.locator('.metric-registry tbody tr')).to_have_count(81)
        expect(page.locator('.strategy2-footer-note')).to_contain_text('Project-owned Strategy 2 results: none')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'strategy2-desktop.png'),full_page=True)

        page.locator('.search-trigger').click()
        page.locator('#glossary-search').fill('Sharpe')
        expect(page.locator('#glossary-items')).to_contain_text('Sharpe ratio')
        page.keyboard.press('Escape')
        page.locator('.sidebar [data-action=report]').click()
        expect(page.locator('#reader-chapter option')).to_have_count(49)
        page.locator('#reader-chapter').select_option('6')
        expect(page.locator('.prose')).to_contain_text('Break-even')
        page.locator('.prose img').wait_for()
        page.wait_for_function('document.querySelector(".prose img").naturalWidth > 0')
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'report-reader.png'))
        page.locator('[data-action=reader-next]').click()
        expect(page.locator('.prose')).to_contain_text('ORB-30R')
        page.locator('[data-action=close-dialog]').click()

        page.locator('.nav-link[data-route=trades]').click()
        expect(page.get_by_role('heading',name='What does your ORB actually return?')).to_be_visible()
        page.locator('[data-action=sample]').click()
        expect(page.locator('.stat-card').first).to_contain_text('1,030')
        expect(page.locator('.callout')).to_contain_text('Fictional sample')
        expect(page.locator('#ledger-table tbody tr')).to_have_count(6)
        page.locator('#trade-side').select_option('SHORT')
        expect(page.locator('#ledger-table tbody tr')).to_have_count(2)
        page.locator('#trade-side').select_option('all')
        page.locator('#trade-search').fill('MES')
        expect(page.locator('#ledger-table tbody tr')).to_have_count(1)
        page.locator('#trade-search').fill('')
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'trades-desktop.png'),full_page=True)
        page.locator('#trade-file').set_input_files({'name':'bad.csv','mimeType':'text/csv','buffer':b'a,b\n1,2'})
        expect(page.locator('#toasts')).to_contain_text('Missing columns')
        expect(page.locator('.stat-card').first).to_contain_text('1,030')

        page.locator('.nav-link[data-route=rules]').click()
        expect(page.locator('#sizing-result')).to_contain_text('14 MES')
        expect(page.locator('#sizing-result')).to_contain_text('$483.00')
        page.locator('#size-instrument').select_option('ES')
        expect(page.locator('#sizing-result')).to_contain_text('1 ES')
        page.locator('#size-budget').fill('20')
        page.locator('#sizing-form button[type=submit]').click()
        expect(page.locator('#sizing-result')).to_contain_text('Skip trade')
        page.locator('#session-date').fill('2026-12-08')
        page.locator('#session-date').dispatch_event('change')
        expect(page.locator('#session-plan')).to_contain_text('17:30')
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'rules-desktop.png'),full_page=True)

        # Store notes, reload them, and verify escaped user text. Clean up afterward.
        page.locator('.nav-link[data-route=journal]').click()
        title='Browser QA note — safe to remove'
        page.locator('#note-title').fill(title)
        page.locator('#note-body').fill('<img src=x onerror="window.__orb_xss=true"> Research note, not a trade.')
        page.locator('#note-category').select_option('Review')
        page.locator('#note-form button[type=submit]').click()
        expect(page.locator('.note-card').filter(has_text=title)).to_be_visible()
        assert page.evaluate('window.__orb_xss') is None
        page.reload(wait_until='networkidle')
        expect(page.locator('.note-card').filter(has_text=title)).to_be_visible()
        assert page.evaluate('window.__orb_xss') is None
        page.screenshot(animations='disabled',path=str(ARTIFACTS/'journal-desktop.png'),full_page=True)
        page.once('dialog',lambda dialog:dialog.accept())
        page.locator('.note-card').filter(has_text=title).locator('[data-action=delete-note]').click()
        expect(page.locator('.note-card').filter(has_text=title)).to_have_count(0)

        # Small-screen layouts, keyboard/menu behavior, and no body overflow.
        mobile=context.new_page()
        mobile.set_viewport_size({'width':390,'height':844})
        mobile.set_default_timeout(10000)
        mobile.on('pageerror',lambda e:errors.append(str(e)))
        mobile.goto(BASE,wait_until='networkidle')
        expect(mobile.get_by_role('heading',name='Opening Range Breakout',exact=True)).to_be_visible()
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mobile.screenshot(animations='disabled',path=str(ARTIFACTS/'overview-mobile.png'),full_page=True)
        mobile.locator('.mobile-menu').click()
        expect(mobile.locator('#sidebar')).to_have_class('sidebar open')
        mobile.locator('.nav-link[data-route=lab]').click()
        expect(mobile.get_by_role('heading',name='Stress-test the possibilities')).to_be_visible()
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mobile.screenshot(animations='disabled',path=str(ARTIFACTS/'lab-mobile.png'),full_page=True)
        for route in ['research','strategy2','trades','rules','journal']:
            mobile.goto(BASE+'/#'+route,wait_until='networkidle')
            mobile.wait_for_function('!document.querySelector(".loading-screen")')
            assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'),route
        assert not errors,errors
        browser.close()
    print('PASS: all six routes, scenario controls, charts, source/metric dialogs, report reader, exports, ledger, sizing, DST, journal persistence/XSS and mobile layouts.')


if __name__=='__main__':main()
