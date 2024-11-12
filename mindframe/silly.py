import random

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


if False:
    # Generate a list of names
    silly_names = [silly_name() for _ in range(10)]
    silly_names
