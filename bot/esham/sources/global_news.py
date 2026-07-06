"""Küresel finansal haber RSS kaynağı."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
import urllib.request
import urllib.error

from ..config import get_logger

log = get_logger(__name__)

@dataclass
class GlobalNewsItem:
    title: str
    link: str
    pub_date: str = ""

class GlobalNewsSource:
    URL = "https://www.forexlive.com/feed/news"

    def fetch_latest(self) -> list[GlobalNewsItem]:
        """RSS feed üzerinden son haber başlıklarını çeker."""
        items: list[GlobalNewsItem] = []
        try:
            req = urllib.request.Request(self.URL, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=15).read()
            root = ET.fromstring(response)
            
            # Tipik RSS 2.0 yapısı: channel -> item
            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")
                pub_date = item.findtext("pubDate") or ""
                
                if title and link:
                    items.append(GlobalNewsItem(title=title.strip(), link=link.strip(), pub_date=pub_date.strip()))
                    
        except Exception as exc:
            log.warning("GlobalNewsSource RSS okunamadı: %s", exc)
            
        return items
