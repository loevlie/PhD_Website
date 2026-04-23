"""Switch Post.collaborators from an auto-generated M2M to a custom
`PostCollaborator` through model that carries a byline-position field.

Django 5 refuses to `AlterField` an M2M to add `through=`, so the dance
here is:

1. Add `Post.author_order` (byline slot for the primary author).
2. Create the `PostCollaborator` table.
3. Copy rows from the auto M2M table → PostCollaborator (preserves data).
4. `RemoveField` on `Post.collaborators` — drops the auto M2M table.
5. Re-`AddField` `Post.collaborators` as an M2M with `through=
   PostCollaborator` — state-only, since the PostCollaborator table
   already holds the data.
"""
from django.db import migrations, models
import django.db.models.deletion


def copy_existing_rows(apps, schema_editor):
    """Copy existing (post, user) pairs from the auto M2M table into
    PostCollaborator. Runs before the M2M is dropped."""
    Post = apps.get_model('portfolio', 'Post')
    PostCollaborator = apps.get_model('portfolio', 'PostCollaborator')
    for p in Post.objects.all():
        existing = list(p.collaborators.all().order_by('id'))
        for i, u in enumerate(existing, start=2):
            PostCollaborator.objects.get_or_create(
                post=p, user=u, defaults={'order': i},
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0018_backfill_userprofiles'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='author_order',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text=(
                    'Byline position for the primary author (post.author). '
                    '1 = first. Collaborators default to 2. Use 3/4/5… to demote Dennis.'
                ),
            ),
        ),
        migrations.CreateModel(
            name='PostCollaborator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(
                    default=2,
                    help_text=(
                        'Byline position. 1 = first author, 2 = second, 3 = third. '
                        'Primary author (post.author) defaults to 1.'
                    ),
                )),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='portfolio.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'verbose_name': 'Post collaborator',
                'verbose_name_plural': 'Post collaborators',
                'ordering': ['order', 'id'],
                'unique_together': {('post', 'user')},
            },
        ),
        migrations.RunPython(copy_existing_rows, noop_reverse),
        migrations.RemoveField(
            model_name='post',
            name='collaborators',
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='post',
                    name='collaborators',
                    field=models.ManyToManyField(
                        blank=True,
                        help_text='Non-staff users who can edit AND are auto-credited on this post.',
                        related_name='edit_posts',
                        through='portfolio.PostCollaborator',
                        to='auth.user',
                    ),
                ),
            ],
        ),
    ]
