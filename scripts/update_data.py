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
    "Spinning Mentor": "المعلّم الدوّار",
    "Daydream Forester": "حارس أحلام اليقظة",
    "Greeting Shaman": "الشامان المرحّب",
    "Provoking Performer": "المؤدي المستفز",
    "Saluting Captain": "القبطان المُحيّي",
    "Backflipping Champion": "بطل الشقلبة الخلفية",
    "Handstanding Thrillseeker": "الباحث عن الإثارة",
    "Laughing Light Catcher": "ملتقط الضوء الضاحك",
    "Crab Whisperer": "همّاس السلطعون",
    "Slumbering Shipwright": "بنّاء السفن النائم",
    "Hairtousle Teen": "المراهق الأشعث",
    "Festival Spin Dancer": "راقص المهرجان الدوّار",
    "Chuckling Scout": "الكشّاف الضاحك",
    "Marching Adventurer": "المغامر المسير",
    "Playfighting Herbalist": "عشّاب المعارك",
    "Scarecrow Farmhand": "عامل الحقل الفزّاعة",
    "Lookout Scout": "الكشّاف المراقب",
    "Troupe Juggler": "بهلوان الفرقة",
    "Ceremonial Worshiper": "المُتعبد الاحتفالي",
    "Rallying Thrillseeker": "الباحث عن الإثارة المتحمس",
    "Star Collector": "جامع النجوم",
    "Praying Acolyte": "الخادم المصلّي",
    "Stretching Lamplighter": "مشعل المصابيح المتمدد",
    "Bowing Medalist": "الحاصل على الميدالية المُنحني",
    "Proud Victor": "المنتصر الفخور",
    "Manta Whisperer": "همّاس المانتا",
    "Turtle Whisperer": "همّاس السلحفاة",
    "Sightseer": "السائح",
    "Flipping Jester": "المهرج القافز",
    "Nodding Muralist": "رسّام الجداريات المُومئ",
    "Indifferent Alchemist": "الخيميائي غير المبالي",
    "Thoughtful Director": "المخرج المتأمل",
    "Reassuring Ranger": "الحارس المُطمئن",
    "Hiking Grouch": "المتشائم المتجول",
    "Fruitful Empath": "المتعاطف المثمر",
    "Sparkler Parent": "الوالد المتلألئ",
    "Modest Dancer": "الراقص المتواضع",
    "Blushing Prospector": "المنقّب الخجول",
    "Apologetic Lumberjack": "الحطّاب الاعتذاري",
    "Reserved Physician": "الطبيب المتحفظ",
    "Chill Sunbather": "المستلقي الهادئ",
    "Wise Grandparent": "الجد الحكيم",
    "Veteran's Guide": "دليل المحاربين القدامى",
    "Twirling Champion": "البطل الدوّار",
    "Crab Walker": "ماشي السلطعون",
    "Snoozing Carpenter": "النجار النائم",
    "Peeking Postman": "ساعي البريد المتلصص",
    "Bearhug Hermit": "الناسك المُعانق",
    "Bumbling Boatswain": "الملاح الأخرق",
}

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        text=data.strip()
        if text: self.parts.append(text)

def fetch(url, timeout=20, accept="application/json, text/html;q=0.9, */*;q=0.8"):
    req=urllib.request.Request(url, headers={
        "User-Agent":"SkyMateCommunityTool/1.0",
        "Accept":accept,
        "Accept-Language":"en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def fetch_json(url):
    return json.loads(fetch(url).decode("utf-8", errors="replace"))

def get_pt_date(now_utc):
    return now_utc.astimezone(PT).date()

def has_arabic(text):
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))

def translate_short(text, max_len=400):
    if not text or not text.strip():
        return ""
    text = text.strip()[:max_len]
    if has_arabic(text):
        return text
    for attempt in range(3):
        try:
            result = GoogleTranslator(source="en", target="ar").translate(text)
            if result and has_arabic(result):
                return result
        except Exception as exc:
            print(f"WARN: translate attempt {attempt+1} failed: {exc}", file=sys.stderr)
            time.sleep(2 + attempt)
    return text

def translate_quest(text):
    if text in QUEST_TRANSLATIONS: return QUEST_TRANSLATIONS[text]
    m=re.match(r"^Collect (\d+) pieces? of [Ll]ight$", text)
    if m: return f"اجمع {m.group(1)} قطعة من الضوء"
    m=re.match(r"^Visit (?:the )?(.+)$", text, re.I)
    if m: return "زُر " + m.group(1)
    m=re.match(r"^Meditate at (?:the )?(.+)$", text, re.I)
    if m: return "تأمّل عند " + m.group(1)
    return text

def parse_daily_guide_quests(raw):
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

def update_quests(doc, now_utc):
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
        print(f"WARN: quest API failed: {exc}", file=sys.stderr)
        try:
            raw=fetch(guide_url,timeout=25,accept="text/html,*/*;q=0.8").decode("utf-8",errors="replace")
            quests,quest_date=parse_daily_guide_quests(raw)
            if len(quests)<4:
                raise ValueError(f"only parsed {len(quests)} daily tasks")
            chosen_source=guide_url
        except Exception as fallback_exc:
            print(f"WARN: fallback failed: {fallback_exc}",file=sys.stderr)
            return False
    date_pt=quest_date or get_pt_date(now_utc).isoformat()
    changed=(old_quest_date != date_pt or old_quest_list != quests or doc.get("quest_data_source") != chosen_source)
    doc["daily_quests_date_pacific"]=date_pt
    doc["daily_quests_en"]=quests
    doc["daily_quests_ar"]=[translate_quest(q) for q in quests]
    doc["quest_source"]=guide_url
    doc["quest_api_source"]=url
    doc["quest_data_source"]=chosen_source
    print(f"Daily quests fetched: {len(quests)} items")
    return changed

def update_timeline(doc, now_utc):
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
                detail = f"باقي {days} أيام" if days != 1 else "باقي يوم واحد"
            else:
                m = re.match(r"^(.+?)\s+ends\s+today[.!]?$", text, re.I)
                if m:
                    title = m.group(1).strip()
                    detail = "ينتهي اليوم"
                else:
                    m = re.match(r"^(.+?)\s+(starts|releases)\s+in\s+(\d+)\s+days?[.!]?$", text, re.I)
                    if m:
                        title = m.group(1).strip()
                        verb = "يبدأ" if m.group(2).lower() == "starts" else "يصدر"
                        days = int(m.group(3))
                        detail = f"{verb} بعد {days} أيام"
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
            raise ValueError("no countdowns found")
        old = doc.get("timeline", [])
        changed = old != entries
        doc["timeline"] = entries[:12]
        doc["timeline_source"] = url
        doc["timeline_updated_utc"] = now_utc.isoformat().replace("+00:00", "Z")
        print(f"Timeline: {len(entries)} items")
        return changed
    except Exception as exc:
        print(f"WARN: timeline failed: {exc}", file=sys.stderr)
        return False

def update_news(doc, now_utc):
    url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2325290&count=8&maxlength=0&format=json"
    try:
        payload = fetch_json(url)
        items = payload.get("appnews", {}).get("newsitems", [])
        if not isinstance(items, list) or not items:
            raise ValueError("no news")
        old_news = doc.get("news", [])
        old_by_url = {n.get("url"): n for n in old_news if isinstance(n, dict)}
        news = []
        for item in items[:8]:
            title = html.unescape(str(item.get("title", "")).strip())
            item_url = str(item.get("url", "")).strip()
            if not title or not item_url.startswith("https://"):
                continue
            contents = html.unescape(str(item.get("contents", "")))
            contents = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", contents)
            contents = re.sub(r"(?is)<br\s*/?>", "\n", contents)
            contents = re.sub(r"(?is)</p>", "\n\n", contents)
            contents = re.sub(r"(?is)<[^>]+>", " ", contents)
            contents = re.sub(r"\[[^\]]*\]", " ", contents)
            contents = re.sub(r"https?://\S+", " ", contents)
            contents = re.sub(r"[ \t]+", " ", contents)
            contents = re.sub(r"\n{3,}", "\n\n", contents).strip()
            published = None
            try:
                published = dt.datetime.fromtimestamp(int(item.get("date", 0)), UTC).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OSError):
                pass
            summary_en = contents[:280] if contents else ""
            old_item = old_by_url.get(item_url)
            if (old_item and old_item.get("title") == title
                and old_item.get("summary_en") == summary_en
                and old_item.get("title_ar") and has_arabic(old_item.get("title_ar"))
                and old_item.get("summary_ar") and has_arabic(old_item.get("summary_ar"))):
                news.append(old_item)
                print(f"Cached: {title[:50]}")
                continue
            title_ar = translate_short(title, max_len=200)
            time.sleep(1.5)
            summary_ar = translate_short(summary_en, max_len=400) if summary_en else ""
            time.sleep(1.5)
            news.append({
                "title": title,
                "title_ar": title_ar,
                "url": item_url,
                "published_utc": published,
                "summary_en": summary_en,
                "summary_ar": summary_ar,
                "full_en": contents,
            })
            print(f"Translated: {title[:50]}")
        if not news:
            raise ValueError("no usable news")
        changed = old_news != news
        doc["news"] = news
        doc["news_source"] = "https://store.steampowered.com/news/app/2325290/"
        doc["news_updated_utc"] = now_utc.isoformat().replace("+00:00", "Z")
        print(f"News: {len(news)} items")
        return changed
    except Exception as exc:
        print(f"WARN: news failed: {exc}", file=sys.stderr)
        return False

def update_spirit(doc, now_utc):
    """Fetch current traveling spirit from skygame-data assets."""
    base = "https://unpkg.com/skygame-data@latest/assets"
    try:
        ts_data = fetch_json(f"{base}/traveling-spirits.json")
    except Exception as exc:
        print(f"WARN: couldn't fetch traveling-spirits.json: {exc}", file=sys.stderr)
        return False

    items = ts_data.get("items", []) if isinstance(ts_data, dict) else []
    if not items:
        print("WARN: no traveling-spirits items", file=sys.stderr)
        return False

    parsed = []
    for it in items:
        try:
            d = dt.datetime.strptime(it["date"], "%Y-%m-%d").replace(tzinfo=PT)
            parsed.append((d, it))
        except (KeyError, ValueError):
            continue
    if not parsed:
        return False
    parsed.sort(key=lambda x: x[0])

    now_pt = now_utc.astimezone(PT)
    current = None
    upcoming = None
    for start_dt, it in reversed(parsed):
        end_dt = start_dt + dt.timedelta(days=4)
        if start_dt <= now_pt < end_dt:
            current = (start_dt, end_dt, it)
            break
        elif start_dt > now_pt and upcoming is None:
            upcoming = (start_dt, end_dt, it)

    chosen = current or upcoming
    if not chosen:
        last = parsed[-1]
        chosen = (last[0], last[0] + dt.timedelta(days=4), last[1])
    start_dt, end_dt, item = chosen

    spirit_guid = item.get("spirit")
    spirit_name = None
    image_url = None

    if spirit_guid:
        try:
            spirits_data = fetch_json(f"{base}/spirits.json")
            for s in spirits_data.get("items", []):
                if s.get("guid") == spirit_guid:
                    spirit_name = s.get("name")
                    image_url = s.get("imageUrl")
                    break
        except Exception as exc:
            print(f"WARN: couldn't fetch spirits.json: {exc}", file=sys.stderr)

    if not spirit_name:
        try:
            eis = fetch_json(f"{base}/event-instance-spirits.json")
            for e in eis.get("items", []):
                if e.get("guid") == spirit_guid or e.get("spirit") == spirit_guid:
                    name = e.get("name")
                    if name:
                        spirit_name = name
                        break
        except Exception:
            pass

    if not spirit_name:
        spirit_name = "Traveling Spirit"

    name_ar = SPIRIT_TRANSLATIONS.get(spirit_name, spirit_name)

    old_spirit = doc.get("spirit", {})
    old_start = old_spirit.get("start_utc")
    new_start = start_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

    spirit = {
        "name": spirit_name,
        "name_ar": name_ar,
        "start_utc": new_start,
        "end_utc": end_dt.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "source_kind": "skygame-data",
        "source_url": "https://unpkg.com/skygame-data@latest/assets/traveling-spirits.json",
        "status_label": "الروح الحالية" if current else "الروح القادمة",
        "last_updated": now_utc.isoformat().replace("+00:00", "Z"),
    }

    if image_url:
        spirit["image_url"] = image_url

    if old_spirit.get("name") == spirit_name:
        for key in ("prices", "cosmetics", "prices_note", "location_ar", "image_path"):
            if old_spirit.get(key):
                spirit[key] = old_spirit[key]

    doc["spirit"] = spirit
    changed = old_start != new_start or old_spirit.get("name") != spirit_name
    print(f"Traveling Spirit: {spirit_name} ({start_dt.date()} to {end_dt.date()})")
    return changed

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
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Wrote data/live.json")
    else:
        print("No changes")

if __name__=="__main__":
    main()
