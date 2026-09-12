# AI Tech Uz — Auto Post Bot

O'zbek tilidagi Telegram kanal ([@aitechnewsuz](https://t.me/aitechnewsuz)) uchun avtomatik kontent generatsiya va joylash tizimi. Bot har kuni haqiqiy, joriy texnologiya/AI/dasturlash yangiliklarini topib, ularni o'zbek tiliga izohlab, rasm yoki video bilan birga kanalga joylaydi.

## Qanday ishlaydi

1. **Yangilik qidirish** — 9 ta manbadan (Hacker News, TechCrunch, va Apple, Samsung, OpenAI, Google DeepMind, Google AI, SpaceX, The Robot Report kabi rasmiy/yetakchi manbalardan) trenddagi, haqiqiy tech yangiliklarni oladi
2. **Kontent generatsiya** — Google Gemini API orqali yangilikni o'zbek tiliga, tushunarli va qisqa post shaklida izohlaydi (fakt to'qib chiqarmasdan, faqat berilgan sarlavhaga asoslanib)
3. **Media qidirish** — avval maqolaning o'zidan (`og:image` / `og:video`), topilmasa Unsplash'dan mavzuga mos rasm topadi
4. **Joylash** — Telegram Bot API orqali tayyor postni, kanal linki bilan birga, kanalga joylaydi
5. **Takrorlanmaslik** — joylangan yangiliklar ro'yxati saqlanadi, bir xil yangilik ikki marta joylanmaydi
6. **Barqarorlik** — Gemini vaqtincha band bo'lsa (503), avtomatik qayta urinadi (exponential backoff bilan)

## Texnologiyalar

- Python
- Google Gemini API (kontent generatsiya)
- Telegram Bot API (joylash)
- Unsplash API (rasm qidirish)
- Hacker News API, TechCrunch va boshqa rasmiy RSS manbalar (yangilik manbalari)
- GitHub Actions (har kuni avtomatik ishga tushirish, serversiz)

## Sozlash

`.env` fayl yarating:

```
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL=@your_channel
UNSPLASH_ACCESS_KEY=...
```

```bash
pip install -r requirements.txt
python auto_post_bot.py
```

## Avtomatlashtirish

`.github/workflows/post.yml` GitHub Actions orqali skriptni har kuni belgilangan vaqtda avtomatik ishga tushiradi — server yoki doimiy yoqilgan kompyuter talab qilinmaydi. Joylangan yangiliklar ro'yxati (`posted_story_ids.txt`) har safar avtomatik ravishda repository'ga qaytarib yoziladi.

## Qo'shimcha: buyruq orqali boshqarish (ixtiyoriy)

`bot_listener.py` — lokal kompyuterda ishga tushirilganda, botga `/post` deb yozilganda darhol yangi post yaratib, kanalga joylaydigan qo'shimcha rejim.
