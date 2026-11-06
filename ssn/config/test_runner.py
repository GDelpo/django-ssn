"""Test runner that makes a bare `manage.py test` work with this project's layout."""

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

# INTENTIONAL: apps/ is on sys.path, so path-based discovery imports the models a second
# time as apps.<app>.models and Django raises "Conflicting models". Labels avoid it.
PROJECT_APPS = ["accounts", "operaciones", "ssn_client", "theme"]


class ProjectTestRunner(DiscoverRunner):
    """Runs project apps by label and does not require collectstatic."""

    def build_suite(self, test_labels=None, **kwargs):
        return super().build_suite(test_labels or PROJECT_APPS, **kwargs)

    def setup_test_environment(self, **kwargs):
        # INTENTIONAL: the manifest storage fails on templates until collectstatic has run.
        self._static_override = override_settings(
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
            }
        )
        self._static_override.enable()
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        super().teardown_test_environment(**kwargs)
        self._static_override.disable()
