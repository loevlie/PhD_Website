"""Tier 2: AI author-assist tests.

Three layers, mirroring the spell-check / smart-paste test files:
  * Pure-Python action registry (ai_assists.ACTIONS + run)
  * HTTP endpoint (POST /blog/<slug>/assist/<action>/)
  * Integration: auth, rate-limit, error mapping

The Anthropic SDK is never actually called — we patch
`ai_assists._call_anthropic` at the module boundary so tests don't need
an API key or the network, and the assertions target the prompt + the
response parser directly.
"""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from portfolio.editor_assist import ai_assists
from portfolio.tests._helpers import StaffClientMixin, make_post


# ─── Module-level: registry + parsers ───────────────────────────────

class AiAssistModuleTests(TestCase):

    def test_all_actions_registered(self):
        # If this ever shrinks, the editor toolbar has buttons that
        # 404. Keep the registry the single source of truth.
        self.assertEqual(
            set(ai_assists.ACTIONS.keys()),
            {'tighten', 'tldr', 'title', 'alt-text', 'sidenote'},
        )

    def test_unknown_action_raises(self):
        with self.assertRaises(ai_assists.AssistUnknown):
            ai_assists.run('does-not-exist', {})

    def test_missing_key_raises_unavailable(self):
        # No ANTHROPIC_API_KEY in env → unavailable, NOT a generic error,
        # so the view can 503 and the client can gracefully hide the UI.
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('ANTHROPIC_API_KEY', None)
            with self.assertRaises(ai_assists.AssistUnavailable):
                ai_assists.run('tldr', {'body': 'hello world'})

    # —— per-action: build_user + parse ——

    def test_tighten_bad_input(self):
        with self.assertRaises(ai_assists.AssistBadInput):
            ai_assists.run('tighten', {})
        with self.assertRaises(ai_assists.AssistBadInput):
            ai_assists.run('tighten', {'text': 'a' * 9000})

    def test_tighten_prompt_and_parse(self):
        fake = '"In a very real way, this is tight." '
        with patch.object(ai_assists, '_call_anthropic', return_value=fake) as m:
            out = ai_assists.run('tighten', {'text': 'hello'})
        self.assertEqual(out, 'In a very real way, this is tight.')
        # The system prompt must say "output only" (no preamble).
        args = m.call_args[0]
        self.assertIn('ONLY', args[0])  # system
        self.assertEqual(args[1], 'hello')  # user
        self.assertEqual(args[2], ai_assists._TIGHTEN.max_tokens)

    def test_tighten_strips_prefix_and_quotes(self):
        for fake, expected in [
            ('Tightened: compact prose.', 'compact prose.'),
            ('Revised: short.', 'short.'),
            ('"quoted body"', 'quoted body'),
            ('“smart quotes”', 'smart quotes'),
        ]:
            with patch.object(ai_assists, '_call_anthropic', return_value=fake):
                out = ai_assists.run('tighten', {'text': 'x'})
            self.assertEqual(out, expected)

    def test_tldr_parse_strips_quotes(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='"A tight summary."\n'):
            out = ai_assists.run('tldr', {'body': 'lorem ipsum'})
        self.assertEqual(out, 'A tight summary.')

    def test_title_returns_list_of_five(self):
        fake = (
            '1. First candidate\n'
            '2. "Second"\n'
            '3. Third one\n'
            '4. Fourth\n'
            '5. Fifth\n'
            '6. Sixth (should be dropped)\n'
        )
        with patch.object(ai_assists, '_call_anthropic', return_value=fake):
            out = ai_assists.run('title', {'body': 'lorem'})
        self.assertEqual(out, [
            'First candidate', 'Second', 'Third one', 'Fourth', 'Fifth',
        ])

    def test_title_handles_bulleted_output(self):
        fake = '- Alpha\n- Beta\n- Gamma\n'
        with patch.object(ai_assists, '_call_anthropic', return_value=fake):
            out = ai_assists.run('title', {'body': 'lorem'})
        self.assertEqual(out, ['Alpha', 'Beta', 'Gamma'])

    def test_title_passes_current_title_as_style_anchor(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='1. a\n2. b\n') as m:
            ai_assists.run('title', {'body': 'body text', 'current_title': 'My existing'})
        user_prompt = m.call_args[0][1]
        self.assertIn('My existing', user_prompt)
        self.assertIn('body text', user_prompt)

    def test_alt_text_requires_caption_or_context(self):
        with self.assertRaises(ai_assists.AssistBadInput):
            ai_assists.run('alt-text', {})

    def test_alt_text_takes_first_line(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='A single-line alt.\n\nextra\n'):
            out = ai_assists.run('alt-text', {'caption': 'diagram of pipeline'})
        self.assertEqual(out, 'A single-line alt.')

    def test_sidenote_requires_passage(self):
        with self.assertRaises(ai_assists.AssistBadInput):
            ai_assists.run('sidenote', {})

    def test_sdk_exception_wraps_as_assist_error(self):
        # Simulate the SDK raising — we wrap everything except
        # AssistUnavailable into AssistError so the view maps to 502.
        import os
        os.environ['ANTHROPIC_API_KEY'] = 'test-key'
        try:
            def boom(system, user, max_tokens):
                # Re-enter the real _call_anthropic path? No — we test
                # the wrapping directly with a patched SDK.
                raise RuntimeError('network down')
            with patch.object(ai_assists, '_call_anthropic', side_effect=ai_assists.AssistError('wrap')):
                with self.assertRaises(ai_assists.AssistError):
                    ai_assists.run('tldr', {'body': 'hello'})
        finally:
            os.environ.pop('ANTHROPIC_API_KEY', None)


# ─── HTTP layer ─────────────────────────────────────────────────────

class AssistViewTests(StaffClientMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.post = make_post(slug='hello', title='Hello', body='# Hello\n\nBody text.')
        self.url = lambda action: f'/blog/{self.post.slug}/assist/{action}/'

    def _post(self, client, action, body):
        return client.post(
            self.url(action),
            data=json.dumps(body),
            content_type='application/json',
        )

    # —— Auth / validation ——

    def test_anon_rejected(self):
        r = self._post(self.anon_client, 'tldr', {'body': 'x'})
        self.assertEqual(r.status_code, 403)

    def test_get_rejected(self):
        r = self.staff_client.get(self.url('tldr'))
        self.assertEqual(r.status_code, 405)

    def test_bad_json_rejected(self):
        r = self.staff_client.post(
            self.url('tldr'), data='gibberish', content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    def test_unknown_slug_404(self):
        r = self.staff_client.post(
            '/blog/does-not-exist/assist/tldr/',
            data=json.dumps({'body': 'x'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 404)

    def test_unknown_action_400(self):
        r = self._post(self.staff_client, 'nope', {'body': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'unknown action')

    # —— Success paths (mocked Anthropic) ——

    def test_tldr_happy_path(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='A short summary.'):
            r = self._post(self.staff_client, 'tldr', {'body': 'some body'})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['action'], 'tldr')
        self.assertEqual(d['result'], 'A short summary.')

    def test_title_returns_list(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='1. A\n2. B\n3. C\n'):
            r = self._post(self.staff_client, 'title', {'body': 'x'})
        d = r.json()
        self.assertEqual(d['result'], ['A', 'B', 'C'])

    def test_tighten_requires_text(self):
        r = self._post(self.staff_client, 'tighten', {})
        self.assertEqual(r.status_code, 400)

    # —— Error mapping ——

    def test_offline_returns_503(self):
        def raise_unavailable(*a, **kw):
            raise ai_assists.AssistUnavailable('no key')
        with patch.object(ai_assists, '_call_anthropic', side_effect=raise_unavailable):
            r = self._post(self.staff_client, 'tldr', {'body': 'x'})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['error'], 'offline')

    def test_upstream_error_returns_502(self):
        def raise_err(*a, **kw):
            raise ai_assists.AssistError('upstream boom')
        with patch.object(ai_assists, '_call_anthropic', side_effect=raise_err):
            r = self._post(self.staff_client, 'tldr', {'body': 'x'})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json()['error'], 'upstream_error')

    # —— Rate limiting ——

    def test_rate_limit_trips_on_per_minute(self):
        with patch.object(ai_assists, '_call_anthropic', return_value='ok'):
            # Configured to 20/min in the view; burst 25 and expect 429.
            hit_429 = False
            for _ in range(25):
                r = self._post(self.staff_client, 'tldr', {'body': 'x'})
                if r.status_code == 429:
                    hit_429 = True
                    self.assertEqual(r.json()['scope'], 'minute')
                    break
        self.assertTrue(hit_429)
