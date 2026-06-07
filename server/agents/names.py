import random

AGENT_NAMES = [
    "Sam", "Alex", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Quinn",
    "Avery", "Parker", "Rowan", "Sage", "Emery", "Finley", "Hayden", "Kai",
    "Reese", "Skyler", "Blake", "Drew", "Ellis", "Frankie", "Harper", "Jamie",
    "Kendall", "Logan", "Marley", "Noel", "Oakley", "Peyton", "Remy", "Shiloh",
    "Tatum", "Wren", "Zion", "Ari", "Bailey", "Charlie", "Dakota", "Eden",
    "Gray", "Hollis", "Indigo", "Juno", "Kit", "Lane", "Micah", "Nova",
    "Onyx", "Pax", "Quill", "Ryder", "Sawyer", "Toby", "Uri", "Vale",
    "Wes", "Xen", "York", "Zane", "Amari", "Bevan", "Corin", "Daryn",
    "Elian", "Faron", "Galen", "Haven", "Ira", "Joss", "Kyro", "Linden",
    "Merin", "Niko", "Orin", "Pell", "Quen", "Rune", "Soren", "Tarin",
    "Uma", "Vesper", "Wynn", "Xander", "Yael", "Zephyr",
]


def pick_agent_name(taken):
    # Pick a random unused name; if all are used, add a [2], [3], ... suffix.
    taken = set(taken)
    free = [n for n in AGENT_NAMES if n not in taken]

    if free:
        return random.choice(free)

    base = random.choice(AGENT_NAMES)
    suffix = 2
    while f"{base} [{suffix}]" in taken:
        suffix += 1
    return f"{base} [{suffix}]"
