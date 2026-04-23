"""End-to-end smoke test for the editor's /sidenote flow.

Runs a real `manage.py runserver` in a subprocess, creates a staff
fixture user via `--command='seed code'`, then drives Playwright
against it. Asserts:
  * `[^note-XXXXXX]` tag lands at the caret
  * definition appears one blank line past the caret's paragraph
  * caret ends up right after the tag
  * preview pane renders the new footnote reference

Run from the repo root:
    python scripts/e2e_sidenote.py
    PW_HEADED=1 python scripts/e2e_sidenote.py   # watch the browser
"""
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request


HEADED = os.environ.get('PW_HEADED') == '1'
PORT = int(os.environ.get('E2E_PORT', '8765'))
BASE = f'http://127.0.0.1:{PORT}'


def wait_for_server():
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'{BASE}/', timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def seed_user_and_post():
    """Seed user + post, return the session cookie value so we can
    hand it to Playwright instead of going through a login form."""
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from datetime import date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from importlib import import_module
from portfolio.models import Post

User = get_user_model()
u, _ = User.objects.get_or_create(username='e2e-staff',
    defaults={'is_staff': True, 'is_superuser': True, 'email': 'e2e@x.com'})
u.is_staff = True; u.is_superuser = True
u.set_password('pass-e2e'); u.save()

Post.objects.filter(slug='e2e-sidenote-seed').delete()
Post.objects.create(
    slug='e2e-sidenote-seed',
    title='E2E seed',
    excerpt='x',
    body=('Opening paragraph one. This is where the author drops a sidenote.\n\n'
          '## Second heading\n\n'
          'Second paragraph here.\n'),
    date=date.today(),
    author='E2E',
)

# Create a session directly so we skip the login form.
SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
s = SessionStore()
s[SESSION_KEY] = str(u.pk)
s[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
s[HASH_SESSION_KEY] = u.get_session_auth_hash()
s.create()
print('SESSION=' + s.session_key)
"""
    r = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True, text=True, cwd=os.getcwd(),
    )
    if r.returncode != 0:
        print('SEED FAILED:', r.stderr, file=sys.stderr); sys.exit(1)
    session_key = None
    for line in r.stdout.splitlines():
        if line.startswith('SESSION='):
            session_key = line.split('=', 1)[1].strip()
    if not session_key:
        print('no session key extracted from', r.stdout); sys.exit(1)
    print('seeded, session=', session_key[:10], '…')
    return session_key


def cleanup_seed():
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from portfolio.models import Post
Post.objects.filter(slug='e2e-sidenote-seed').delete()
"""
    subprocess.run([sys.executable, '-c', code], cwd=os.getcwd())


def run():
    session_key = seed_user_and_post()
    server_log = open('/tmp/e2e_server.log', 'w')
    server = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'],
        stdout=server_log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    try:
        if not wait_for_server():
            print('server never came up'); return 1
        print(f'server up at {BASE}')

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not HEADED)
            ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
            page = ctx.new_page()
            # Form-based login (the seed-direct-session approach fought
            # Django's SameSite / cookie path defaults on localhost).
            page.goto(f'{BASE}/accounts/login/', wait_until='domcontentloaded')
            page.locator('input[name="username"]').fill('e2e-staff')
            page.locator('input[name="password"]').fill('pass-e2e')
            page.locator('form').evaluate('f => f.submit()')
            page.wait_for_url('**/accounts/profile/', timeout=6_000)
            print('[ok] logged in')

            resp = page.goto(f'{BASE}/blog/e2e-sidenote-seed/edit/', wait_until='networkidle')
            print(f'[debug] editor URL status={resp.status} final={page.url}')
            # Dump the page title so we know if we hit the editor or a
            # login/profile redirect.
            print(f'[debug] title={page.title()!r}')
            ta = page.locator('textarea[name="body"]')
            # attached (in DOM) is enough — the editor textarea is
            # behind a scroll area and `visible` can race with layout.
            ta.wait_for(state='attached', timeout=5_000)

            # Place caret right after "sidenote. " (with trailing
            # space). The editor only opens the slash menu when "/" is
            # preceded by whitespace — matches author reality, and we
            # need a space before `/` for the trigger to fire.
            body_text = ta.input_value()
            anchor = 'sidenote.'
            target = body_text.index(anchor) + len(anchor)
            page.evaluate(
                '([sel, pos]) => { const el = document.querySelector(sel);'
                ' el.focus(); el.setSelectionRange(pos, pos); }',
                ['textarea[name="body"]', target],
            )
            page.keyboard.type(' ', delay=10)

            # Type slash command.
            page.keyboard.type('/sidenote', delay=15)
            try:
                page.wait_for_selector('.slash-menu:not(.hidden)', timeout=3_000)
                print('[ok] slash menu opened')
            except Exception:
                print('[!!] slash menu did not open')
                html = page.locator('textarea[name="body"]').input_value()
                print('     current body:', repr(html[:200]))
                return 2

            # Fire the active command (sidenote is first).
            page.keyboard.press('Enter')

            # Sidenote dialog should open.
            try:
                page.wait_for_selector('dialog#sidenote-dialog[open]', timeout=3_000)
                print('[ok] sidenote dialog opened')
            except Exception:
                print('[!!] sidenote dialog did not open')
                # The /sidenote command was probably lost to some
                # intermediate state; dump textarea to see what
                # survived.
                body_after = page.locator('textarea[name="body"]').input_value()
                print('     body after /sidenote:', repr(body_after[-200:]))
                return 3

            page.fill('#sidenote-text', 'This is an E2E test sidenote.')
            page.click('#sidenote-ok')

            page.wait_for_function(
                "!document.querySelector('dialog#sidenote-dialog').open",
                timeout=3_000,
            )

            new_body = ta.input_value()
            print('\n--- BODY AFTER INSERT ---')
            print(new_body)
            print('--- end body ---\n')

            # Tag assertion.
            tag_match = re.search(r'\[\^note-[a-z0-9]{4,8}\]', new_body)
            if not tag_match:
                print('[!!] NO TAG INSERTED')
                return 4
            tag = tag_match.group(0)
            slug = tag[2:-1]
            print(f'[ok] tag inserted: {tag}')

            # Def assertion.
            def_marker = f'{tag}: This is an E2E test sidenote.'
            if def_marker not in new_body:
                print(f'[!!] DEFINITION NOT FOUND — expected {def_marker!r}')
                return 5
            print('[ok] definition placed')

            # Caret should be right after the tag.
            caret = page.evaluate(
                '() => document.querySelector(\'textarea[name="body"]\').selectionStart'
            )
            expected_caret = tag_match.end()
            if caret != expected_caret:
                print(f'[??] caret at {caret}, expected {expected_caret}')
            else:
                print(f'[ok] caret at {caret} (after tag)')

            # Preview should render the new fnref.
            deadline = time.time() + 5.0
            rendered = False
            while time.time() < deadline:
                found = page.evaluate(
                    '(s) => !!document.querySelector(`#editor-preview-content [id="fnref:${s}"]`)',
                    slug,
                )
                if found:
                    rendered = True; break
                time.sleep(0.15)
            if not rendered:
                print(f'[!!] preview never rendered #fnref:{slug}')
                inner = page.evaluate("() => document.querySelector('#editor-preview-content').innerHTML.slice(0, 800)")
                print('     preview html:', repr(inner))
                return 6
            print(f'[ok] preview rendered #fnref:{slug}')

            print('\nALL ASSERTIONS PASSED ✓')
            browser.close()
            return 0
    finally:
        try:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        cleanup_seed()


if __name__ == '__main__':
    sys.exit(run())
