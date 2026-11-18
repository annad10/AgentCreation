"""Check source evidence. No unverified credit conversions are performed."""


def verify_quote(source, citation):
    return source[citation['start']:citation['end']] == citation['quote']


def locate_quote(source, quote):
    """Require an exact informative quote; calculate offsets and page in code."""
    import re
    if len(quote.strip()) < 12 or not re.search(r'[^\W\d_]{4,}', quote):
        return None
    start = source.find(quote)
    if start < 0:
        return None
    evidence = {'quote': quote, 'start': start, 'end': start + len(quote)}
    pages = list(re.finditer(r'^\[Page (\d+)\]$', source[:start], re.MULTILINE))
    if pages:
        evidence['page'] = int(pages[-1].group(1))
    return evidence
