from django.db import connection
from django.test.utils import setup_databases


def enable_vector_extension():
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


# Custom test runner
from django.test.runner import DiscoverRunner


class VectorEnabledTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)
        enable_vector_extension()
        return old_config
