"""Exploratory vocabulary comparison; never an equivalence decision."""
from .extract import terms, citation
from .checks import verify_quote


def compare(home, bocconi):
    home_terms, host_terms = terms(home), terms(bocconi)
    shared = sorted(home_terms.keys() & host_terms.keys())
    evidence = []
    for term in shared[:20]:
        item = {'term': term, 'home': citation(home, home_terms[term]),
                'bocconi': citation(bocconi, host_terms[term])}
        if verify_quote(home, item['home']) and verify_quote(bocconi, item['bocconi']):
            evidence.append(item)
    return {
        'method': 'keyword_overlap', 'decision': 'ask_your_advisor',
        'shared_terms': shared, 'evidence': evidence,
        'message': ('Shared vocabulary found. Review the excerpts with your advisor.'
                    if shared else 'No shared keywords found. Ask your advisor to review both syllabi.'),
        'limitations': 'Keyword overlap does not establish equivalent content, level or credits. '
                      'Different wording or languages may hide similarities. '
                      'No AI analysis or credit conversion was performed. '
                      'Excerpts are shown for up to 20 shared terms. PDF excerpts refer to the reviewed extracted text; check the original PDF.'
    }


def compare_ai(home, bocconi, provider="openai"):
    from . import llm
    from .checks import locate_quote
    analysis = llm.call_local_model(home, bocconi) if provider == "ollama" else llm.call_model(home, bocconi)
    findings, gaps, warnings = [], [], []
    if provider == "ollama":
        warnings.append('Experimental local Qwen analysis. A small model can miss or misinterpret topics; verify every observation against the original syllabi.')
    rejected = False
    for item in analysis.findings:
        home_evidence = locate_quote(home, item.home_quote)
        host_evidence = locate_quote(bocconi, item.bocconi_quote)
        if not home_evidence or not host_evidence:
            rejected = True
            continue
        findings.append({'kind': item.kind, 'title': item.title,
            'explanation': item.explanation, 'home': home_evidence, 'bocconi': host_evidence})
    for item in analysis.gaps:
        source = home if item.source == 'home' else bocconi
        evidence = locate_quote(source, item.quote)
        if not evidence:
            rejected = True
            continue
        gaps.append({'topic': item.topic, 'explanation': item.explanation,
                     'source': item.source, 'citation': evidence})
    if rejected:
        warnings.append('Some AI findings were hidden because their quotes could not be verified in the submitted text.')
    insufficient = analysis.insufficient_evidence or rejected or not findings
    return {'method': 'ai', 'provider': provider, 'decision': 'ask_your_advisor',
        'message': ('Evidence is incomplete. Review the supported observations with your advisor.'
                    if insufficient else 'AI comparison ready. Review the cited evidence with your advisor.'),
        'findings': findings, 'gaps': gaps, 'insufficient_evidence': insufficient,
        'warnings': warnings,
        'limitations': 'Quotes were checked against the submitted text; AI interpretations may still be wrong. '
            'A possible gap means coverage is not established in the other supplied syllabus, not that the topic is absent from the course. '
            'No equivalence approval, similarity percentage or credit conversion is provided. '
            'PDF excerpts refer to the reviewed extracted text; check the original PDF.'}
