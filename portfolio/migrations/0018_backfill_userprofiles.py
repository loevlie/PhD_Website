"""Backfill a UserProfile for every existing auth.User so the signal-
created 1:1 invariant holds retroactively. The post_save signal
handles users created AFTER this migration runs."""
from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('portfolio', 'UserProfile')
    for u in User.objects.all():
        UserProfile.objects.get_or_create(user=u)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0017_userprofile"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
