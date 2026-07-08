"""
title: Offline Wikis (Kiwix)
author: Gr4Ig
description: Search and read the offline Kiwix library (Wikipedia and any other ZIM files) served locally by kiwix-serve. No internet required.
required_open_webui_version: 0.4.0
version: 2.1.0
license: MIT
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, urljoin

import requests
from pydantic import BaseModel, Field


def _html_to_text(html) -> str:
    """Accepts str or bytes; bytes are preferred so bs4 can sniff the charset."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "table", "sup", "footer", "nav"]):
            tag.decompose()
        # Drop common Wikipedia chrome/navigation boxes
        for sel in [".mw-editsection", ".navbox", ".infobox", ".reflist",
                    ".mw-references-wrap", "#mw-navigation", ".hatnote",
                    ".sidebar", ".metadata", ".catlinks"]:
            for tag in soup.select(sel):
                tag.decompose()
        text = soup.get_text(separator="\n")
    except Exception:
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


_ATOM = "{http://www.w3.org/2005/Atom}"


class Tools:
    class Valves(BaseModel):
        kiwix_url: str = Field(
            default="http://127.0.0.1:8090",
            description="Base URL of the local kiwix-serve instance",
        )
        max_results: int = Field(
            default=5, description="Number of search results to return"
        )
        max_article_chars: int = Field(
            default=12000,
            description="Maximum characters of article text returned to the model",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    def _list_books(self):
        """Return [{'book': stem, 'title': ..., 'summary': ...}] from the catalog."""
        r = requests.get(
            f"{self.valves.kiwix_url}/catalog/v2/entries",
            params={"count": "-1"},
            timeout=15,
        )
        r.raise_for_status()
        books = []
        for entry in ET.fromstring(r.text).findall(f"{_ATOM}entry"):
            stem = None
            for link in entry.findall(f"{_ATOM}link"):
                href = link.get("href", "")
                if link.get("type") == "text/html" and href.startswith("/content/"):
                    stem = href.split("/content/", 1)[1].strip("/")
            if stem:
                books.append(
                    {
                        "book": stem,
                        "title": (entry.findtext(f"{_ATOM}title") or "").strip(),
                        "summary": (entry.findtext(f"{_ATOM}summary") or "").strip(),
                    }
                )
        return books

    def list_offline_wikis(self) -> str:
        """
        List the wikis/books available in the local offline Kiwix library
        (e.g. Wikipedia, Wiktionary, Stack Exchange dumps).

        :return: One line per available book with its name and description
        """
        try:
            books = self._list_books()
        except Exception as e:
            return f"Error listing offline library: {e}"
        if not books:
            return "The offline library is empty or the Kiwix server is not running."
        lines = ["Available offline books:"]
        for b in books:
            lines.append(f"- {b['title']} (book: {b['book']}) — {b['summary']}")
        return "\n".join(lines)

    def search_offline_wikis(self, query: str) -> str:
        """
        Full-text search across ALL offline wikis in the local Kiwix library
        (offline Wikipedia and any other installed books). Returns article
        titles with the book they belong to. Use get_wiki_article to read one.

        :param query: Search terms, e.g. "battle of hastings" or "CRISPR gene editing"
        :return: Numbered list of matching articles with their book names and snippets
        """
        v = self.valves

        def run_search(params):
            r = requests.get(f"{v.kiwix_url}/search", params=params, timeout=25)
            r.raise_for_status()
            return ET.fromstring(r.text)

        base = {"pattern": query, "pageLength": v.max_results, "format": "xml"}
        items = []
        try:
            items = run_search(base).findall(".//item")
        except Exception:
            items = []
        if not items:
            # Fallback: some setups reject unfiltered multi-book search; query per book
            try:
                for b in self._list_books():
                    try:
                        root = run_search({**base, "books.name": b["book"],
                                           "pageLength": max(2, v.max_results // 2)})
                        items.extend(root.findall(".//item"))
                    except Exception:
                        continue
            except Exception as e:
                return f"Error searching offline library: {e}"
        if not items:
            return (
                f"No offline results for '{query}'. "
                "Try different or fewer keywords."
            )

        lines = [f"Offline library results for '{query}':"]
        for i, item in enumerate(items[: v.max_results * 2], 1):
            title = (item.findtext("title") or "").strip()
            link = item.findtext("link") or ""
            m = re.match(r"/content/([^/]+)/", link)
            book = m.group(1) if m else "?"
            desc = re.sub(r"\s+", " ", (item.findtext("description") or "")).strip()
            if len(desc) > 250:
                desc = desc[:250] + "..."
            lines.append(f"{i}. {title} [book: {book}]\n   {desc}")
        lines.append(
            "\nCall get_wiki_article with an exact title and its book name to read the full article."
        )
        return "\n".join(lines)

    def get_wiki_article(self, title: str, book: str = "") -> str:
        """
        Fetch the full text of an article from the offline Kiwix library.

        :param title: Exact article title, e.g. "Photosynthesis" or "Battle of Hastings"
        :param book: Book name the article belongs to, as shown in search results (e.g. "wikipedia_en_all_maxi_2026-02"). Optional; if omitted, all books are searched.
        :return: The article text (truncated if very long)
        """
        v = self.valves
        book = (book or "").strip()
        r = None
        try:
            if not book:
                # Resolve via search across all books
                s = requests.get(
                    f"{v.kiwix_url}/search",
                    params={"pattern": title, "pageLength": 1, "format": "xml"},
                    timeout=25,
                )
                if s.ok:
                    link = ET.fromstring(s.text).findtext(".//item/link")
                    if link:
                        r = requests.get(
                            urljoin(f"{v.kiwix_url}/", link.lstrip("/")),
                            timeout=30,
                            allow_redirects=True,
                        )
                if r is None or r.status_code == 404:
                    return (
                        f"Could not find '{title}' in the offline library. "
                        "Use search_offline_wikis first and pass the book name."
                    )
            else:
                path_title = quote(title.strip().replace(" ", "_"), safe="_()',.-")
                r = requests.get(
                    f"{v.kiwix_url}/content/{book}/{path_title}",
                    timeout=30,
                    allow_redirects=True,
                )
                if r.status_code == 404:
                    # Fall back to title suggestion lookup within the book
                    s = requests.get(
                        f"{v.kiwix_url}/suggest",
                        params={"content": book, "term": title},
                        timeout=15,
                    )
                    for hit in s.json() if s.ok else []:
                        if hit.get("kind") == "path" and hit.get("path"):
                            path = hit["path"]
                            # Gutenberg suggestions point at cover pages
                            # ("Title_cover.123"); the readable full text
                            # lives at "Title.123".
                            candidates = [path]
                            if "_cover." in path:
                                candidates.insert(0, path.replace("_cover.", "."))
                            for p in candidates:
                                r = requests.get(
                                    f"{v.kiwix_url}/content/{book}/{p}",
                                    timeout=30,
                                    allow_redirects=True,
                                )
                                if r.status_code != 404:
                                    break
                            break
                if r.status_code == 404:
                    return (
                        f"Article '{title}' not found in book '{book}'. "
                        "Use search_offline_wikis to find the exact title and book."
                    )
            r.raise_for_status()
        except Exception as e:
            return f"Error fetching article '{title}': {e}"

        text = _html_to_text(r.content)
        if len(text) > v.max_article_chars:
            text = (
                text[: v.max_article_chars]
                + f"\n\n[Article truncated at {v.max_article_chars} characters]"
            )
        src = f" (book: {book})" if book else ""
        return f"Offline article: {title}{src}\n\n{text}"
