"""Hardcore tests for the editor's slash-command output.

The slash menu itself is client-side (can't unit-test without a
browser), but each command boils down to a specific markdown /
HTML fragment that must render to the expected blog-prose output. We
cover every insertion shape authored by the editor so regressions in
either the slash JS or the render pipeline surface here.
"""
import json
from unittest.mock import patch

from django.test import TestCase

from portfolio.blog import render_markdown
from portfolio.tests._helpers import StaffClientMixin, make_post


# The exact snippets the slash menu emits. Kept in sync with
# COMMANDS in portfolio/templates/portfolio/blog_edit.html.
SLASH_OUTPUTS = {
    'sidenote_tag': '[^note-1]',
    'sidenote_def': '[^note-1]: A sidenote.',
    'cite':         '<cite class="ref" data-key="harvey2025synthetic">[1]</cite>',
    'math_display': '\n$$\n\\theta\n$$\n',
    'math_inline':  'inline $\\theta$ done',
    'quote':        '\n> A quote\n>\n> — Author\n',
    'pullquote':    '\n<blockquote class="pullquote">A line worth pulling out.</blockquote>\n',
    'codeblock':    '\n```python\nprint("hi")\n```\n',
    'callout':      '\n<aside class="callout"><strong>Note:</strong> Heads-up.</aside>\n',
    'glossary':     '<span class="g" data-g="learnable parameters">$\\theta$</span>',
    'h2':           '\n## Heading\n\n',
    'h3':           '\n### Subheading\n\n',
    'table':        '\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n',
    'hr':           '\n\n---\n\n',
    'comment':      '<!-- internal note -->',
    'comment_hid':  '[//]: # (vanishes entirely)',
}


class SidenoteTests(TestCase):

    def test_sidenote_renders_as_footnote_on_standard_post(self):
        body = (
            'Before tag ' + SLASH_OUTPUTS['sidenote_tag'] + '. After tag.\n\n'
            + SLASH_OUTPUTS['sidenote_def'] + '\n'
        )
        html, _ = render_markdown(body, is_explainer=False)
        self.assertIn('footnote', html.lower())
        self.assertIn('A sidenote.', html)

    def test_sidenote_transforms_to_margin_note_on_explainer(self):
        body = (
            'Para one ' + SLASH_OUTPUTS['sidenote_tag'] + '.\n\n'
            + SLASH_OUTPUTS['sidenote_def'] + '\n'
        )
        html, _ = render_markdown(body, is_explainer=True)
        # Explainer posts transform footnotes into Tufte sidenotes.
        self.assertIn('sidenote', html)
        self.assertIn('A sidenote.', html)

    def test_paragraph_local_def_still_resolves(self):
        # The new /sidenote flow puts the definition one blank line
        # below the paragraph containing the tag; verify that still
        # parses correctly (it's valid markdown — the definition just
        # has to be at block level somewhere in the document).
        body = (
            'Reference ' + SLASH_OUTPUTS['sidenote_tag'] + ' in the middle.\n\n'
            + SLASH_OUTPUTS['sidenote_def'] + '\n\n'
            'Another paragraph further down.\n'
        )
        html, _ = render_markdown(body, is_explainer=False)
        self.assertIn('A sidenote.', html)
        self.assertIn('Another paragraph further down', html)

    def test_multiple_sidenotes_numbered_in_order(self):
        # nextNoteSlug() in the editor issues note-1, note-2, …
        # Verify two of them render as distinct footnotes.
        body = (
            'Alpha [^note-1] and beta [^note-2].\n\n'
            '[^note-1]: First.\n'
            '[^note-2]: Second.\n'
        )
        html, _ = render_markdown(body, is_explainer=False)
        self.assertIn('First.', html)
        self.assertIn('Second.', html)


class CitationSlashTests(TestCase):

    def test_cite_tag_survives_markdown(self):
        html, _ = render_markdown('See ' + SLASH_OUTPUTS['cite'] + ' for details.')
        self.assertIn('class="ref"', html)
        self.assertIn('data-key="harvey2025synthetic"', html)
        self.assertIn('[1]', html)

    def test_running_index_from_multiple_refs(self):
        # The editor assigns `[N]` based on running count of cite tags
        # in the post. We don't re-number server-side; verify both
        # hand-authored indices come through.
        body = (
            'First <cite class="ref" data-key="a">[1]</cite> and '
            'second <cite class="ref" data-key="b">[2]</cite>.'
        )
        html, _ = render_markdown(body)
        self.assertIn('[1]', html)
        self.assertIn('[2]', html)
        self.assertIn('data-key="a"', html)
        self.assertIn('data-key="b"', html)


class NotationSlashTests(TestCase):

    def test_span_g_survives_render(self):
        html, _ = render_markdown(
            'The param ' + SLASH_OUTPUTS['glossary'] + ' is learnable.'
        )
        self.assertIn('class="g"', html)
        self.assertIn('data-g="learnable parameters"', html)

    def test_notation_card_rendered_from_post_entries(self):
        # An empty <div data-notation></div> marker + a notation list
        # populates into a full glossary card at render time.
        notation = [
            {'term': '\\theta', 'definition': 'parameters of the model', 'kind': 'latex'},
            {'term': 'TabICL', 'definition': 'an in-context tabular model', 'kind': 'text'},
        ]
        body = 'Body prose before.\n\n<div data-notation></div>\n\nBody after.\n'
        html, _ = render_markdown(body, notation_entries=notation)
        self.assertIn('notation-glossary', html)
        # text-kind terms appear as-is; latex-kind terms get $…$ (KaTeX
        # picks them up via the math-inline placeholder).
        self.assertIn('TabICL', html)
        self.assertIn('math-inline', html)   # $\theta$ placeholder
        self.assertIn('parameters of the model', html)
        self.assertIn('in-context tabular model', html)

    def test_empty_marker_with_no_notation_leaves_stub(self):
        # No entries → the empty marker is left for the embed handler,
        # which renders nothing (tested elsewhere) rather than a
        # corrupted glossary.
        body = 'Before.\n\n<div data-notation></div>\n\nAfter.\n'
        html, _ = render_markdown(body, notation_entries=[])
        self.assertNotIn('notation-glossary', html)


class ScaffoldSnippetTests(TestCase):
    """Lightweight sanity — every scaffolded snippet renders without
    error and produces recognisable HTML."""

    def test_callout(self):
        html, _ = render_markdown(SLASH_OUTPUTS['callout'])
        self.assertIn('class="callout"', html)
        self.assertIn('Heads-up.', html)

    def test_pullquote(self):
        html, _ = render_markdown(SLASH_OUTPUTS['pullquote'])
        self.assertIn('class="pullquote"', html)

    def test_codeblock_pygments_highlights(self):
        html, _ = render_markdown(SLASH_OUTPUTS['codeblock'])
        self.assertIn('class="highlight"', html)

    def test_heading_levels(self):
        h2_html, _ = render_markdown(SLASH_OUTPUTS['h2'])
        h3_html, _ = render_markdown(SLASH_OUTPUTS['h3'])
        self.assertIn('<h2', h2_html)
        self.assertIn('<h3', h3_html)

    def test_table(self):
        html, _ = render_markdown(SLASH_OUTPUTS['table'])
        self.assertIn('<table>', html)
        self.assertIn('<th>a</th>', html)

    def test_hr(self):
        html, _ = render_markdown(SLASH_OUTPUTS['hr'])
        self.assertIn('<hr', html)

    def test_html_comment_hidden_in_markdown(self):
        # Both comment variants render nothing visible.
        html1, _ = render_markdown('Before\n' + SLASH_OUTPUTS['comment'] + '\nAfter')
        html2, _ = render_markdown('Before\n' + SLASH_OUTPUTS['comment_hid'] + '\nAfter')
        self.assertIn('Before', html1)
        self.assertIn('After', html1)
        self.assertIn('Before', html2)
        self.assertIn('After', html2)
        # The `[//]: #` form leaves nothing in the HTML.
        self.assertNotIn('vanishes entirely', html2)


class NotationAutosaveTests(StaffClientMixin, TestCase):
    """The editor serialises notation as a JSON string under
    `name="notation"`; `_apply_post_fields` parses + sanitises it."""

    def test_autosave_persists_notation_entries(self):
        post = make_post(slug='notation-save', body='# Hi')
        payload = [
            {'term': '\\theta', 'definition': 'params', 'kind': 'latex'},
            {'term': 'TabICL',  'definition': 'tabular in-context model', 'kind': 'text'},
        ]
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': post.title,
            'body': post.body,
            'notation': json.dumps(payload),
        })
        self.assertEqual(r.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(len(post.notation), 2)
        self.assertEqual(post.notation[0]['term'], '\\theta')
        self.assertEqual(post.notation[1]['kind'], 'text')

    def test_autosave_rejects_malformed_notation(self):
        post = make_post(slug='notation-bad', body='# Hi', title='Hi')
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': post.title,
            'body': post.body,
            'notation': 'not-json',
        })
        self.assertEqual(r.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.notation, [])

    def test_autosave_drops_blank_notation_rows(self):
        post = make_post(slug='notation-blanks', body='# Hi', title='Hi')
        payload = [
            {'term': '', 'definition': 'no term', 'kind': 'text'},          # blank term
            {'term': 'ok', 'definition': '', 'kind': 'text'},                # blank def
            {'term': 'good', 'definition': 'kept', 'kind': 'weird-kind'},    # bad kind → 'text'
        ]
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': post.title, 'body': post.body,
            'notation': json.dumps(payload),
        })
        post.refresh_from_db()
        self.assertEqual(len(post.notation), 1)
        self.assertEqual(post.notation[0]['term'], 'good')
        self.assertEqual(post.notation[0]['kind'], 'text')


class EditorDetailsDrawerTests(StaffClientMixin, TestCase):
    """The Details drawer renders each notation entry as a row; the
    hidden JSON is pre-populated so the client manager hydrates them."""

    def test_renders_notation_manager_section(self):
        post = make_post(slug='editor-render', body='# Body', title='T')
        post.notation = [{'term': '\\alpha', 'definition': 'step size', 'kind': 'latex'}]
        post.save()
        r = self.staff_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'fm-notation-list')
        # The hidden JSON carries the seeded entry as a raw string so
        # the client-side manager can hydrate rows on load.
        self.assertContains(r, '\\\\alpha')
        self.assertContains(r, 'step size')
