"""Home course -> shortlisted Bocconi courses, with the official Bocconi page as the other side."""
import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from backend.main import app
from backend.offer_match import course_text
from backend.recommend import load_courses
from tests.test_ai import provider as cloud, provider_response

client = TestClient(app)
HOME = ('Credit risk management. Students learn credit risk models and scoring for retail banking. '
        'Assessment is a written exam.')
BASE = {'home_syllabus': HOME, 'terms': ['fall', 'spring'], 'level': 'graduate'}
OFFICIAL = {c['code']: c for c in load_courses()}
URL = 'https://didattica.unibocconi.eu/ts/tsn_anteprima.php?cod_ins={}&anno=2027'
PUBLIC = '93.184.216.34'


PAGE_TEXT = ('20249 - CREDIT RISK MANAGEMENT\nImportant! The content in this course profile refers to the 2025-2026 academic year.\n'
             'Students learn credit risk models in banking and corporate lending.')


def bocconi_page(code):
    return (f'<html><head><title>Course 2026-2027</title></head><body><header>Apply Discover Admissions menu</header>'
            f'<h1>{code} - {OFFICIAL[code]["title"]}</h1>'
            '<p>Important! The content in this course profile refers to the 2025-2026 academic year.</p>'
            '<p>Students learn credit risk models in banking and corporate lending.</p>'
            '<footer>Cookie footer</footer></body></html>')


@contextmanager
def site(handler=None, requested=None):
    def default(request):
        assert request.url.host == 'didattica.unibocconi.eu', request.url
        if requested is not None:
            requested.append(str(request.url))
        code = request.url.params['cod_ins']
        assert request.url.params['anno'] == '2027'
        return httpx.Response(200, content=bocconi_page(code).encode(),
                              headers={'content-type': 'text/html; charset=utf-8'})
    with patch('backend.web_page._resolve', side_effect=lambda host, port: [PUBLIC]), \
         patch('backend.web_page._client', side_effect=lambda: httpx.Client(
             transport=httpx.MockTransport(handler or default))):
        yield


def run(**changes):
    return client.post('/match-offer', json={**BASE, **changes})


def test_course_text_starts_at_the_course_heading():
    text = 'Menu\nApply\n20249 - CREDIT RISK MANAGEMENT\nStudents learn models\n'
    assert course_text('20249', text).startswith('20249 - CREDIT RISK MANAGEMENT')
    assert 'Apply' not in course_text('20249', text)
    assert course_text('99999', text) == text


def test_shortlist_reads_official_pages_and_shows_credits_link_and_both_quotes():
    requested = []
    with site(requested=requested):
        response = run()
    assert response.status_code == 200
    data = response.json()
    assert data['method'] == 'offer_match' and data['decision'] == 'ask_your_advisor'
    matches = data['matches']
    assert 1 <= len(matches) <= 5 and '20249' in [m['code'] for m in matches]
    assert requested == [URL.format(m['code']) for m in matches]
    for match in matches:
        official = OFFICIAL[match['code']]
        assert match['title'] == official['title'] and match['offerings'] == official['offerings']
        assert match['url'] == URL.format(match['code'])
        assert match['profile_year'] == '2025-2026'
    credit = next(m for m in matches if m['code'] == '20249')
    comparison = credit['comparison']
    assert comparison['method'] == 'keyword_overlap' and 0 < len(comparison['evidence']) <= 5
    for item in comparison['evidence']:
        assert HOME[item['home']['start']:item['home']['end']] == item['home']['quote']
        assert item['bocconi']['quote'] in PAGE_TEXT
        assert 'Admissions' not in item['bocconi']['quote']
    assert 'titles' in data['limitations'].lower()


def test_term_and_level_filters_apply():
    with site():
        spring = run(terms=['spring']).json()['matches']
        undergrad = run(level='undergraduate', home_syllabus='finance statistics management marketing economics').json()['matches']
    assert spring and all(o['term'] == 'Spring 2027' for m in spring for o in m['offerings'])
    assert undergrad and all(m['level'] == 'Undergraduate' for m in undergrad)


def test_unreadable_bocconi_page_still_shows_the_course_with_a_note():
    with site(lambda request: httpx.Response(404, text='secret site diagnostic')):
        response = run()
    assert response.status_code == 200 and 'secret site diagnostic' not in response.text
    match = response.json()['matches'][0]
    assert match['comparison'] is None and match['note']
    assert match['offerings'] and match['url'].startswith('https://didattica.unibocconi.eu/')


def test_no_title_match_makes_no_requests_and_points_to_the_cv_tab():
    with site(lambda request: (_ for _ in ()).throw(AssertionError('No request needed'))):
        data = run(home_syllabus='Painting techniques, sculpture and ceramics studio.').json()
    assert data['matches'] == [] and 'CV' in data['message']


def test_invalid_requests_are_rejected():
    for changes in [{'home_syllabus': ''}, {'home_syllabus': '   '}, {'home_syllabus': 'a' * 30001},
                    {'terms': []}, {'terms': ['summer']}, {'level': 'phd'}, {'mode': 'other'}, {'extra': 1}]:
        assert run(**changes).status_code == 422, changes


def test_openai_needs_consent_then_compares_each_shortlisted_page():
    with site(lambda request: (_ for _ in ()).throw(AssertionError('No request before consent'))):
        assert run(mode='ai').status_code == 422
    calls = []
    def provider_handler(request):
        calls.append(request)
        report = {'findings': [{'kind': 'similarity', 'title': 'Credit risk models',
            'explanation': 'Both texts describe learning credit risk models.',
            'home_quote': 'Students learn credit risk models',
            'bocconi_quote': 'Students learn credit risk models'}], 'gaps': [], 'insufficient_evidence': False}
        return httpx.Response(200, json=provider_response(report))
    with site(), cloud(provider_handler):
        data = run(mode='ai', ai_consent=True).json()
    assert len(calls) == len(data['matches']) >= 1
    comparison = data['matches'][0]['comparison']
    assert comparison['method'] == 'ai' and comparison['findings'][0]['home']['quote'] == 'Students learn credit risk models'


def test_syllabus_tab_no_longer_asks_for_a_bocconi_syllabus():
    page = client.get('/').text
    assert 'id="syllabus-bocconi"' not in page and 'id="syllabus-bocconi-pdf"' not in page
    assert page.count('name="syl-level"') == 2 and 'id="syllabus-home"' in page
    assert 'Course text to compare' not in page and 'paste the syllabus' not in page.lower()
    assert 'Check the text read from your course' in page
