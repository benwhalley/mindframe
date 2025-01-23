from mindframe.models import Cycle


def run():
    print(Cycle.objects.all().delete())
