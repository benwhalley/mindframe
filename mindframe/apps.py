from django.apps import AppConfig


class MindFrameAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mindframe"

    def ready(self):
        import mindframe.checks
