"""Fold the primary author (site owner) into PostCollaborator so every
author — including the admin — shows up in the same ordering inline.

Steps:
1. For each Post, if no PostCollaborator row exists for the first
   superuser, create one at `post.author_order` (so existing intended
   ordering is preserved).
2. Populate that superuser's UserProfile with canonical defaults
   (display_name / bio / homepage) if the fields are blank, so
   the self-serve profile page shows "set up" and the byline can
   source his name + bio from the profile like every other author.
3. Drop `Post.author_order` — redundant now that the owner has a
   proper PostCollaborator row with its own `order` field.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Post = apps.get_model('portfolio', 'Post')
    PostCollaborator = apps.get_model('portfolio', 'PostCollaborator')
    UserProfile = apps.get_model('portfolio', 'UserProfile')
    User = apps.get_model('auth', 'User')

    owner = User.objects.filter(is_superuser=True).order_by('id').first()
    if owner is None:
        return

    for p in Post.objects.all():
        PostCollaborator.objects.get_or_create(
            post=p, user=owner,
            defaults={'order': getattr(p, 'author_order', 1) or 1},
        )

    profile, _ = UserProfile.objects.get_or_create(user=owner)
    changed = False
    if not profile.display_name:
        profile.display_name = 'Dennis Loevlie'
        changed = True
    if not profile.bio:
        profile.bio = 'ELLIS PhD Student at CWI & University of Amsterdam'
        changed = True
    if not profile.homepage_url:
        profile.homepage_url = '/'
        changed = True
    if changed:
        profile.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0019_post_authors_through'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
        migrations.RemoveField(
            model_name='post',
            name='author_order',
        ),
    ]
