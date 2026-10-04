"""Citation parsing and position mapping after generated-text sanitization."""
from difflib import SequenceMatcher
from urllib.parse import urlsplit


def safe_citation_url(url):
    try:
        parsed = urlsplit(url)
        return parsed.scheme in {"https", "http"} and bool(parsed.hostname) and not parsed.username
    except (ValueError, TypeError):
        return False


def response_text_and_citations(response):
    parts, citations = [], []
    offset = 0
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            text = getattr(content, "text", None) or getattr(content, "refusal", "")
            if not text:
                continue
            if parts:
                parts.append("\n")
                offset += 1
            for annotation in getattr(content, "annotations", []) or []:
                if annotation.type != "url_citation" or not safe_citation_url(annotation.url):
                    continue
                start, end = annotation.start_index, annotation.end_index
                if 0 <= start < end <= len(text):
                    citations.append({"url": annotation.url, "title": annotation.title,
                                      "start_index": start + offset, "end_index": end + offset})
            parts.append(text)
            offset += len(text)
    return "".join(parts), citations


def remap_citations(original, sanitized, citations):
    """Drop citations on redacted text; translate retained positions to JS UTF-16."""
    blocks = SequenceMatcher(None, original, sanitized, autojunk=False).get_matching_blocks()
    remapped = []
    for citation in citations or []:
        if not safe_citation_url(citation.get("url")):
            continue
        start, end = citation.get("start_index"), citation.get("end_index")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(original):
            continue
        # Only retain a citation if its entire attributed span survived unchanged.
        for block in blocks:
            if block.a <= start and end <= block.a + block.size:
                new_start, new_end = block.b + start - block.a, block.b + end - block.a
                remapped.append({**citation,
                    "start_index": len(sanitized[:new_start].encode("utf-16-le")) // 2,
                    "end_index": len(sanitized[:new_end].encode("utf-16-le")) // 2})
                break
    return remapped
