import logging

from box import Box
from django.db.models import Case, When

logger = logging.getLogger(__name__)


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


from collections import defaultdict


def group_notes(notes_queryset):
    """
    Group a queryset of Note objects by their variable_name.

    For each unique variable_name, returns:
    - A key with the variable name mapped to the latest Note (by timestamp).
    - A key with the suffix '__all' mapped to a list of all Notes with that variable name.

    Args:
        notes_queryset (QuerySet): A Django queryset of Note objects.

    Returns:
        dict: A dictionary with keys:
            - '<variable_name>': the most recent Note with that variable name.
            - '<variable_name>__all': a list of all Notes with that variable name.
    """
    latest_notes = {}
    all_notes = defaultdict(list)

    for note in notes_queryset:
        var_name = note.variable_name()
        all_notes[var_name].append(note and note.data or None)

        # Keep only the latest note (timestamp ordering assumed from Meta)
        if var_name not in latest_notes or note.timestamp > latest_notes[var_name].timestamp:
            latest_notes[var_name] = note and note.data or None

    # Combine into the final dict with both keys
    grouped = {}
    for var_name, note_list in all_notes.items():
        grouped[var_name] = latest_notes[var_name]
        grouped[f"{var_name}__all"] = note_list

    return grouped


def make_data_variable(notes):
    """This makes the `data` context variable, used in the prompt template.

    The layout/structure of this object is important because end-users will access it in templates and it needs to be consistent/predictable and provide good defaults.
    """

    dd = group_notes(notes)
    return Box(dd, default_box=True)


def hsv_to_rgb(h, s, v):
    """Convert HSV color space to RGB.
    h: Hue angle in degrees [0,360)
    s: Saturation [0,1]
    v: Value [0,1]
    Returns (r, g, b) as integers in the range 0-255.
    """
    h = float(h)
    s = float(s)
    v = float(v)
    h60 = h / 60.0
    h60f = int(h60)
    f = h60 - h60f
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    if h60f % 6 == 0:
        r, g, b = v, t, p
    elif h60f == 1:
        r, g, b = q, v, p
    elif h60f == 2:
        r, g, b = p, v, t
    elif h60f == 3:
        r, g, b = p, q, v
    elif h60f == 4:
        r, g, b = t, p, v
    elif h60f == 5:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def generate_color_palette(n, saturation=0.85, value=0.95):
    """
    Generate a list of n hex color codes using the golden ratio to vary hue.
    Lower saturation yields a pastel, more muted look.
    """
    colors = []
    golden_ratio_conjugate = 0.61803398875
    h = 0.0  # Start hue as fraction [0,1]
    for _ in range(n):
        h = (h + golden_ratio_conjugate) % 1.0
        hue_deg = h * 360.0
        r, g, b = hsv_to_rgb(hue_deg, saturation, value)
        hex_color = "#{:02X}{:02X}{:02X}".format(r, g, b)
        colors.append(hex_color)
    return colors
