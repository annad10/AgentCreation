"""Match a home-university course to the Fall 2026 / Spring 2027 Bocconi offer.

The offer lists titles, credits and terms only, so the other side of each comparison
is the official public Bocconi course page, read by the server for a short list of courses.
"""
import re
from fastapi import HTTPException
from .judge import compare, compare_ai
from .recommend import COURSE_URL, LIMITATIONS, eligible, rank_courses
from .web_page import read_page

SHORTLIST = 5
MAX_EVIDENCE = 5
PROFILE_YEAR = re.compile(r'refers to the (\d{4}-\d{4}) academic year')
LIMITS = ('The shortlist comes from course titles in the official Fall 2026 and Spring 2027 exchange offer; '
          'a good match may have a different title. Each comparison uses the text of the official Bocconi '
          'course page, which can still describe last year\'s course. ') + LIMITATIONS


def course_text(code, text):
    """Start at the course heading so page menus do not count as course content."""
    match = re.search(rf'^{re.escape(code)} - ', text, re.MULTILINE)
    return text[match.start():] if match else text


def match_offer(home, term_keys, level, mode='keyword'):
    from . import llm
    courses = eligible(term_keys, level)
    shortlist = [course for _, course, _ in rank_courses({'cv': home}, courses)[:SHORTLIST]]
    matches = []
    for course in shortlist:
        url = COURSE_URL.format(code=course['code'])
        entry = {'code': course['code'], 'title': course['title'], 'department': course['department'],
                 'level': course['level'], 'offerings': course['offerings'], 'url': url,
                 'profile_year': None, 'note': None, 'comparison': None}
        matches.append(entry)
        try:
            text = course_text(course['code'], read_page(url)['text'])
        except HTTPException as error:
            entry['note'] = f'The Bocconi course page could not be read ({error.detail}) Open the link to read it yourself.'
            continue
        year = PROFILE_YEAR.search(text)
        entry['profile_year'] = year.group(1) if year else None
        try:
            if mode == 'keyword':
                entry['comparison'] = compare(home, text)
            else:
                entry['comparison'] = compare_ai(home, text, provider='ollama' if mode == 'ollama' else 'openai')
        except llm.AIError as error:
            if error.status != 422:
                raise
            entry['note'] = error.message
            continue
        if entry['comparison'].get('evidence'):
            entry['comparison']['evidence'] = entry['comparison']['evidence'][:MAX_EVIDENCE]
    return {'method': 'offer_match', 'mode': mode, 'decision': 'ask_your_advisor',
            'matches': matches, 'candidate_count': len(courses),
            'message': ('No course title in the offer matches your text. Add more detail, or use the CV course recommendations tab.'
                        if not matches else
                        'Possible Bocconi matches found. Read the quotes and the course pages, then review them with your advisor.'),
            'limitations': LIMITS}
