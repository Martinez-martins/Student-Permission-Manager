from django.apps import AppConfig


class PermissionsConfig(AppConfig):
    name = 'permissions'

    def ready(self):
        import permissions.signals
