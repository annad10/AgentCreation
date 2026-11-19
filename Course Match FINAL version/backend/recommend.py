"""Course suggestions from a student's own text and the official Fall 2026 / Spring 2027 offer.

Titles, credits, terms, levels and links always come from data/bocconi/courses.json
and code; a model may only choose course codes and explain them with a quote.
"""
import json
from functools import lru_cache
from pathlib import Path
from .extract import terms, citation
from .checks import locate_quote, verify_quote

DATA = Path(__file__).resolve().parents[1] / 'data' / 'bocconi' / 'courses.json'
TERM_NAMES = {'fall': 'Fall 2026', 'spring': 'Spring 2027'}
# Both terms belong to Bocconi academic year 2026-27, which the course pages call anno=2027.
COURSE_URL = 'https://didattica.unibocconi.eu/ts/tsn_anteprima.php?cod_ins={code}&anno=2027'
MAX_RESULTS = 8
LOCAL_CANDIDATES = 60
SOURCE_WEIGHT = {'job': 3, 'interests': 2, 'cv': 1}
SOURCE_NAME = {'cv': 'CV', 'job': 'job of interest', 'interests': 'interests'}
TITLE_STOPWORDS = {'module', 'advanced'}
LIMITATIONS = (
    'Suggestions use only course titles and departments from the official Fall 2026 and Spring 2027 '
    'exchange offer; syllabi were not read. Read each course description before choosing. '
    'Credits are Bocconi credits as listed in the offer (ECTS equivalent) and are not converted to '
    'your home-university credits. Bocconi may still show last year\'s description on a course page, '
    'and class groups can change, so confirm availability with Bocconi and your advisor. '
    'A suggestion is not an approval or an equivalence decision.')


@lru_cache(maxsize=1)
def _load():
    rows = json.loads(DATA.read_text(encoding='utf-8'))['courses']
    courses = {}
    for row in rows:
        course = courses.setdefault(row['code'], {
            'code': row['code'], 'title': row['title'], 'department': row['department'],
            'level': row['level'], 'offerings': []})
        offering = {'term': row['term'], 'credits': row['credits']}
        if offering not in course['offerings']:
            course['offerings'].append(offering)
    order = list(TERM_NAMES.values())
    for course in courses.values():
        course['offerings'].sort(key=lambda o: order.index(o['term']))
    return tuple(courses.values())


def load_courses():
    return [{**course, 'offerings': [dict(o) for o in course['offerings']]} for course in _load()]


def eligible(term_keys, level):
    """Courses offered in the chosen terms; undergraduates may only take undergraduate courses."""
    wanted = {TERM_NAMES[key] for key in term_keys}
    result = []
    for course in load_courses():
        course['offerings'] = [o for o in course['offerings'] if o['term'] in wanted]
        if course['offerings'] and (level == 'graduate' or course['level'] == 'Undergraduate'):
            result.append(course)
    return result


def _stem(word):
    return word[:-1] if word.endswith('s') and len(word) > 4 else word


def _words(text):
    return {_stem(word): (word, span) for word, span in terms(text).items()}


def rank_courses(texts, courses):
    """Score each course by title words found in the student's text (job > interests > CV)."""
    words = {source: _words(text) for source, text in texts.items() if text}
    ranked = []
    for course in courses:
        title = {_stem(w) for w in terms(course['title']) if w not in TITLE_STOPWORDS}
        best, score = None, 0
        for stem in sorted(title):
            hits = [(SOURCE_WEIGHT[s], s) for s in words if stem in words[s]]
            if hits:
                weight, source = max(hits)
                score += weight
                if best is None or weight > best[0]:
                    best = (weight, source, words[source][stem])
        if score:
            ranked.append((score, course, best))
    ranked.sort(key=lambda item: (-item[0], item[1]['title']))
    return ranked


def _entry(course, category, reason, evidence):
    return {'code': course['code'], 'title': course['title'], 'department': course['department'],
            'level': course['level'], 'offerings': course['offerings'],
            'url': COURSE_URL.format(code=course['code']),
            'category': category, 'reason': reason, 'evidence': evidence}


def _result(method, provider, entries, warnings, count, insufficient=False):
    return {'method': method, 'provider': provider, 'decision': 'ask_your_advisor',
            'recommendations': entries, 'warnings': warnings, 'candidate_count': count,
            'message': ('No supported suggestions. Add more detail about your studies, experience and job of interest, then try again.'
                        if not entries or insufficient else
                        'Suggestions ready. Open each course description, then review the list with your advisor.'),
            'limitations': LIMITATIONS}


def recommend_keyword(cv, job, interests, term_keys, level):
    texts = {'cv': cv, 'job': job, 'interests': interests}
    courses = eligible(term_keys, level)
    entries = []
    for _, course, (_, source, (word, span)) in rank_courses(texts, courses)[:MAX_RESULTS]:
        evidence = {'source': source, **citation(texts[source], span)}
        if not verify_quote(texts[source], evidence):
            continue
        entries.append(_entry(
            course, 'background' if source == 'cv' else 'interest',
            f'The word "{word}" in your {SOURCE_NAME[source]} also appears in this course title.', evidence))
    return _result('keyword_overlap', None, entries, [], len(courses))


def recommend_ai(cv, job, interests, term_keys, level, provider='openai'):
    from . import llm
    texts = {'cv': cv, 'job': job, 'interests': interests}
    courses = eligible(term_keys, level)
    warnings = []
    if provider == 'ollama':
        ranked = {c['code']: score for score, c, _ in rank_courses(texts, courses)}
        courses = sorted(courses, key=lambda c: (-ranked.get(c['code'], 0), c['title']))[:LOCAL_CANDIDATES]
        warnings.append('Experimental local Qwen analysis. A small model can miss or misjudge courses. '
                        f'It only saw the {len(courses)} courses whose titles best match your text.')
    candidates = [{k: c[k] for k in ('code', 'title', 'department', 'level')} for c in courses]
    analysis = llm.recommend_courses(
        {'cv': cv, 'job_of_interest': job, 'interests': interests}, candidates, provider)
    by_code = {c['code']: c for c in courses}
    entries, seen, rejected = [], set(), False
    for item in analysis.recommendations:
        course = by_code.get(item.code)
        evidence = locate_quote(texts[item.evidence_source], item.evidence_quote)
        if course is None or evidence is None or item.code in seen:
            rejected = rejected or course is None or evidence is None
            continue
        seen.add(item.code)
        entries.append(_entry(course, item.category, item.reason,
                              {'source': item.evidence_source, **evidence}))
    if rejected:
        warnings.append('Some AI suggestions were hidden because the course is not in the offer for your '
                        'choices or the quote could not be verified in your text.')
    return _result('ai', provider, entries[:MAX_RESULTS], warnings, len(courses), analysis.insufficient_evidence)
