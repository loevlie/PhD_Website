"""E2E: per-render editor-instance locking across two tabs.

Two tabs of the SAME browser context (same session, same session
tab_token) open the editor on the same slug. Each GET mints a distinct
editor_instance token and the LAST GET owns the lock. Asserts:

  * tab B (opened last) holds the lock — typing autosaves cleanly,
    no lost-lock overlay
  * typing in tab A trips lock_lost on its autosave: the tab freezes
    (#lock-lost-overlay.open, #editor-body readOnly) and its text is
    rescued to localStorage['editor-draft-lostlock:<slug>']
  * 'Take back & keep editing' (#lock-lost-takeover) in A unfreezes it
  * typing in B afterwards freezes B (it lost the lock to A)

Run from the repo root:
    python3 scripts/e2e_lock_multitab.py
    PW_HEADED=1 python3 scripts/e2e_lock_multitab.py   # watch it
"""
import os
import signal
import subprocess
import sys
import time
import urllib.request


PORT = 8767
BASE = f'http://127.0.0.1:{PORT}'
HEADED = os.environ.get('PW_HEADED') == '1'
SLUG = 'e2e-locktab-seed'
LOST_KEY = f'editor-draft-lostlock:{SLUG}'


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
u, _ = U.objects.get_or_create(username='e2e-lock',
    defaults={'is_staff': True, 'is_superuser': True, 'email': 'x@x.com'})
u.is_staff = True; u.is_superuser = True
u.set_password('e2e-lock-pw'); u.save()
Post.objects.filter(slug='e2e-locktab-seed').delete()
Post.objects.create(
    slug='e2e-locktab-seed', title='Lock test', excerpt='x',
    body='Baseline body for the multi-tab lock test.\n',
    date=date.today(), author='E2E', draft=True,
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
Post.objects.filter(slug='e2e-locktab-seed').delete()
"""
    subprocess.run([sys.executable, '-c', code])


def type_in(page, text):
    """Simulate typing: append text + dispatch input (drives markDirty
    → 1.5s autosave debounce), exactly like e2e_save.py does."""
    page.evaluate(
        '([sel, t]) => {'
        ' const el = document.querySelector(sel);'
        ' el.focus();'
        ' el.setSelectionRange(el.value.length, el.value.length);'
        ' el.value = el.value + t;'
        ' el.dispatchEvent(new Event(\'input\', { bubbles: true }));'
        '}',
        ['#editor-body', text],
    )


def overlay_open(page):
    return page.evaluate(
        "() => document.getElementById('lock-lost-overlay').classList.contains('open')"
    )


def body_readonly(page):
    return page.evaluate("() => document.getElementById('editor-body').readOnly")


def open_editor(page):
    page.goto(f'{BASE}/blog/{SLUG}/edit/', wait_until='networkidle')
    page.locator('#editor-body').wait_for(state='attached', timeout=10_000)
    inst = page.locator('#editor-form input[name="editor_instance"]').input_value()
    if not inst:
        print('[!!] editor rendered without an editor_instance token')
        sys.exit(1)
    return inst


def run():
    seed()
    log = open('/tmp/e2e_lock_server.log', 'w')
    server = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'],
        stdout=log, stderr=subprocess.STDOUT, preexec_fn=os.setsid,
    )
    try:
        if not wait_for_server():
            print('server never came up'); return 1

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not HEADED)
            ctx = browser.new_context(viewport={'width': 1440, 'height': 900})

            # ── Login once; both tabs share the context's session ──
            page_a = ctx.new_page()
            page_a.goto(f'{BASE}/accounts/login/', wait_until='domcontentloaded')
            page_a.fill('input[name="username"]', 'e2e-lock')
            page_a.fill('input[name="password"]', 'e2e-lock-pw')
            page_a.locator('form').evaluate('f => f.submit()')
            page_a.wait_for_url('**/accounts/profile/', timeout=10_000)
            print('[ok] logged in')

            # ── Tab A opens the editor first ──
            inst_a = open_editor(page_a)
            print(f'[ok] tab A open, instance={inst_a[:6]}…')

            # ── Tab B opens the SAME editor (same session) — last GET
            #    owns the lock ──
            page_b = ctx.new_page()
            inst_b = open_editor(page_b)
            print(f'[ok] tab B open, instance={inst_b[:6]}…')
            if inst_a == inst_b:
                print('[!!] both tabs got the SAME editor_instance token')
                return 2

            # ── B types first: it holds the lock — autosave succeeds,
            #    no overlay ──
            type_in(page_b, '\nB owns the lock right now.\n')
            page_b.wait_for_selector('#save-status.is-saved', timeout=10_000)
            print(f'[ok] B autosaved (status={page_b.locator("#save-status").text_content()!r})')
            if overlay_open(page_b):
                print('[!!] B shows the lost-lock overlay while holding the lock')
                return 3
            print('[ok] B has no overlay')

            # ── A types: its autosave must come back lock_lost and the
            #    tab must freeze within ~5s ──
            type_in(page_a, '\nA typing into a lost lock.\n')
            page_a.wait_for_selector('#lock-lost-overlay.open', timeout=10_000)
            print('[ok] A froze: #lock-lost-overlay.open')
            if not body_readonly(page_a):
                print('[!!] A overlay open but #editor-body is not readOnly')
                return 4
            print('[ok] A #editor-body is readOnly')
            rescued = page_a.evaluate('(k) => localStorage.getItem(k)', LOST_KEY)
            if not rescued:
                print(f'[!!] localStorage[{LOST_KEY!r}] is empty after freeze')
                return 5
            print(f'[ok] A rescued draft to localStorage ({len(rescued)} bytes)')

            # ── Take back & keep editing in A: overlay closes,
            #    readOnly drops, autosave re-arms ──
            page_a.click('#lock-lost-takeover')
            page_a.wait_for_selector('#lock-lost-overlay.open', state='detached',
                                     timeout=10_000)
            print('[ok] A takeover: overlay closed')
            if body_readonly(page_a):
                print('[!!] A still readOnly after takeover')
                return 6
            print('[ok] A #editor-body editable again')

            # ── B types again: it lost the lock to A — must freeze ──
            type_in(page_b, '\nB types again after losing the lock.\n')
            page_b.wait_for_selector('#lock-lost-overlay.open', timeout=10_000)
            print('[ok] B froze after A took over')
            if not body_readonly(page_b):
                print('[!!] B overlay open but #editor-body is not readOnly')
                return 7
            print('[ok] B #editor-body is readOnly')

            print('\nALL ASSERTIONS PASSED ✓')
            browser.close()
            return 0
    finally:
        try:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        cleanup()


if __name__ == '__main__':
    sys.exit(run())
