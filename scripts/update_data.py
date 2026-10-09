#!/usr/bin/env python3
"""Refresh Sky Mate's public data from community sources."""
from __future__ import annotations
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "live.json"
PT = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

QUEST_TRANSLATIONS = {
    "Wave to a player": "لوّح للاعب",
    "Find the candles at the end of the rainbow in the Vault of Knowledge": "اعثر على الشموع عند نهاية قوس قزح في قبو المعرفة",
    "Catch the wandering lights in the Upper Vault": "التقط الأضواء المتجوّلة في الجزء العلوي من قبو المعرفة",
    "Meditate at the Temple of the Vault": "تأمّل عند معبد قبو المعرفة",
    "Collect 30 pieces of light": "اجمع 30 قطعة من الضوء",
    "Spend time with a friend": "اقضِ بعض الوقت مع صديق",
    "Hug a friend": "عانق صديقًا",
    "Hold hands with a friend": "أمسك بيد صديق",
    "Send a gift of light to a friend": "أرسل هدية نور إلى صديق",
    "Make a new acquaintance": "تعرّف على لاعب جديد",
    "Admire the beauty of the Sanctuary Islands": "تأمّل جمال جزر الملاذ"
}
SPIRIT_TRANSLATIONS = {
    "Talented Builder": "البنّاء الموهوب",
    "Light Whisperer": "همّاس الضوء",
    "Confetti Cousin": "قريب قصاصات الورق",
    "Admiring Actor": "الممثل المعجب",
    "Dancing Performer": "المؤدي الراقص",
}

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        text=data.strip()
        if text: self.parts.append(text)

def fetch(url: str, timeout: int = 20, accept: str = "application/json, text/html;q=0.9, */*;q=0.8") -> bytes:
    req=urllib.request.Request(url, headers={
        "User-Agent":"SkyMateCommunityTool/1.0",
        "Accept":accept,
        "Accept-Language":"en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def fetch_json(url: str):
    return json.loads(fetch(url).decode("utf-8", errors="replace"))

def get_pt_date(now_utc: dt.datetime) -> dt.date:
    return now_utc.astimezone(PT).date()

def translate_text(text: str) -> str:
    if not text or not text.strip():
        return ""
    try:
        return GoogleTranslator(source="en", target="ar").translate(text[:4900]) or text
    except Exception as exc:
        print(f"WARN: translation failed: {exc}", file=sys.stderr)
        return text

def translate_batch(texts: list) -> list:
    if not texts:
        return []
    cleaned = [t[:4900] if t else "" for t in texts]
    try:
        result = GoogleTranslator(source="en", target="ar").translate_batch(cleaned)
        return result or cleaned
    except Exception as exc:
        print(f"WARN: batch translation failed: {exc}", file=sys.stderr)
        return cleaned

def translate_quest(text: str) -> str:
    if text in QUEST_TRANSLATIONS: return QUEST_TRANSLATIONS[text]
    m=re.match(r"^Collect (\d+) pieces? of [Ll]ight$", text)
    if m: return f"اجمع {m.group(1)} قطعة من الضوء"
    m=re.match(r"^Visit (?:the )?(.+)$", text, re.I)
    if m: return "زُر " + m.group(1)
    m=re.match(r"^Meditate at (?:the )?(.+)$", text, re.I)
    if m: return "تأمّل عند " + m.group(1)
    return text

def parse_daily_guide_quests(raw: str):
    parser = TextExtractor()
    parser.feed(raw)
    parts = [html.unescape(re.sub(r"\s+", " ", part)).strip() for part in parser.parts]
    try:
        start = next(i for i, part in enumerate(parts) if part.casefold() == "quests")
    except StopIteration:
        return [], None
    quests = []
    quest_date = None
    for part in parts[max(0, start - 4):start]:
        m = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{1,2}\s+[A-Za-z]+\s+20\d{2}", part)
        if m:
            try:
                quest_date = dt.datetime.strptime(m.group(0), "%A, %d %B %Y").date().isoformat()
            except ValueError:
                pass
    for part in parts[start + 1:]:
        if part.casefold().startswith("treasure candles"):
            break
        if re.fullmatch(r"\d+\.?", part):
            continue
        m = re.match(r"^\d+\s*[.)]\s*(.+)$", part)
        candidate = m.group(1).strip() if m else part
        if not candidate or candidate.casefold() in {"view", "more", "button", "today", "jump to a date"}:
            continue
        if candidate not in quests:
            quests.append(candidate)
        if len(quests) == 4:
            break
    return quests, quest_date

def update_quests(doc: dict, now_utc: dt.datetime) -> bool:
    url="https://quest.skyapi.shhy.in/?lang=en"
    guide_url="https://thatskyapplication.com/daily-guides"
    quests = []
    quest_date = None
    old_quest_date = doc.get("daily_quests_date_pacific")
    old_quest_list = doc.get("daily_quests_en")
    chosen_source = url
    try:
        payload=fetch_json(url)
        if isinstance(payload, dict):
            payload=payload.get("quests", payload.get("data", []))
        if not isinstance(payload, list) or len(payload) < 4:
            raise ValueError("unexpected daily quest payload")
        quests=[]
        for item in payload[:4]:
            if isinstance(item,str):
                quests.append(item.strip())
            elif isinstance(item,dict):
                text_value=next((item.get(k) for k in ("text","title","name","quest","description") if isinstance(item.get(k),str) and item.get(k).strip()),"")
                if not text_value: raise ValueError("daily quest object missing text")
                quests.append(text_value.strip())
            else:
                raise ValueError("unexpected daily quest item")
        if not all(quests): raise ValueError("daily quest payload contains empty entries")
    except Exception as exc:
        print(f"WARN: quest API failed, trying daily guide fallback: {exc}", file=sys.stderr)
        try:
            raw=fetch(guide_url,timeout=25,accept="text/html,*/*;q=0.8").decode("utf-8",errors="replace")
            quests,quest_date=parse_daily_guide_quests(raw)
            if len(quests)<4:
                raise ValueError(f"only parsed {len(quests)} daily tasks from guide")
            chosen_source=guide_url
        except Exception as fallback_exc:
            print(f"WARN: daily guide fallback failed: {fallback_exc}",file=sys.stderr)
            return False
    date_pt=quest_date or get_pt_date(now_utc).isoformat()
    changed=(old_quest_date != date_pt or old_quest_list != quests or doc.get("quest_data_source") != chosen_source)
    doc["daily_quests_date_pacific"]=date_pt
    doc["daily_quests_en"]=quests
    doc["daily_quests_ar"]=[translate_quest(q) for q in quests]
    doc["quest_source"]=guide_url
    doc["quest_api_source"]=url
    doc["quest_data_source"]=chosen_source
    print(f"Daily quests fetched: {len(quests)} items for {date_pt} PT")
    return changed

def update_spirit(doc: dict, now_utc: dt.datetime) -> bool:
    url = "https://unpkg.com/skygame-data@latest/assets/everything.json"
    try:
        payload = fetch_json(url)
    except Exception as exc:
        print(f"WARN: couldn't fetch skygame-data: {exc}", file=sys.stderr)
        return False
    now_pt = now_utc.astimezone(PT)
    candidates = []
    if isinstance(payload, dict):
        traveling = payload.get("travelingSpirits") or payload.get("traveling_spirits") or []
        if isinstance(traveling, list):
            for s in traveling:
                if not isinstance(s, dict): continue
                start = s.get("startDate") or s.get("start") or s.get("start_utc")
                end = s.get("endDate") or s.get("end") or s.get("end_utc")
                if not start or not end: continue
                try:
                    start_dt = dt.datetime.fromisoformat(str(start).replace("Z","+00:00"))
                    end_dt = dt.datetime.fromisoformat(str(end).replace("Z","+00:00"))
                except Exception:
                    continue
                if start_dt <= now_utc < end_dt:
                    candidates.append((0, s, start_dt, end_dt))
                elif start_dt > now_utc:
                    delta = (start_dt - now_utc).total_seconds()
                    candidates.append((1, s, start_dt, end_dt))
    if not candidates:
        print("WARN: no traveling spirit in skygame-data", file=sys.stderr)
        return False
    candidates.sort(key=lambda x: (x[0], x[2]))
    _, s, start_dt, end_dt = candidates[0]
    name = s.get("name") or s.get("name_en") or "Unknown Spirit"
    name_ar = SPIRIT_TRANSLATIONS.get(name, name)
    image = s.get("image") or s.get("imageUrl") or s.get("image_url") or ""
    prices = s.get("prices") or s.get("costs") or {}
    candles = prices.get("candles") or prices.get("regularCandles") or s.get("candles")
    hearts = prices.get("hearts") or s.get("hearts")
    ascended = prices.get("ascended") or prices.get("ascendedCandles") or s.get("ascended")
    old_identity = (doc.get("spirit",{}).get("name"), doc.get("spirit",{}).get("start_utc"))
    new_identity = (name, start_dt.astimezone(UTC).isoformat().replace("+00:00","Z"))
    spirit = {
        "name": name,
        "name_ar": name_ar,
        "start_utc": start_dt.astimezone(UTC).isoformat().replace("+00:00","Z"),
        "end_utc": end_dt.astimezone(UTC).isoformat().replace("+00:00","Z"),
        "source_kind": "skygame-data",
        "status_label": "الروح الحالية" if start_dt <= now_utc < end_dt else "الروح القادمة",
        "last_updated": now_utc.isoformat().replace("+00:00","Z"),
    }
    if image:
        spirit["image_url"] = image
    if candles or hearts or ascended:
        spirit["prices"] = {
            "candles": candles or 0,
            "hearts": hearts or 0,
            "ascended": ascended or 0,
        }
    doc["spirit"] = spirit
    changed = old_identity != new_identity
    print(f"Traveling Spirit: {name} ({start_dt.date()} to {end_dt.date()})")
    return changed

def update_timeline(doc: dict, now_utc: dt.datetime) -> bool:
    url = "https://thatskyapplication.com/daily-guides"
    try:
        raw = fetch(url, timeout=25, accept="text/html,*/*;q=0.8").decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(raw)
        entries = []
        seen = set()
        for piece in parser.parts:
            text = html.unescape(re.sub(r"\s+", " ", piece)).strip(" \t\r\n•")
            title = detail = None
            m = re.match(r"^(\d+)\s+days?\s+left\s+in\s+(.+?)(?:\s+event)?[.!]?$", text, re.I)
            if m:
                days, name = int(m.group(1)), m.group(2).strip()
                title = name
                detail = f"باقي {days} أيام بحسب دليل المجتمع" if days != 1 else "باقي يوم واحد بحسب دليل المجتمع"
            else:
                m = re.match(r"^(.+?)\s+ends\s+today[.!]?$", text, re.I)
                if m:
                    title = m.group(1).strip()
                    detail = "ينتهي اليوم بحسب دليل المجتمع"
                else:
                    m = re.match(r"^(.+?)\s+(starts|releases)\s+in\s+(\d+)\s+days?[.!]?$", text, re.I)
                    if m:
                        title = m.group(1).strip()
                        verb = "يبدأ" if m.group(2).lower() == "starts" else "يصدر"
                        days = int(m.group(3))
                        detail = f"{verb} بعد {days} أيام بحسب دليل المجتمع"
            if title and detail:
                key = (title.casefold(), detail)
                if key in seen: continue
                seen.add(key)
                translations = {
                    "radiance event": "حدث الإشعاع",
                    "radiance": "حدث الإشعاع",
                    "days of moonlight": "أيام ضوء القمر",
                    "the 35.0 update": "تحديث 35.0",
                    "the new season": "الموسم الجديد",
                    "days of mischief": "أيام الشقاوة",
                    "community eden run": "تحدّي إيدن الجماعي",
                }
                entries.append({"title": title, "title_ar": translations.get(title.casefold(), title), "detail": detail, "source_url": url})
        if not entries:
            raise ValueError("no recognized event countdowns in the current guide")
        old = doc.get("timeline", [])
        changed = old != entries
        doc["timeline"] = entries[:12]
        doc["timeline_source"] = url
        doc["timeline_updated_utc"] = now_utc.isoformat().replace("+00:00", "Z")
        print(f"Community event timeline fetched: {len(entries)} items")
        return changed
    except Exception as exc:
        print(f"WARN: couldn't refresh event timeline: {exc}", file=sys.stderr)
        return False

def update_news(doc: dict, now_utc: dt.datetime) -> bool:
    url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2325290&count=8&maxlength=450&format=json"
    try:
        payload = fetch_json(url)
        items = payload.get("appnews", {}).get("newsitems", [])
        if not isinstance(items, list) or not items:
            raise ValueError("Steam API returned no news items")
        raw_items = []
        for item in items[:8]:
            title = html.unescape(str(item.get("title", "")).strip())
            item_url = str(item.get("url", "")).strip()
            if not title or not item_url.startswith("https://"):
                continue
            contents = html.unescape(str(item.get("contents", "")))
            contents = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", contents)
            contents = re.sub(r"(?is)<[^>]+>", " ", contents)
            contents = re.sub(r"\[[^\]]*\]", " ", contents)
            contents = re.sub(r"https?://\S+", " ", contents)
            contents = re.sub(r"\s+", " ", contents).strip()
            published = None
            try:
                published = dt.datetime.fromtimestamp(int(item.get("date", 0)), UTC).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OSError):
                pass
            raw_items.append({
                "title": title,
                "url": item_url,
                "published_utc": published,
                "summary": contents[:190],
            })
        if not raw_items:
            raise ValueError("Steam news items did not contain usable headlines")
        batch = []
        for r in raw_items:
            batch.append(r["title"])
            batch.append(r["summary"] or "")
        translated = translate_batch(batch)
        news = []
        for i, r in enumerate(raw_items):
            title_ar = translated[i*2] if i*2 < len(translated) else r["title"]
            summary_ar = translated[i*2+1] if i*2+1 < len(translated) else r["summary"]
            news.append({
                "title": r["title"],
                "title_ar": title_ar,
                "url": r["url"],
                "published_utc": r["published_utc"],
                "summary": r["summary"],
                "summary_ar": summary_ar,
            })
        changed = doc.get("news", []) != news
        doc["news"] = news
        doc["news_source"] = "https://store.steampowered.com/news/app/2325290/"
        doc["news_updated_utc"] = now_utc.isoformat().replace("+00:00", "Z")
        print(f"Official Steam announcements fetched & translated: {len(news)} items")
        return changed
    except Exception as exc:
        print(f"WARN: couldn't refresh official Steam news: {exc}", file=sys.stderr)
        return False

def main():
    now=dt.datetime.now(UTC).replace(microsecond=0)
    if DATA_FILE.exists():
        try: doc=json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception: doc={}
    else: doc={}
    changed=False
    changed |= update_quests(doc,now)
    changed |= update_spirit(doc,now)
    changed |= update_timeline(doc,now)
    changed |= update_news(doc,now)
    if changed:
        doc["last_updated_utc"]=now.isoformat().replace("+00:00","Z")
        DATA_FILE.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Wrote refreshed data to data/live.json")
    else:
        print("No material data change detected")

if __name__=="__main__":
    main()
