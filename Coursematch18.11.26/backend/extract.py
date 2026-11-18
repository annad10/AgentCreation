"""Locate original text passages without rewriting source evidence."""
import re

# Generic syllabus vocabulary is deliberately excluded from keyword evidence.
STOPWORDS = set('''the and for with from this that into are was will have has can its
les des une pour dans avec sur est sont aux par ces pas qui que du de la le et en
page pages table tables course courses syllabus students student learning outcomes objectives introduction
study studies covers covering topics understand understanding knowledge skills
cours étudiants apprentissage objectifs introduction'''.split())


def terms(text):
    found = {}
    for match in re.finditer(r'[^\W\d_]{4,}', text, re.UNICODE):
        word = match.group().lower()
        if word not in STOPWORDS:
            found.setdefault(word, match.span())
    return found


def citation(text, span):
    # Preserve exact character offsets into the submitted document.
    start, end = span
    left = max(text.rfind(mark, 0, start) for mark in '.!?\n') + 1
    boundaries = [text.find(mark, end) for mark in '.!?\n']
    right = min((pos + 1 for pos in boundaries if pos >= 0), default=len(text))
    # Bound excerpts even when a syllabus contains one very long line.
    left = max(left, start - 160)
    right = min(right, end + 160)
    while left < start and text[left].isspace():
        left += 1
    result = {'quote': text[left:right], 'start': left, 'end': right}
    pages = list(re.finditer(r'^\[Page (\d+)\]$', text[:start], re.MULTILINE))
    if pages:
        result['page'] = int(pages[-1].group(1))
    return result
