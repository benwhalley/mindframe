import random
from mindframe.models import CustomUser
from django.utils.text import slugify


# Define syllables that sound like American sports stars or Vegas show names
first_names = [
    "Thaddeus",
    "Augustus",
    "Percival",
    "Horatio",
    "Jasper",
    "Algernon",
    "Basil",
    "Cyrus",
    "Ezekiel",
    "Phineas",
    "Montague",
    "Silas",
]
last_name_prefixes = ["Whit", "Ash", "Haw", "Mor", "Cran", "Fair", "Thor", "Mar", "Beau", "Elder"]
last_name_suffixes = [
    "sworth",
    "field",
    "ington",
    "more",
    "dale",
    "well",
    "croft",
    "ridge",
    "ley",
    "brook",
]


def silly_name():
    # Combine a first name with a random last name prefix and suffix
    first_name = random.choice(first_names)
    last_name = random.choice(last_name_prefixes) + random.choice(last_name_suffixes)
    return f"{first_name} {last_name}"


def silly_user():
    sn = silly_name()
    f, l = sn.split(" ")
    return CustomUser.objects.create(
        username=f"{slugify(sn)}{random.randint(1e4, 1e5)}",
        first_name=f,
        last_name=l,
        is_active=False,
    )


if False:
    # Generate a list of names
    silly_names = [silly_name() for _ in range(10)]
    silly_names
