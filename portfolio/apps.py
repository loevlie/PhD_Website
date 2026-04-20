from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portfolio'

    def ready(self):
        # Wire up post-save / post-delete cache invalidation
        from portfolio import signals  # noqa: F401
