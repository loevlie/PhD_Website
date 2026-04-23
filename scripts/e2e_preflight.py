"""E2E preflight — one script that exercises the full collaborator
flow before inviting a co-author to a shared post.

Approach (why this shape):

- Playwright drives the browser for the JS-heavy parts a real
  collaborator touches (slash commands, dialogs, file uploads,
  popovers). Matches the pattern in scripts/e2e_sidenote.py.
- Subprocess-based Django seed for fixtures instead of the Django
  test runner: the editor's click-through lock is cache-backed, and
  swapping cache backends between a test process and the runserver
  process creates false-positive lock failures. Seeding via a
  sibling `python -c` against the same DATABASE_URL / CACHES config
  avoids that.
- No pyfig / matplotlib block exercised here. Pyfig forks a worker
  subprocess and adds ~20s of variance; we test it separately if
  needed. The flow that matters for collaborator onboarding is
  citation / cover / sidenote / notation / save / byline.
- One-shot: each run creates, exercises, asserts, and tears down
  its own fixtures. Safe to run against an empty dev DB; safe to
  rerun after a failure.

Run from the repo root:

    python scripts/e2e_preflight.py
    PW_HEADED=1 python scripts/e2e_preflight.py   # watch the browser
    KEEP_SEED=1 python scripts/e2e_preflight.py   # skip cleanup to inspect
"""
import os
import signal
import subprocess
import sys
import time
import urllib.request


HEADED = os.environ.get('PW_HEADED') == '1'
KEEP_SEED = os.environ.get('KEEP_SEED') == '1'
PORT = int(os.environ.get('E2E_PORT', '8766'))
BASE = f'http://127.0.0.1:{PORT}'

COLLEAGUE_USERNAME = 'e2e-colleague'
COLLEAGUE_PASSWORD = 'pass-e2e-colleague'
POST_SLUG = 'e2e-preflight-seed'
COVER_PATH = '/tmp/e2e_preflight_cover.png'


def wait_for_server():
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'{BASE}/', timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _run_django(code, tag):
    """Run a Django shell snippet in a subprocess. Fail loudly."""
    r = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True, text=True, cwd=os.getcwd(),
    )
    if r.returncode != 0:
        print(f'{tag} FAILED:\n{r.stderr}', file=sys.stderr)
        sys.exit(1)
    return r.stdout


def seed():
    """Create the admin + colleague + shared post. Idempotent."""
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from datetime import date
from django.contrib.auth import get_user_model
from portfolio.models import Post, PostCollaborator, UserProfile

User = get_user_model()

# Owner (simulates the site author Dennis). Reuse the existing
# superuser if one's already present — matches prod topology.
owner = User.objects.filter(is_superuser=True).order_by('id').first()
if owner is None:
    owner = User.objects.create_superuser('e2e-owner', 'e2e-owner@x', 'pass-owner')

# Colleague — the collaborator we invite. Non-staff.
colleague, _ = User.objects.get_or_create(
    username='""" + COLLEAGUE_USERNAME + r"""',
    defaults={'is_staff': False, 'is_superuser': False, 'email': 'colleague@x.com'},
)
colleague.is_staff = False
colleague.is_superuser = False
colleague.set_password('""" + COLLEAGUE_PASSWORD + r"""')
colleague.save()

# Colleague's self-serve profile — the byline needs to render their
# display name + bio.
prof, _ = UserProfile.objects.get_or_create(user=colleague)
prof.display_name = 'E2E Colleague'
prof.bio = 'Preflight stand-in for a co-author'
prof.save()

# Post body has a clean paragraph for slash-command insertion and a
# notation-card placeholder so the glossary embed fires.
Post.objects.filter(slug='""" + POST_SLUG + r"""').delete()
p = Post.objects.create(
    slug='""" + POST_SLUG + r"""',
    title='E2E preflight — OOD + UQ co-authoring',
    excerpt='Smoke check for the collaborator flow.',
    body=(
        'This is the opening paragraph where we exercise the /cite slash command. \n\n'
        'Second paragraph mentions the half-moon dataset and ends here. \n\n'
        '<div data-notation></div>\n'
    ),
    date=date.today(),
    author='Dennis Loevlie',
    draft=True,
    is_explainer=True,
)

# Byline ordering: Dennis first (order=1), colleague second (order=2).
# Owner is already auto-added by the post_save signal; set its order
# defensively in case the signal ran without our preferred slot.
PostCollaborator.objects.update_or_create(
    post=p, user=owner, defaults={'order': 1},
)
PostCollaborator.objects.update_or_create(
    post=p, user=colleague, defaults={'order': 2},
)
print('SEEDED slug=""" + POST_SLUG + r""" colleague=""" + COLLEAGUE_USERNAME + r"""')
"""
    out = _run_django(code, 'SEED')
    print(out.strip())


def cleanup():
    code = r"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_site.settings')
django.setup()
from django.contrib.auth import get_user_model
from portfolio.models import Post, Citation

User = get_user_model()
Post.objects.filter(slug='""" + POST_SLUG + r"""').delete()
User.objects.filter(username='""" + COLLEAGUE_USERNAME + r"""').delete()
Citation.objects.filter(key='preflight2026demo').delete()
print('CLEANED UP')
"""
    _run_django(code, 'CLEANUP')


def make_cover_png():
    """Generate a tiny but valid PNG so the cover-image upload has
    something to attach. 8x8 red square; < 100 bytes on disk."""
    # Minimal PNG bytes (truecolor+alpha, RLE) — hand-packed so we
    # don't need PIL in the test-runner path.
    import base64
    payload = (
        'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX/AAD///'
        '9BHTQRAAAADElEQVQI12NgIA8AAAAkAAGPbiedAAAAAElFTkSuQmCC'
    )
    with open(COVER_PATH, 'wb') as f:
        f.write(base64.b64decode(payload))
    return COVER_PATH


# Asserting helpers — print and return a step number on failure so
# the caller returns a non-zero exit code at the first failed check.

_step = 0
def ok(msg):
    print(f'  [ok] {msg}')

def fail(step_no, msg, extra=None):
    print(f'  [!!] STEP {step_no}: {msg}')
    if extra:
        print('       ', extra)
    return step_no


def run_browser():
    global _step
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()

        # ── Phase A — access the collaborator sees ─────────────────
        print('\n▶ Phase A — collaborator access')

        page.goto(f'{BASE}/accounts/login/', wait_until='domcontentloaded')
        page.locator('input[name="username"]').fill(COLLEAGUE_USERNAME)
        page.locator('input[name="password"]').fill(COLLEAGUE_PASSWORD)
        page.locator('form').evaluate('f => f.submit()')
        page.wait_for_url('**/accounts/profile/', timeout=6_000)
        ok('logged in as colleague')

        # Profile page should list the assigned post, with the
        # "collaborator · 1 post" role chip.
        _step += 1
        body_text = page.locator('body').inner_text()
        if 'E2E preflight' not in body_text:
            return fail(_step, 'profile page missing post title')
        if 'collaborator' not in body_text.lower():
            return fail(_step, 'profile page missing collaborator role chip')
        ok('profile shows assigned post + collaborator role')

        # Editor GET must succeed (not a 403).
        _step += 1
        resp = page.goto(f'{BASE}/blog/{POST_SLUG}/edit/', wait_until='networkidle')
        if resp.status != 200:
            return fail(_step, f'editor GET returned {resp.status}')
        # Gate on the textarea actually existing — if we hit the
        # lock-held screen, the editable body never renders.
        ta = page.locator('textarea[name="body"]')
        try:
            ta.wait_for(state='attached', timeout=4_000)
        except Exception:
            return fail(_step, 'editor textarea never attached — lock-held?',
                        page.title())
        ok('colleague can open the editor')

        # ── Phase B — citation via BibTeX paste ────────────────────
        print('\n▶ Phase B — citation (BibTeX paste)')

        _step += 1
        # Open /cite slash command at the end of the first paragraph.
        body_text = ta.input_value()
        target = body_text.index('/cite slash command.') + len('/cite slash command.')
        page.evaluate(
            '([sel, pos]) => { const el = document.querySelector(sel);'
            ' el.focus(); el.setSelectionRange(pos, pos); }',
            ['textarea[name="body"]', target],
        )
        page.keyboard.type(' /cite', delay=15)
        try:
            page.wait_for_selector('.slash-menu:not(.hidden)', timeout=3_000)
        except Exception:
            return fail(_step, 'slash menu did not open')
        page.keyboard.press('Enter')
        try:
            page.wait_for_selector('dialog#cite-dialog[open]', timeout=3_000)
        except Exception:
            return fail(_step, 'cite dialog did not open')
        ok('cite dialog opened')

        _step += 1
        # Expand the "+ Add new from BibTeX" disclosure, paste, submit.
        page.click('#cite-bibtex summary.cite-bibtex-head')
        bibtex = (
            '@article{preflight2026demo, '
            'author={Doe, Jane and Smith, John}, '
            'title={A Preflight Citation}, '
            'journal={J. Preflight}, year={2026}, '
            'url={https://example.com/preflight}}'
        )
        page.fill('#cite-bibtex-input', bibtex)
        page.click('#cite-bibtex-add')
        # The POST is async; status text updates when the server responds.
        try:
            page.wait_for_function(
                "() => /Added|Reused/.test("
                "document.getElementById('cite-bibtex-status').textContent)",
                timeout=4_000,
            )
        except Exception:
            status = page.evaluate("() => document.getElementById('cite-bibtex-status').textContent")
            return fail(_step, 'BibTeX create did not report success', status)
        ok('BibTeX parsed, Citation row created')

        _step += 1
        # The insert should have dropped a <cite> pill at the cursor.
        new_body = ta.input_value()
        if 'data-key="preflight2026demo"' not in new_body:
            return fail(_step, '<cite> pill not inserted in body', new_body[-200:])
        ok('cite pill inserted at cursor')

        # ── Phase C — notation entry + cover upload ────────────────
        print('\n▶ Phase C — notation + cover upload')

        _step += 1
        # Add a notation row with term "half-moon" + a definition.
        # The Details drawer is an always-visible <aside>, no summary
        # to click. Scroll the add button into view for Playwright.
        page.locator('#fm-notation-add').scroll_into_view_if_needed()
        page.click('#fm-notation-add')
        last_row = page.locator('.fm-notation-row').last
        last_row.locator('.fm-nt-term').fill('half-moon')
        last_row.locator('.fm-nt-def').fill(
            'a 2D toy dataset of two interleaved crescents, useful for OOD demos'
        )
        ok('notation entry added in the details drawer')

        _step += 1
        # Sidenote at END of paragraph 2 (slash menu triggers on
        # whitespace-before-slash). Re-focus the textarea first — we
        # just edited the notation drawer row so focus is elsewhere.
        ta.click()
        body_text = ta.input_value()
        anchor = 'ends here.'
        target = body_text.index(anchor) + len(anchor)
        page.evaluate(
            '([sel, pos]) => { const el = document.querySelector(sel);'
            ' el.focus(); el.setSelectionRange(pos, pos); }',
            ['textarea[name="body"]', target],
        )
        # Type space first, wait a frame, then the slash — some
        # keyup handlers in the editor test the char just BEFORE
        # the '/' literal, so a beat between keys helps the state
        # settle after the prior /cite flow.
        page.keyboard.type(' ', delay=20)
        page.wait_for_timeout(80)
        page.keyboard.press('/')
        try:
            page.wait_for_selector('.slash-menu:not(.hidden)', timeout=3_000)
        except Exception:
            menu_class = page.evaluate(
                "() => document.getElementById('slash-menu')?.className"
            )
            return fail(_step, 'sidenote slash menu did not open',
                        f'menu class: {menu_class}; body tail: ' + repr(ta.input_value()[-160:]))
        page.keyboard.type('sidenote', delay=15)
        page.keyboard.press('Enter')
        page.wait_for_selector('dialog#sidenote-dialog[open]', timeout=3_000)
        page.fill('#sidenote-text', 'OOD = out-of-distribution.')
        page.click('#sidenote-ok')
        page.wait_for_function(
            "!document.querySelector('dialog#sidenote-dialog').open",
            timeout=3_000,
        )
        ok('sidenote inserted')

        _step += 1
        # Attach a tiny PNG as the cover image.
        make_cover_png()
        page.set_input_files('input[name="cover_image"]', COVER_PATH)
        ok('cover image attached (will upload on Save)')

        # ── Phase D — Save, then view ───────────────────────────────
        print('\n▶ Phase D — save + view as reader')

        _step += 1
        # Sanity check: the notation hidden JSON input should be
        # populated before we submit. If it's empty the drawer's
        # input handler never ran and the server won't persist the
        # term — catching this here beats debugging from "not wrapped".
        notation_hidden = page.input_value('#fm-notation-json')
        if 'half-moon' not in notation_hidden:
            return fail(_step, 'notation hidden JSON missing half-moon',
                        repr(notation_hidden))
        ok(f'notation JSON populated: {notation_hidden}')

        _step += 1
        # The Save button submits the form with action=save.
        with page.expect_navigation(wait_until='domcontentloaded', timeout=10_000):
            page.click('button[value="save"]')
        ok('Save submitted')

        # Navigate to the public post page.
        _step += 1
        resp = page.goto(f'{BASE}/blog/{POST_SLUG}/', wait_until='domcontentloaded')
        if resp.status != 200:
            return fail(_step, f'public post page returned {resp.status}')
        ok('public post page renders')

        _step += 1
        page_text = page.locator('body').inner_text()
        if 'Dennis Loevlie' not in page_text:
            return fail(_step, 'byline missing the owner')
        if 'E2E Colleague' not in page_text:
            return fail(_step, 'byline missing the colleague')
        # Position: Dennis (order=1) should appear before colleague.
        if page_text.index('Dennis Loevlie') > page_text.index('E2E Colleague'):
            return fail(_step, 'byline order wrong — colleague before owner')
        ok('byline lists both authors in owner→colleague order')

        _step += 1
        pill = page.locator('cite.ref[data-key="preflight2026demo"], button.ref[data-key="preflight2026demo"]')
        if pill.count() == 0:
            return fail(_step, 'citation pill not rendered on the post')
        ok('citation pill is on the page')

        _step += 1
        # The popover-stays-open regression: hover the pill, wait
        # past the 250ms hide grace, check the popover is still
        # visible after we move into it.
        pill.first.hover()
        try:
            page.wait_for_selector('.cite-popover.is-visible', timeout=2_000)
        except Exception:
            return fail(_step, 'popover never appeared on hover')
        page.locator('.cite-popover.is-visible').first.hover()
        page.wait_for_timeout(500)   # past the 250ms hide timer
        if page.locator('.cite-popover.is-visible').count() == 0:
            return fail(_step, 'popover vanished before user could reach buttons')
        ok('popover survives the trigger→popover hover traverse')

        _step += 1
        # Sidenote should render as a span (not an <aside>) so the
        # surrounding paragraph is not broken in two by the browser.
        aside_count = page.locator('.blog-prose aside.sidenote').count()
        span_count = page.locator('.blog-prose span.sidenote').count()
        if aside_count > 0:
            return fail(_step, f'sidenote still rendered as <aside> ({aside_count} nodes)')
        if span_count == 0:
            return fail(_step, 'no sidenote <span> rendered at all')
        ok('sidenote renders as inline <span> (paragraph stays intact)')

        _step += 1
        # Notation auto-wrap: "half-moon" should appear somewhere in
        # the prose wrapped in an element with data-g="half-moon".
        # Don't assume `span` — math-glossary.js may upgrade spans to
        # buttons when the term is in the global manifest. Our term
        # isn't, so the span should stay, but the data-g attribute
        # is the stable marker across both paths.
        wrap = page.locator('[data-g="half-moon"]')
        if wrap.count() == 0:
            # Dump a snippet so the failure message is actionable.
            snippet = page.evaluate(
                "() => { const m = document.body.innerHTML.match(/half-moon[^<]{0,60}/); "
                "return m ? m[0] : 'no-match'; }"
            )
            return fail(_step, 'notation term was not auto-wrapped in the prose',
                        'snippet around half-moon: ' + repr(snippet))
        ok('notation term auto-wrapped in the rendered body')

        _step += 1
        # Cover image made it through the upload.
        img = page.locator('article img[src*="blog_covers/"], img[src*="blog_covers/"]').first
        if img.count() == 0:
            return fail(_step, 'cover image not rendered on post page')
        ok('cover image rendered')

        browser.close()
        print('\nALL ASSERTIONS PASSED ✓')
        return 0


def main():
    seed()
    server_log = open('/tmp/e2e_preflight_server.log', 'w')
    server = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'],
        stdout=server_log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    try:
        if not wait_for_server():
            print('server never came up; see /tmp/e2e_preflight_server.log')
            return 1
        print(f'server up at {BASE}\n')
        return run_browser()
    finally:
        try:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        if not KEEP_SEED:
            cleanup()
        else:
            print(f'\n[KEEP_SEED=1] fixtures kept — inspect at {BASE}/blog/{POST_SLUG}/')


if __name__ == '__main__':
    sys.exit(main())
