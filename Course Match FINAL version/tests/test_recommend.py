"""Course recommendations from a CV: Fall 2026 / Spring 2027 offer, evidence checked in code."""
import json
import httpx
from fastapi.testclient import TestClient
from backend.main import app
from backend.recommend import load_courses
from tests.test_ai import provider as cloud, provider_response
from tests.test_ollama import provider as local

client = TestClient(app)
CV = 'Analyst at a retail bank where I worked on credit risk models and Excel reporting.'
JOB = 'Credit risk analyst'
BASE = {'cv_text': CV, 'job': JOB, 'terms': ['fall', 'spring'], 'level': 'graduate'}
OFFICIAL = {course['code']: course for course in load_courses()}
URL = 'https://didattica.unibocconi.eu/ts/tsn_anteprima.php?cod_ins={}&anno=2027'


def source_for(evidence, cv=CV, job=JOB, interests=''):
    return {'cv': cv, 'job': job, 'interests': interests}[evidence['source']]


def ai_report(**changes):
    item = {'code': '20249', 'category': 'background',
            'reason': 'Your CV mentions credit risk work, which matches this course title.',
            'evidence_source': 'cv', 'evidence_quote': 'credit risk models and Excel reporting'}
    return {'recommendations': [{**item, **changes}], 'insufficient_evidence': False}


def test_offer_data_is_loaded_once_per_course_with_credits_per_term():
    assert len(OFFICIAL) == 542
    course = OFFICIAL['20249']
    assert course['title'] == 'CREDIT RISK MANAGEMENT'
    assert all(isinstance(o['credits'], int) and o['term'] in ('Fall 2026', 'Spring 2027')
               for o in course['offerings'])


def test_keyword_recommendations_have_credits_link_and_verified_evidence():
    data = client.post('/recommend', json=BASE).json()
    recs = data['recommendations']
    assert data['method'] == 'keyword_overlap' and data['decision'] == 'ask_your_advisor'
    assert '20249' in [r['code'] for r in recs]
    for rec in recs:
        official = OFFICIAL[rec['code']]
        assert rec['title'] == official['title']
        assert rec['offerings'] == official['offerings']
        assert rec['url'] == URL.format(rec['code'])
        assert rec['category'] in ('background', 'interest')
        evidence = rec['evidence']
        assert source_for(evidence)[evidence['start']:evidence['end']] == evidence['quote']
    assert 'titles' in data['limitations'].lower()


def test_term_and_level_filters_are_applied():
    base = {**BASE, 'cv_text': 'finance marketing management economics statistics', 'job': 'consultant'}
    spring = client.post('/recommend', json={**base, 'terms': ['spring']}).json()['recommendations']
    assert spring and all(o['term'] == 'Spring 2027' for r in spring for o in r['offerings'])
    undergrad = client.post('/recommend', json={**base, 'level': 'undergraduate'}).json()['recommendations']
    assert undergrad and all(r['level'] == 'Undergraduate' for r in undergrad)


def test_invalid_requests_are_rejected():
    for changes in [{'cv_text': ''}, {'cv_text': '   '}, {'job': ''}, {'terms': []}, {'terms': ['summer']},
                    {'level': 'phd'}, {'cv_text': 'a' * 30001}, {'job': 'a' * 501}, {'unknown': 1}]:
        assert client.post('/recommend', json={**BASE, **changes}).status_code == 422, changes
    assert client.post('/recommend', json={'job': JOB}).status_code == 422


def test_keyword_mode_never_calls_a_provider():
    with cloud(lambda request: (_ for _ in ()).throw(AssertionError('No call allowed'))):
        assert client.post('/recommend', json={**BASE, 'mode': 'keyword', 'ai_consent': True}).status_code == 200


def test_openai_requires_consent_before_any_call():
    with cloud(lambda request: (_ for _ in ()).throw(AssertionError('No call allowed'))):
        assert client.post('/recommend', json={**BASE, 'mode': 'ai'}).status_code == 422


def test_ai_request_lists_only_offered_courses_and_hides_credits():
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=provider_response(ai_report()))
    with cloud(handler):
        data = client.post('/recommend', json={**BASE, 'mode': 'ai', 'ai_consent': True,
                                               'interests': 'banking'}).json()
    body = seen[0]
    sent = json.loads(body['input'][0]['content'])
    assert sent['student'] == {'cv': CV, 'job_of_interest': JOB, 'interests': 'banking'}
    assert {c['code'] for c in sent['candidate_courses']} == set(OFFICIAL)
    assert all(set(c) == {'code', 'title', 'department', 'level'} for c in sent['candidate_courses'])
    assert 'UNTRUSTED' in body['instructions'] and 'credit' in body['instructions'].lower()
    rec = data['recommendations'][0]
    assert rec['code'] == '20249' and rec['category'] == 'background'
    assert rec['offerings'] == OFFICIAL['20249']['offerings'] and rec['url'] == URL.format('20249')
    assert data['provider'] == 'openai' and data['method'] == 'ai'


def test_ai_invented_courses_and_fabricated_quotes_are_removed_with_warning():
    report = ai_report()
    report['recommendations'] += [
        {**report['recommendations'][0], 'code': '99999'},
        {**report['recommendations'][0], 'evidence_quote': 'An invented sentence that is not in the CV.'},
        {**report['recommendations'][0]}]
    with cloud(lambda request: httpx.Response(200, json=provider_response(report))):
        data = client.post('/recommend', json={**BASE, 'mode': 'ai', 'ai_consent': True}).json()
    assert [r['code'] for r in data['recommendations']] == ['20249']
    assert data['warnings']


def test_ai_gap_must_quote_the_students_own_text():
    report = ai_report(category='gap', evidence_source='job', evidence_quote='Credit risk analyst',
                       reason='The job text names credit risk; your CV does not mention modelling theory.')
    with cloud(lambda request: httpx.Response(200, json=provider_response(report))):
        rec = client.post('/recommend', json={**BASE, 'mode': 'ai', 'ai_consent': True}).json()['recommendations'][0]
    assert rec['category'] == 'gap' and rec['evidence']['source'] == 'job'


def test_local_qwen_is_loopback_limited_and_experimental():
    seen = []
    def handler(request):
        seen.append(request)
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        body = json.loads(request.content)
        sent = json.loads(body['messages'][1]['content'])
        assert 0 < len(sent['candidate_courses']) <= 60
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(ai_report())}})
    with local(handler):
        data = client.post('/recommend', json={**BASE, 'mode': 'ollama'}).json()
    assert len(seen) == 1 and data['provider'] == 'ollama'
    assert any('Experimental' in w for w in data['warnings'])
    with local(lambda request: (_ for _ in ()).throw(AssertionError('Too long: no call'))):
        long = client.post('/recommend', json={**BASE, 'cv_text': 'x ' * 3100, 'mode': 'ollama'})
    assert long.status_code == 422
