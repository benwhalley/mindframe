from django.db.models import Case, When
from box import Box


def get_ordered_queryset(model, pk_list):
    """
    Return a QuerySet of model instances ordered according to the provided pk_list.

    Args:
        model (django.db.models.Model): The model class to query.
        pk_list (list): List of primary key values in the desired order.

    Returns:
        django.db.models.QuerySet: The ordered QuerySet.
    """
    ordering = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(pk_list)])
    return model.objects.filter(pk__in=pk_list).order_by(ordering)


def make_data_variable(notes):
    """This makes the `data` context variable, used in the prompt template.

    The layout/structure of this object is important because end-users will access it in templates and it needs to be consistent/predictable and provide good defaults.
    """

    def getv(notes, v):
        notes = notes.filter(judgement__variable_name=v)
        r = {v: notes.last().data, v + "__all": notes}
        return Box(r, default_box=True)

    # get all notes for this session and flatten them so that we can access the latest
    # instance of each Judgement/Note by variable name
    vars = set(notes.values_list("judgement__variable_name", flat=True))
    dd = {}
    for i in vars:
        dd.update(getv(notes, i))
    return Box(dd, default_box=True)
