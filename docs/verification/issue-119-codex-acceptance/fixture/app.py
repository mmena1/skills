import fixturedep


def calculate(value):
    """Public contract: calculate doubles its input."""
    return fixturedep.scale(value) + value


def label(value):
    return fixturedep.fmt(value)
