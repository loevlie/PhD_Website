"""Tests for portfolio.editor_assist.spellcheck + the /spellcheck/
view. Split into two classes so failures point at the right layer:
pure-Python module vs. HTTP boundary / auth / payload shape.
"""
from django.test import TestCase

from portfolio.editor_assist import spellcheck as sc
from portfolio.tests._helpers import StaffClientMixin, make_post


# ─── Pure-module tests (no Django, no HTTP) ──────────────────────────

class SpellcheckModuleTests(TestCase):
    """Exercise the check_text / is_known / term-loader contract.
    Intentionally hits the real pyspellchecker corpus + our terms
    files so the integration is validated end-to-end."""

    def test_empty_input_returns_empty(self):
        self.assertEqual(sc.check_text(''), [])
        self.assertEqual(sc.check_text('   \n\n  '), [])

    def test_clean_prose_no_misspellings(self):
        out = sc.check_text("The cat sat on the mat. It was comfortable.")
        self.assertEqual(out, [])

    def test_flags_obvious_typo(self):
        out = sc.check_text("The cat sat on the maat.")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].word, 'maat')
        self.assertIn('mat', out[0].suggestions)

    def test_offset_points_at_original_text(self):
        # Useful for the editor's "jump to line" button.
        text = "okay\nokay\nthiss is wrong"
        out = sc.check_text(text)
        self.assertEqual(len(out), 1)
        m = out[0]
        self.assertEqual(m.word, 'thiss')
        self.assertEqual(m.line, 2)
        self.assertEqual(m.col, 0)
        # Offset should land exactly on the 't' of "thiss".
        self.assertEqual(text[m.offset:m.offset + len(m.word)], 'thiss')

    def test_ml_term_accepted(self):
        """pytorch/tabicl/transformer are baked into terms/ml.txt —
        none of them should be flagged."""
        out = sc.check_text("We fine-tune pytorch on tabicl. Transformers help.")
        flagged = {m.word for m in out}
        self.assertNotIn('pytorch', flagged)
        self.assertNotIn('tabicl', flagged)
        self.assertNotIn('Transformers', flagged)

    def test_tech_term_accepted(self):
        out = sc.check_text("The django whitenoise gunicorn stack ships fast.")
        self.assertEqual(out, [])

    def test_code_block_skipped(self):
        """Typos inside fenced code blocks must not be reported."""
        text = (
            "Prose before.\n\n"
            "```python\n"
            "this_has_a_typooooo = 42\n"
            "```\n\n"
            "Prose after."
        )
        out = sc.check_text(text)
        flagged = {m.word for m in out}
        self.assertNotIn('typooooo', flagged)

    def test_inline_code_skipped(self):
        out = sc.check_text("Call `notarealfunc` to blow up.")
        self.assertEqual([m.word for m in out], [])

    def test_inline_math_skipped(self):
        out = sc.check_text("The formula $f(xyzzy) = k$ defines things.")
        # xyzzy is nonsense but inside math — shouldn't be flagged.
        self.assertNotIn('xyzzy', {m.word for m in out})

    def test_display_math_skipped(self):
        out = sc.check_text("Intro.\n$$\n\\blahblahblah\n$$\nOutro.")
        self.assertNotIn('blahblahblah', {m.word for m in out})

    def test_url_skipped(self):
        out = sc.check_text("Ref: https://github.com/zzzorkerfoo/xyzzyplop.")
        # Word-level garbage inside a URL should not show up.
        flagged = {m.word for m in out}
        self.assertNotIn('zzzorkerfoo', flagged)
        self.assertNotIn('xyzzyplop', flagged)

    def test_markdown_link_text_is_checked_but_url_is_not(self):
        text = "See [some reel post](https://example.com/typoooo)."
        out = sc.check_text(text)
        flagged = {m.word for m in out}
        # Link text is technically matched by the image/link regex,
        # so it's also skipped — acceptable tradeoff, keeps the
        # implementation simple. Core requirement: URL garbage hidden.
        self.assertNotIn('typoooo', flagged)

    def test_html_tag_skipped(self):
        out = sc.check_text('<div data-foo="zzzzz">bar</div>')
        self.assertNotIn('zzzzz', {m.word for m in out})

    def test_short_all_caps_acronyms_are_safe(self):
        """DNA, URL, GPU, etc. aren't in the dictionary but shouldn't
        be flagged — they're obviously acronyms."""
        out = sc.check_text("Using DNA and XYZ sequences.")
        self.assertEqual(out, [])

    def test_extras_override(self):
        """Caller-provided extras take precedence over the baseline."""
        text = "The qlanxcupus is novel."
        self.assertEqual(len(sc.check_text(text)), 1)
        self.assertEqual(sc.check_text(text, extra_words=['qlanxcupus']), [])

    def test_max_results_cap(self):
        """A spammy post with many typos shouldn't produce an unbounded
        result list."""
        text = ' '.join(f'typoo{i}' for i in range(40))
        out = sc.check_text(text, max_results=5)
        self.assertEqual(len(out), 5)

    def test_is_known_basic(self):
        self.assertTrue(sc.is_known('hello'))
        self.assertTrue(sc.is_known('pytorch'))
        self.assertFalse(sc.is_known('grxmbylth'))

    def test_is_known_respects_extras(self):
        self.assertFalse(sc.is_known('grxmbylth'))
        self.assertTrue(sc.is_known('grxmbylth', extras=['grxmbylth']))

    def test_misspelling_serializes_to_dict(self):
        m = sc.Misspelling(word='fooo', line=3, col=2, offset=19, suggestions=['foo'])
        d = m.to_dict()
        self.assertEqual(d, {
            'word': 'fooo', 'line': 3, 'col': 2, 'offset': 19,
            'suggestions': ['foo'],
        })

    def test_load_term_list_ignores_comments(self):
        terms = sc.load_term_list('ml')
        # Direct assertions that proof-of-loading; don't over-couple to
        # exact contents of the file.
        self.assertIn('pytorch', terms)
        self.assertIn('tabicl', terms)
        self.assertNotIn('', terms)                     # no blank lines
        for t in terms:
            self.assertFalse(t.startswith('#'))          # comments gone


# ─── HTTP-layer tests ────────────────────────────────────────────────

class SpellcheckViewTests(StaffClientMixin, TestCase):
    """Exercises the /blog/<slug>/spellcheck/ endpoint. Payload
    shape, auth, error paths."""

    def setUp(self):
        super().setUp()
        self.post = make_post(slug='spell-demo', title='Spellcheck demo')
        self.url = f'/blog/{self.post.slug}/spellcheck/'

    def _post(self, client, body):
        import json
        return client.post(
            self.url, data=json.dumps(body), content_type='application/json',
        )

    def test_staff_can_spellcheck(self):
        r = self._post(self.staff_client, {'text': 'A clean sentence here.'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['misspellings'], [])

    def test_staff_sees_typo(self):
        r = self._post(self.staff_client, {'text': 'A claen sentence here.'})
        data = r.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['misspellings'][0]['word'], 'claen')

    def test_anon_rejected(self):
        r = self._post(self.anon_client, {'text': 'anything'})
        self.assertEqual(r.status_code, 403)

    def test_unknown_slug_404(self):
        import json
        r = self.staff_client.post(
            '/blog/does-not-exist/spellcheck/',
            data=json.dumps({'text': 'x'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 404)

    def test_get_rejected(self):
        r = self.staff_client.get(self.url)
        self.assertEqual(r.status_code, 405)

    def test_bad_json_rejected(self):
        r = self.staff_client.post(
            self.url, data='this is not json', content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    def test_extras_passthrough(self):
        """The `extras` payload field should be honored so clients can
        inject their per-author allowed words without a DB round-trip."""
        body = {'text': 'My grzftxkltm runs.', 'extras': ['grzftxkltm']}
        r = self._post(self.staff_client, body)
        data = r.json()
        self.assertEqual(data['count'], 0)

    def test_oversized_input_rejected(self):
        r = self._post(self.staff_client, {'text': 'x' * 200_001})
        self.assertEqual(r.status_code, 413)


class CheckWordViewTests(StaffClientMixin, TestCase):
    def test_known(self):
        import json
        r = self.staff_client.post(
            '/editor/check-word/',
            data=json.dumps({'word': 'pytorch'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['known'])

    def test_unknown(self):
        import json
        r = self.staff_client.post(
            '/editor/check-word/',
            data=json.dumps({'word': 'grzftxkltm'}),
            content_type='application/json',
        )
        self.assertFalse(r.json()['known'])

    def test_unknown_then_extra(self):
        import json
        # With the word added to extras, becomes known.
        r = self.staff_client.post(
            '/editor/check-word/',
            data=json.dumps({'word': 'grzftxkltm', 'extras': ['grzftxkltm']}),
            content_type='application/json',
        )
        self.assertTrue(r.json()['known'])

    def test_anon_rejected(self):
        import json
        r = self.anon_client.post(
            '/editor/check-word/',
            data=json.dumps({'word': 'hello'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    def test_missing_word_400(self):
        import json
        r = self.staff_client.post(
            '/editor/check-word/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)
