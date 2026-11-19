"""Reading a course or degree page from a link: offline, with strict address checks."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / 'fixtures'
PUBLIC = '93.184.216.34'
PAGE = '''<html><head><title>BSc Economics – Course 101</title><style>.x{color:red}</style>
<script>var secret = "tracking code";</script></head><body>
<nav>Home | Admissions | Login menu</nav>
<h1>Introduction to Microeconomics</h1>
<p>Students learn <b>consumer theory</b> and market equilibrium.</p>
<ul><li>Learning outcome: analyse supply and demand</li><li>Assessment: written exam</li></ul>
<footer>Cookie settings and privacy footer</footer></body></html>'''


def resolver(host, port):
    return ['10.0.0.5'] if host == 'internal.example' else [PUBLIC]


@contextmanager
def web(handler, resolve=resolver):
    with patch('backend.web_page._resolve', side_effect=resolve), \
         patch('backend.web_page._client', side_effect=lambda: httpx.Client(
             transport=httpx.MockTransport(handler))):
        yield


def html(body=PAGE, status=200, **headers):
    headers.setdefault('content-type', 'text/html; charset=utf-8')
    return httpx.Response(status, content=body.encode(), headers=headers)


def read(url='https://uni.example/course'):
    return client.post('/extract-url', json={'url': url})


def never(request):
    raise AssertionError('No request may be sent')


def test_page_text_title_and_noise_removal():
    seen = []
    def handler(request):
        seen.append(request)
        return html()
    with web(handler):
        response = read()
    assert response.status_code == 200
    data = response.json()
    assert data['source'] == 'html' and data['url'] == 'https://uni.example/course'
    assert data['title'] == 'BSc Economics – Course 101'
    for wanted in ['Introduction to Microeconomics', 'consumer theory', 'analyse supply and demand', 'written exam']:
        assert wanted in data['text']
    for noise in ['tracking code', 'color:red', 'Admissions', 'Cookie settings']:
        assert noise not in data['text']
    assert data['warnings']
    assert len(seen) == 1 and seen[0].method == 'GET'
    assert 'cookie' not in seen[0].headers and 'authorization' not in seen[0].headers


def test_text_follows_the_declared_charset():
    page = '<html><body><p>Économie et développement</p></body></html>'
    with web(lambda request: httpx.Response(200, content=page.encode('latin-1'),
                                            headers={'content-type': 'text/html; charset=iso-8859-1'})):
        assert 'Économie et développement' in read().json()['text']


def test_page_without_a_declared_charset_still_reads_as_utf8():
    with web(lambda request: httpx.Response(200, content='<p>Économie appliquée</p>'.encode(),
                                            headers={'content-type': 'text/html'})):
        assert 'Économie appliquée' in read().json()['text']
    with web(lambda request: httpx.Response(200, content='<meta charset="nonsense-xyz"><p>Hello course text</p>'.encode(),
                                            headers={'content-type': 'text/html'})):
        assert 'Hello course text' in read().json()['text']


def test_unsafe_addresses_are_rejected_before_any_request():
    urls = ['file:///etc/passwd', 'ftp://example.com/x', 'javascript:alert(1)', 'example.com/course', '',
            'http://user:pass@example.com/', 'http://example.com:8080/', 'https://example.com:22/',
            'http://localhost/', 'http://127.0.0.1/', 'http://[::1]/', 'http://10.0.0.5/',
            'http://169.254.169.254/latest/meta-data/', 'http://192.168.1.1/', 'http://0.0.0.0/',
            'http://[::ffff:127.0.0.1]/', 'http://2130706433/']
    with patch('backend.web_page._client', side_effect=never):
        for url in urls:
            assert read(url).status_code in (400, 422), url


def test_public_looking_name_that_resolves_to_private_space_is_rejected():
    with web(never):
        assert read('https://internal.example/course').status_code in (400, 422)
    with web(never, resolve=lambda host, port: [PUBLIC, '127.0.0.1']):
        assert read('https://mixed.example/course').status_code in (400, 422)
    with web(never, resolve=lambda host, port: []):
        assert read('https://unknown.example/course').status_code in (400, 422, 502)


def test_redirects_are_followed_but_checked_each_time():
    def ok(request):
        if request.url.host == 'uni.example':
            return httpx.Response(302, headers={'location': 'https://other.example/page'})
        return html()
    with web(ok):
        data = read().json()
    assert data['url'] == 'https://other.example/page'
    for target in ['http://internal.example/admin', 'http://169.254.169.254/', 'file:///etc/passwd']:
        with web(lambda request, t=target: httpx.Response(302, headers={'location': t}) if request.url.host == 'uni.example' else never(request)):
            assert read().status_code in (400, 422), target
    with web(lambda request: httpx.Response(302, headers={'location': '/loop'})):
        assert read().status_code == 502


def test_size_type_status_timeout_and_emptiness_are_reported_without_echoing_the_site():
    with patch('backend.web_page.MAX_BYTES', 500), web(lambda request: html('<p>' + 'a' * 2000 + '</p>')):
        assert read().status_code == 413
    with web(lambda request: httpx.Response(200, content=b'x', headers={'content-type': 'image/png'})):
        assert read().status_code == 415
    with web(lambda request: html('<html><body><script>app()</script></body></html>')):
        response = read()
    assert response.status_code == 422 and 'pdf' in response.json()['detail'].lower()
    with web(lambda request: html('<p>' + 'word ' * 7000 + '</p>')):
        assert read().status_code == 422
    with web(lambda request: html('secret site diagnostic', status=404)):
        response = read()
    assert response.status_code == 502 and 'secret site diagnostic' not in response.text
    def slow(request):
        raise httpx.ReadTimeout('private diagnostic', request=request)
    with web(slow):
        response = read()
    assert response.status_code == 504 and 'private diagnostic' not in response.text


def test_pdf_behind_a_link_uses_the_pdf_reader():
    pdf = httpx.Response(200, content=(FIXTURES / 'table.pdf').read_bytes(),
                         headers={'content-type': 'application/pdf'})
    with web(lambda request: pdf):
        data = read('https://uni.example/syllabus.pdf').json()
    assert data['source'] == 'pdf' and 'Synthetic syllabus' in data['text'] and data['warnings']
    bad = httpx.Response(200, content=(FIXTURES / 'encrypted.pdf').read_bytes(),
                         headers={'content-type': 'application/pdf'})
    with web(lambda request: bad):
        assert read('https://uni.example/locked.pdf').status_code == 422


def test_invalid_request_bodies_are_rejected():
    for body in [{}, {'url': 5}, {'url': 'https://uni.example/' + 'a' * 2100},
                 {'url': 'https://uni.example/', 'extra': 1}]:
        assert client.post('/extract-url', json=body).status_code == 422


def test_page_offers_the_link_option_for_the_home_syllabus():
    page = client.get('/').text
    assert 'id="syllabus-home-link"' in page
    assert page.count('name="syllabus-home-source"') == 2
