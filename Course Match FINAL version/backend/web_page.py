"""Read one public course or degree page so the student can review its text.

The server fetches only http(s) pages on standard ports, never local or private
addresses (re-checked on every redirect), sends no cookies or credentials, and
caps size and time. Nothing fetched is stored. The address check happens just
before each request; use this tool locally, as the README advises.
"""
import ipaddress
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import httpx
from fastapi import HTTPException
from .pdf_upload import extract_pdf, MAX_BYTES, MAX_TEXT

MAX_REDIRECTS = 3
MAX_SECONDS = 20
DEFAULT_PORTS = {'http': 80, 'https': 443}
TEXT_TYPES = {'text/html', 'application/xhtml+xml', 'text/plain'}
SKIP_TAGS = {'script', 'style', 'noscript', 'template', 'svg', 'iframe', 'nav', 'footer', 'aside'}
BLOCK_TAGS = {'p', 'div', 'br', 'li', 'ul', 'ol', 'tr', 'table', 'section', 'article', 'header', 'main',
              'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'dt', 'dd'}
NOT_ALLOWED = 'This web address cannot be used. Enter a public http:// or https:// page, or upload a PDF instead.'
PASTE = ' Save the page as a PDF and upload that instead.'


def _client():
    # No proxy settings, no cookies, no automatic redirects: each hop is checked in code.
    return httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)


def _resolve(host, port):
    try:
        return [item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except (socket.gaierror, UnicodeError, OSError):
        return []


def _public(address):
    ip = ipaddress.ip_address(address.split('%')[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def _check(url):
    """Raise unless the address is a public http(s) page on a standard port."""
    try:
        parts = urlsplit(url.strip())
        host, port = parts.hostname, parts.port
    except ValueError:
        raise HTTPException(422, NOT_ALLOWED) from None
    if parts.scheme not in DEFAULT_PORTS or not host or parts.username or parts.password:
        raise HTTPException(422, NOT_ALLOWED)
    if port not in (None, DEFAULT_PORTS[parts.scheme]):
        raise HTTPException(422, NOT_ALLOWED)
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = _resolve(host, DEFAULT_PORTS[parts.scheme])
    if not addresses:
        raise HTTPException(422, 'This web address could not be found. Check the link or upload a PDF instead.')
    try:
        if not all(_public(address) for address in addresses):
            raise HTTPException(422, NOT_ALLOWED)
    except ValueError:
        raise HTTPException(422, NOT_ALLOWED) from None


def _fetch(url):
    started = time.monotonic()
    for _ in range(MAX_REDIRECTS + 1):
        _check(url)
        try:
            with _client() as client, client.stream('GET', url, headers={
                    'User-Agent': 'CourseMatch/0.1 (student tool)',
                    'Accept': 'text/html,application/pdf;q=0.9,text/plain;q=0.5'}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    target = response.headers.get('location')
                    if not target:
                        raise HTTPException(502, 'The website sent an unusable redirect.' + PASTE)
                    url = urljoin(url, target)
                    continue
                if response.status_code != 200:
                    raise HTTPException(502, 'The website did not return the page. It may need a login or block automated access.' + PASTE)
                header = response.headers.get('content-type', '')
                kind = header.split(';', 1)[0].strip().lower()
                if kind not in TEXT_TYPES | {'application/pdf'}:
                    raise HTTPException(415, 'This link is not a web page or PDF.' + PASTE)
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, 'This page is too large (limit 10 MB).' + PASTE)
                    if time.monotonic() - started > MAX_SECONDS:
                        raise HTTPException(504, 'The website took too long to answer. Try again or upload a PDF instead.')
                    chunks.append(chunk)
                return url, kind, header, b''.join(chunks)
        except HTTPException:
            raise
        except httpx.TimeoutException:
            raise HTTPException(504, 'The website took too long to answer. Try again or upload a PDF instead.') from None
        except httpx.RequestError:
            raise HTTPException(502, 'Cannot reach this website. Check the link and your connection, or upload a PDF instead.') from None
    raise HTTPException(502, 'The website redirected too many times.' + PASTE)


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self.skip, self.in_title = [], '', 0, False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag == 'title':
            self.in_title = True
        elif tag in BLOCK_TAGS:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag == 'title':
            self.in_title = False
        elif tag in BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def _decode(content, header):
    found = re.search(r'charset=["\']?([\w-]+)', header, re.I)
    name = found.group(1) if found else None
    if not name:
        meta = re.search(rb'charset=["\']?([\w-]+)', content[:2048], re.I)
        name = meta.group(1).decode('ascii') if meta else 'utf-8'
    try:
        return content.decode(name, errors='replace')
    except LookupError:
        return content.decode('utf-8', errors='replace')


def _clean(text):
    lines = (' '.join(line.replace('\xa0', ' ').split()) for line in text.splitlines())
    return '\n'.join(line for line in lines if line)


def read_page(url):
    final_url, kind, header, content = _fetch(url)
    if kind == 'application/pdf':
        result = extract_pdf(content)
        return {'source': 'pdf', 'url': final_url, 'title': '', 'text': result['text'],
                'warnings': result['warnings']}
    raw = _decode(content, header)
    title = ''
    if kind == 'text/plain':
        text = _clean(raw)
    else:
        parser = _PageText()
        parser.feed(raw)
        parser.close()
        text, title = _clean(''.join(parser.parts)), ' '.join(parser.title.split())[:200]
    if not text:
        raise HTTPException(422, 'No readable text was found on this page. It may need JavaScript or a login.' + PASTE)
    if len(text) > MAX_TEXT:
        raise HTTPException(422, 'The page text exceeds 30,000 characters. Paste only the relevant part.')
    return {'source': 'html', 'url': final_url, 'title': title, 'text': text,
            'warnings': ['Menus, footers and scripts were removed. Check the text against the page before comparing; '
                         'pages that load content with JavaScript or sit behind a login may be incomplete.']}
