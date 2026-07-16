# Anki Vocab Bot (Telegram + Groq + AnkiConnect)

Bot Telegram: bạn gửi 1 từ tiếng Anh → bot gọi Groq API giải nghĩa,
lấy MP3 từ trang Cambridge nếu có → tự động tạo thẻ trong Anki (qua addon
AnkiConnect, cần Anki đang mở trên cùng máy chạy bot).

## 1. Chuẩn bị

### a) Cài AnkiConnect trong Anki
1. Mở Anki → **Tools → Add-ons → Get Add-ons...**
2. Nhập code: `2055492159`
3. Restart Anki. Từ giờ khi Anki mở, nó tự chạy 1 server local ở
   `http://127.0.0.1:8765`.

### b) Lấy Telegram Bot Token
- Chat với [@BotFather](https://t.me/BotFather) trên Telegram → `/newbot`
  → làm theo hướng dẫn → copy token dạng `123456:ABC-DEF...`.

### c) Lấy Groq API Key
- Vào https://console.groq.com/keys → tạo API key.

## 2. Cài đặt

```bash
cd anki_bot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# rồi mở .env, điền TELEGRAM_BOT_TOKEN và GROQ_API_KEY
```

## 3. Chạy

1. **Mở Anki trước** (để AnkiConnect server sống).
2. Chạy bot:
   ```bash
   python bot.py
   ```
3. Trên Telegram, mở chat với bot bạn vừa tạo → gõ `/start` → gửi thử
   1 từ, ví dụ: `serendipity`.

Bot sẽ tự tạo deck (`Vocab AI` theo mặc định) và note type (`Vocab (AI)`)
trong Anki nếu chưa có, với các field: Word, Phonetic, PartOfSpeech,
MeaningVi, MeaningEn, ExampleEn, ExampleVi, Audio. Field `Word` sẽ tự
gộp luôn base word khi có, nên không cần field riêng cho BaseWord.

## 4. Tuỳ chỉnh

- **Đổi tên deck/note type**: sửa `ANKI_DECK_NAME`, `ANKI_MODEL_NAME` trong `.env`.
- **Đổi model Groq**: sửa `GROQ_MODEL` trong `.env` (ví dụ
  `llama-3.3-70b-versatile`).
- **Schema tối giản**: bot luôn lưu nguyên từ người dùng nhập ở field `Word`,
  và nếu có base word thì nó được gộp ngay trong field `Word` luôn. Các field
  khác giữ như đề xuất của bạn: `Phonetic`, `PartOfSpeech`, `MeaningVi`,
  `MeaningEn`, `ExampleEn`, `ExampleVi`, `Audio`.
- **Audio Cambridge**: bot sẽ tự mở trang
  `https://dictionary.cambridge.org/vi/dictionary/english/<tu-vung>` để lấy
  file `.mp3` phát âm và đính kèm vào field `Audio` trong Anki. Khi từ là dạng
  biến đổi, bot sẽ ưu tiên tra audio theo `BaseWord` nhưng vẫn giữ `Word`
  gốc người dùng đã gửi.
- **Giới hạn ai được dùng bot**: điền Telegram user ID (không phải username)
  vào `ALLOWED_TELEGRAM_USER_IDS` trong `.env`, cách nhau dấu phẩy. Lấy user
  ID bằng cách chat với bot @userinfobot.
- **Sửa layout thẻ / thêm field** (ví dụ: thêm ảnh minh hoạ, âm thanh phát
  âm): sửa `FIELDS`, `FRONT_TEMPLATE`, `BACK_TEMPLATE` trong `anki_client.py`
  — lưu ý nếu note type đã tồn tại trong Anki rồi thì sửa code sẽ không tự
  cập nhật lại note type cũ, cần xoá note type đó trong Anki để bot tạo lại,
  hoặc tự sửa tay trong Anki.

## 5. Chạy nền lâu dài (tuỳ chọn)

Nếu muốn bot chạy nền, có thể dùng `pm2`, `systemd` (Linux), hoặc Task
Scheduler (Windows) để tự khởi động `python bot.py` cùng máy. Vì bot cần
Anki đang mở, cách này chỉ hợp lý nếu máy bạn luôn bật Anki sẵn.

## Cấu trúc project

```
anki_bot/
├── bot.py             # entrypoint, xử lý Telegram
├── ai_client.py   # gọi AI API, parse JSON nghĩa từ
├── anki_client.py     # gọi AnkiConnect, tạo deck/note type/thẻ
├── requirements.txt
├── .env.example
└── README.md
```
