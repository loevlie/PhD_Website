"""E2E: edit the body in the editor, click Save & view, assert the
live page reflects the edit.

Reproduces the user-reported bug: "after Save & view my edits are
missing from the live page" even though the preview shows them.
"""
import os
import signal
import subprocess
import sys
import time
import urllib.request
import uuid


PORT = 8766
BASE = f'http://127.0.0.1:{PORT}'
HEADED = os.environ.get('PW_HEADED') == '1'


def wait_for_server():
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'{BASE}/', timeout=1); return True
        except Exception:
            time.sleep(0.3)
    return False


def seed():
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from datetime import date
from django.contrib.auth import get_user_model
from portfolio.models import Post
U = get_user_model()
u, _ = U.objects.get_or_create(username='e2e-save',
    defaults={'is_staff': True, 'is_superuser': True, 'email': 'x@x.com'})
u.is_staff = True; u.is_superuser = True
u.set_password('e2e-save-pw'); u.save()
Post.objects.filter(slug='e2e-save-seed').delete()
Post.objects.create(
    slug='e2e-save-seed', title='Save test', excerpt='x',
    body='Baseline body content. Seventy words or so to be safe.\n',
    date=date.today(), author='E2E',
)
print('seeded')
"""
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    if r.returncode != 0:
        print('SEED FAILED:', r.stderr); sys.exit(1)


def cleanup():
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from portfolio.models import Post
Post.objects.filter(slug='e2e-save-seed').delete()
"""
    subprocess.run([sys.executable, '-c', code])


def run():
    seed()
    log = open('/tmp/e2e_save_server.log', 'w')
    server = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'],
        stdout=log, stderr=subprocess.STDOUT, preexec_fn=os.setsid,
    )
    try:
        if not wait_for_server():
            print('server never came up'); return 1

        from playwright.sync_api import sync_playwright
        marker = f'SAVE_MARKER_{uuid.uuid4().hex[:8].upper()}'

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not HEADED)
            ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
            page = ctx.new_page()

            page.goto(f'{BASE}/accounts/login/', wait_until='domcontentloaded')
            page.fill('input[name="username"]', 'e2e-save')
            page.fill('input[name="password"]', 'e2e-save-pw')
            page.locator('form').evaluate('f => f.submit()')
            page.wait_for_url('**/accounts/profile/', timeout=5_000)

            page.goto(f'{BASE}/blog/e2e-save-seed/edit/', wait_until='networkidle')
            ta = page.locator('textarea[name="body"]')
            ta.wait_for(state='attached', timeout=5_000)
            print(f'[ok] editor open')

            # Append a unique marker to the body so we can grep for it
            # on the live page after Save.
            page.evaluate(
                '([sel, marker]) => {'
                ' const el = document.querySelector(sel);'
                ' el.focus();'
                ' el.setSelectionRange(el.value.length, el.value.length);'
                ' el.value = el.value + "\\n\\n" + marker + "\\n";'
                ' el.dispatchEvent(new Event(\'input\', { bubbles: true }));'
                '}',
                ['textarea[name="body"]', marker],
            )
            # Wait for autosave to at least not be in-flight; it marks
            # status = 'saved'. (Not strictly required — Save POSTs
            # form directly — but makes the test deterministic.)
            time.sleep(1.0)

            # Click Save & view — goes through the same blog_edit POST
            # path as the red Save button, but redirects to the
            # blog_post page afterwards.
            save_view = page.locator('button[name="action"][value="view"]')
            save_view.click()
            page.wait_for_url(lambda url: '/blog/e2e-save-seed/' in url, timeout=8_000)
            print(f'[ok] redirected to live page: {page.url}')

            # Assertion: the marker must appear on the live page.
            html = page.content()
            if marker in html:
                print(f'[ok] marker {marker} visible on live page')
                print('SAVE PERSISTED ✓')
                return 0
            else:
                print(f'[!!] marker {marker} NOT FOUND on live page')
                print('\n----- first 2KB of live-page HTML -----')
                print(html[:2000])
                print('----- end slice -----\n')
                # Check if the marker is in the saved Post body via a
                # second Django shell call — that tells us whether the
                # issue is save-not-persisting vs render-cache.
                check = subprocess.run(
                    [sys.executable, '-c', (
                        "import os, django; "
                        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings'); "
                        "django.setup(); "
                        "from portfolio.models import Post; "
                        "p = Post.objects.get(slug='e2e-save-seed'); "
                        f"print('BODY_HAS_MARKER=' + str({marker!r} in p.body)); "
                        "print('RENDERED_HAS_MARKER=' + str(" f"{marker!r}" " in (p.rendered_html or ''))); "
                        "print('BODY_TAIL=' + repr(p.body[-200:]))"
                    )],
                    capture_output=True, text=True,
                )
                print(check.stdout)
                return 2
    finally:
        try:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        cleanup()


if __name__ == '__main__':
    sys.exit(run())
