# سماء — رفيقك اليومي في Sky: Children of the Light

<div align="center">

<img src="assets/creator.jpg" width="90" style="border-radius:50%;border:3px solid #7ee7d2" alt="𝐀𝐓𝐋𝐀𝐍𝐓𝐈𝐒">

### 𝐀𝐓𝐋𝐀𝐍𝐓𝐈𝐒

**صنع من قبل 𝐀𝐓𝐋𝐀𝐍𝐓𝐈𝐒**

</div>

---

## عن المشروع

موقع عربي متجاوب للاعبي Sky: Children of the Light:

- ⏱️ مؤقّتات الفعاليات (النافورة، الجدة، السلحفاة، متزلّجة الأحلام)
- 📜 المهام اليومية مع ترجمة عربية
- 🕯️ الروح المسافرة مع التكلفة
- 🧮 حاسبة الشموع
- 📅 جدول المواسم والأحداث
- 📰 أخبار Sky الرسمية من Steam

## التحديث التلقائي

- GitHub Actions يشتغل كل **15 دقيقة** ويحدّث `data/live.json` ثم ينشر الموقع.
- الواجهة تسحب `data/live.json` كل **60 ثانية** بينما الصفحة مفتوحة.
- لا حاجة لأي تدخل يدوي.

## النشر على GitHub Pages

1. **Settings → Actions → General** → اختر **Read and write permissions**
2. **Settings → Pages** → اختر **GitHub Actions** كمصدر
3. **Actions** → شغّل `Update Sky data and deploy` يدويًا مرة واحدة

الرابط: `https://4ioo.github.io/-ATLANTIS/`

## التشغيل المحلي

```bash
python -m http.server 8000