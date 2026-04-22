"""Tier 3: authoring-aid embeds — notation glossary + reproducibility.

Both embeds are render-time, pure-Python, no network. We test them
through the full render_markdown pipeline so the dispatcher ordering,
markdown conversion, and HTML escaping are all exercised together.
"""
from django.test import TestCase

from portfolio.blog import render_markdown
from portfolio.blog.embeds import notation, reproducibility


# ─── Notation glossary ──────────────────────────────────────────────

class NotationParseTests(TestCase):
    """Direct unit tests on the parser — faster iteration than going
    through the whole markdown pipeline."""

    def test_colon_separator(self):
        out = notation._parse('theta: learnable params\nalpha: learning rate\n')
        self.assertEqual(out, [
            ('theta', 'learnable params'),
            ('alpha', 'learning rate'),
        ])

    def test_em_dash_separator(self):
        out = notation._parse('θ — the params\nα — step size\n')
        self.assertEqual(out, [('θ', 'the params'), ('α', 'step size')])

    def test_pipe_separator(self):
        out = notation._parse('L | loss function\n')
        self.assertEqual(out, [('L', 'loss function')])

    def test_hyphen_separator_requires_whitespace(self):
        # A hyphen inside a term must NOT split it.
        out = notation._parse('layer-norm: normalises per-token\n')
        self.assertEqual(out, [('layer-norm', 'normalises per-token')])

    def test_skips_malformed_lines(self):
        out = notation._parse(
            'good: ok\n'
            'no-separator-here\n'
            '\n'
            ': no term\n'
            'term only:\n'
            'another: fine\n'
        )
        self.assertEqual(out, [('good', 'ok'), ('another', 'fine')])

    def test_caps_at_30_entries(self):
        body = '\n'.join(f't{i}: d{i}' for i in range(100))
        out = notation._parse(body)
        self.assertEqual(len(out), 30)

    def test_drops_oversize_rows(self):
        body = 'ok: fine\nlong: ' + ('x' * 400) + '\n'
        out = notation._parse(body)
        self.assertEqual(out, [('ok', 'fine')])


class NotationRenderTests(TestCase):

    def test_renders_glossary_from_markdown(self):
        md = (
            '<div data-notation>\n'
            'θ: learnable parameters\n'
            'α: learning rate\n'
            'L: loss function\n'
            '</div>\n'
        )
        html, _ = render_markdown(md)
        self.assertIn('notation-glossary', html)
        self.assertIn('>Notation<', html)
        self.assertIn('learnable parameters', html)
        self.assertIn('learning rate', html)
        self.assertIn('loss function', html)

    def test_empty_body_drops_marker(self):
        # An empty glossary should NOT leave a stray <aside> in the
        # document — render nothing.
        md = '<div data-notation>\n\n</div>\n'
        html, _ = render_markdown(md)
        self.assertNotIn('notation-glossary', html)

    def test_preserves_math_spans_unescaped(self):
        # KaTeX runs client-side; the server-side job is just to mark
        # the math span so the client picks it up AND leave the raw
        # `$\theta$` text intact (escaping would produce `$\theta$`
        # inside &amp;/&lt; noise that KaTeX wouldn't render).
        md = '<div data-notation>\n$\\theta$: the parameters\n</div>\n'
        html, _ = render_markdown(md)
        self.assertIn('math-inline', html)
        self.assertIn(r'$\theta$', html)
        self.assertNotIn('&#36;', html)   # $ not HTML-entity-escaped

    def test_escapes_html_in_definitions(self):
        md = '<div data-notation>\nx: <script>alert(1)</script>\n</div>\n'
        html, _ = render_markdown(md)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)


# ─── Reproducibility card ───────────────────────────────────────────

class ReproParseTests(TestCase):

    def test_basic_pairs(self):
        out = reproducibility._parse(
            'python: 3.11\n'
            'commit: abc1234\n'
            'seed: 42\n'
        )
        self.assertEqual(out, {
            'python': '3.11',
            'commit': 'abc1234',
            'seed': '42',
        })

    def test_unknown_keys_kept(self):
        out = reproducibility._parse('framework: pytorch 2.3\n')
        self.assertEqual(out, {'framework': 'pytorch 2.3'})

    def test_duplicate_key_first_wins(self):
        out = reproducibility._parse('python: 3.11\npython: 3.12\n')
        self.assertEqual(out['python'], '3.11')

    def test_malformed_line_skipped(self):
        out = reproducibility._parse(
            'ok: fine\n'
            'this is not a key-value line\n'
            'also-ok: yes\n'
        )
        self.assertEqual(out, {'ok': 'fine', 'also-ok': 'yes'})

    def test_value_too_long_skipped(self):
        out = reproducibility._parse('command: ' + ('x' * 401) + '\n')
        self.assertEqual(out, {})

    def test_caps_at_20_keys(self):
        body = '\n'.join(f'k{i}: v{i}' for i in range(50))
        out = reproducibility._parse(body)
        self.assertEqual(len(out), 20)


class ReproRenderTests(TestCase):

    def test_renders_card_with_known_keys_ordered(self):
        md = (
            '<div data-repro>\n'
            'seed: 42\n'
            'python: 3.11\n'
            'command: python train.py\n'
            '</div>\n'
        )
        html, _ = render_markdown(md)
        self.assertIn('repro-card', html)
        self.assertIn('How to reproduce', html)
        # Display order follows _KNOWN_KEYS: python before seed before
        # command. So "Python" label appears before "Seed" label.
        py_idx = html.index('Python 3.11')
        seed_idx = html.index('>42<')
        cmd_idx = html.index('python train.py')
        self.assertLess(py_idx, seed_idx)
        self.assertLess(seed_idx, cmd_idx)

    def test_command_wraps_in_code(self):
        md = '<div data-repro>\ncommand: python train.py --lr 3e-4\n</div>\n'
        html, _ = render_markdown(md)
        self.assertIn('repro-command', html)
        self.assertIn('python train.py --lr 3e-4', html)

    def test_commit_links_when_repo_provided(self):
        md = (
            '<div data-repro>\n'
            'commit: abc1234def\n'
            'commit-repo: foo/bar\n'
            '</div>\n'
        )
        html, _ = render_markdown(md)
        self.assertIn('github.com/foo/bar/commit/abc1234def', html)
        # The aux key itself should NOT render as its own row.
        self.assertNotIn('>Commit Repo<', html)

    def test_commit_without_repo_is_code(self):
        md = '<div data-repro>\ncommit: abc1234\n</div>\n'
        html, _ = render_markdown(md)
        self.assertIn('repro-commit', html)
        self.assertNotIn('github.com', html)

    def test_empty_body_drops_marker(self):
        md = '<div data-repro>\n\n</div>\n'
        html, _ = render_markdown(md)
        self.assertNotIn('repro-card', html)

    def test_escapes_html_in_value(self):
        md = '<div data-repro>\nnotes: <img src=x onerror=1>\n</div>\n'
        html, _ = render_markdown(md)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;img', html)

    def test_injected_repo_slug_must_look_valid(self):
        # A hostile author supplying `commit-repo: javascript:alert(1)`
        # must NOT get an href injection.
        md = (
            '<div data-repro>\n'
            'commit: abc1234\n'
            'commit-repo: javascript:alert(1)\n'
            '</div>\n'
        )
        html, _ = render_markdown(md)
        self.assertNotIn('javascript:alert', html)
        # Falls back to the plain <code> form.
        self.assertIn('repro-commit', html)
