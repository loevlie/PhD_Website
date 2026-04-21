"""Seed /reading/ with five starter papers so prod has content on first
deploy. The owner can edit/delete/reorder via /admin/portfolio/reading/.
"""
from django.db import migrations


SEED = [
    # status, order, title, venue, year, url, annotation
    ('this_week', 10, 'muP: Maximal Update Parametrization', 'arXiv 2503.16302', 2025,
     'https://arxiv.org/abs/2503.16302',
     "Re-reading after Greg's tutorial; the trust-region intuition still does not feel right."),
    ('this_week', 20, 'Towards Monosemanticity', 'Anthropic', 2024,
     'https://arxiv.org/abs/2402.05749',
     'For the SAE work; section 4 is the only honest dictionary-size discussion in the literature.'),
    ('this_week', 30, 'Mixture-of-Depths', 'DeepMind', 2024,
     'https://arxiv.org/abs/2401.04081',
     'Unsure if it generalizes off the toy benchmark. Looking for a replication.'),
    ('chewing', 10, 'Attention Is All You Need', 'Vaswani et al.', 2017,
     'https://arxiv.org/abs/1706.03762',
     'Re-read every six months; spotted something new in the positional-encoding section last time.'),
    ('chewing', 20, 'Zoom In: An Introduction to Circuits', 'Distill', 2020,
     'https://distill.pub/2020/circuits/zoom-in/',
     'Still the cleanest framing for what mechanistic interpretability is trying to do.'),
]


def seed(apps, schema_editor):
    Reading = apps.get_model('portfolio', 'Reading')
    # Idempotent: only insert if the table is empty (admin edits survive).
    if Reading.objects.exists():
        return
    for status, order, title, venue, year, url, annotation in SEED:
        Reading.objects.create(
            status=status, order=order, title=title, venue=venue, year=year,
            url=url, annotation=annotation,
        )


def unseed(apps, schema_editor):
    # Best-effort un-seed: only remove rows whose title matches a seed entry
    # AND that haven't been edited since insert (no admin touches).
    Reading = apps.get_model('portfolio', 'Reading')
    titles = {row[2] for row in SEED}
    Reading.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('portfolio', '0009_reading_post_kind'),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
