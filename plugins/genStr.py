import os
import json
import time
import asyncio

from asyncio.exceptions import TimeoutError

from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    SessionPasswordNeeded, FloodWait,
    PhoneNumberInvalid, ApiIdInvalid,
    PhoneCodeInvalid, PhoneCodeExpired
)


API_TEXT = """🙋‍♂ Xin chào {},

Tôi là một bot tạo chuỗi phiên đăng nhập.

Để tạo phiên chuỗi, hãy gửi cho tôi `API_ID` 🐿
"""
HASH_TEXT = "Ok bây giờ Gửi `API_HASH` của bạn để tiếp tục.\n\nNhấn /cancel để Hủy bỏ.🐧"
PHONE_NUMBER_TEXT = (
    "📞__ Bây giờ hãy gửi số điện thoại đăng ký tài khoản để Tiếp tục"
    " bao gồm mã Quốc gia.__\n**VD:** `++84123456789`\n\n"
    "Nhấn /cancel để Hủy bỏ."
)



@Client.on_message(filters.private & filters.command("start"))
async def generate_str(c, m):
    get_api_id = await c.ask(
        chat_id=m.chat.id,
        text=API_TEXT.format(m.from_user.mention(style='md')),
        filters=filters.text
    )
    api_id = get_api_id.text
    if await is_cancel(m, api_id):
        return

    await get_api_id.delete()
    await get_api_id.request.delete()
    try:
        check_api = int(api_id)
    except Exception:
        await m.reply("**--🛑 APP ID không hợp lệ 🛑--**\nNhấp /start để bắt đầu tạo lại")
        return

    get_api_hash = await c.ask(
        chat_id=m.chat.id, 
        text=HASH_TEXT,
        filters=filters.text
    )
    api_hash = get_api_hash.text
    if await is_cancel(m, api_hash):
        return

    await get_api_hash.delete()
    await get_api_hash.request.delete()

    if not len(api_hash) >= 30:
        await m.reply("--**🛑 API HASH không hợp lệ 🛑**--\nNhấp /start để bắt đầu tạo lại.")
        return

    try:
        client = Client(":memory:", api_id=api_id, api_hash=api_hash)
    except Exception as e:
        await c.send_message(m.chat.id ,f"**🛑 ERROR: 🛑** `{str(e)}`\nNhấp /start để bắt đầu tạo lại.")
        return

    try:
        await client.connect()
    except ConnectionError:
        await client.disconnect()
        await client.connect()
    while True:
        get_phone_number = await c.ask(
            chat_id=m.chat.id,
            text=PHONE_NUMBER_TEXT
        )
        phone_number = get_phone_number.text
        if await is_cancel(m, phone_number):
            return
        await get_phone_number.delete()
        await get_phone_number.request.delete()

        confirm = await c.ask(
            chat_id=m.chat.id,
            text=f'🤔 Xác nhận `{phone_number}` là chính xác? (y/n): \n\nnhập: `y` (là Đúng)\ntype: `n` (là Không)'
        )
        if await is_cancel(m, confirm.text):
            return
        if "y" in confirm.text.lower():
            await confirm.delete()
            await confirm.request.delete()
            break
    try:
        code = await client.send_code(phone_number)
        await asyncio.sleep(1)
    except FloodWait as e:
        await m.reply(f"__Xin lỗi phải nói với bạn rằng bạn đang chờ đợi {e.x} Giây 😞__")
        return
    except ApiIdInvalid:
        await m.reply("🕵‍♂ ID API hoặc API HASH không hợp lệ.\n\nNhấp /start để tạo lại!")
        return
    except PhoneNumberInvalid:
        await m.reply("☎ Số điện thoại bạn cung cấp không hợp lệ.`\n\nNhấp /start để tạo lại!")
        return

    try:
        sent_type = {"app": "Telegram App 💌",
            "sms": "SMS 💬",
            "call": "Phone call 📱",
            "flash_call": "phone flash call 📲"
        }[code.type]
        otp = await c.ask(
            chat_id=m.chat.id,
            text=(f"Tôi đã gửi OTP tới số`{phone_number}` xuyên qua {sent_type}\n\n"
                  "Vui lòng nhập OTP theo định dạng `1 2 3 4 5` __(khoảng trắng được đề xuất giữa các số)__\n\n"
                  "Nếu Bot không gửi OTP thì hãy thử /start lại Bot.\n"
                  "Nhấp /cancel để Hủy bỏ."), timeout=300)
    except TimeoutError:
        await m.reply("**⏰ Lỗi TimeOut:** Bạn đã đạt đến Giới hạn thời gian là 5 phút.\nNhấp /start để tạo lại!")
        return
    if await is_cancel(m, otp.text):
        return
    otp_code = otp.text
    await otp.delete()
    await otp.request.delete()
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code=' '.join(str(otp_code)))
    except PhoneCodeInvalid:
        await m.reply("**📵 Invalid Code**\n\nNhấp /start để tạo lại!")
        return 
    except PhoneCodeExpired:
        await m.reply("**⌚ Code is Expired**\n\nNhấp /start để tạo lại!")
        return
    except SessionPasswordNeeded:
        try:
            two_step_code = await c.ask(
                chat_id=m.chat.id, 
                text="`🔐 Tài khoản này có mã xác minh hai bước.\nVui lòng nhập mã xác thực yếu tố thứ hai của bạn.`\nNhấn /cancel để Hủy..",
                timeout=300
            )
        except TimeoutError:
            await m.reply("**⏰ TimeOut Error:** You reached Time limit of 5 min.\nNhấp /start để tạo lại!")
            return
        if await is_cancel(m, two_step_code.text):
            return
        new_code = two_step_code.text
        await two_step_code.delete()
        await two_step_code.request.delete()
        try:
            await client.check_password(new_code)
        except Exception as e:
            await m.reply(f"**⚠️ ERROR:** `{str(e)}`")
            return
    except Exception as e:
        await c.send_message(m.chat.id ,f"**⚠️ ERROR:** `{str(e)}`")
        return
    try:
        session_string = await client.export_session_string()
        await client.send_message("me", f"**Phiên chuỗi của bạn 👇**\n\n`{session_string}`\n\nCảm ơn đã sử dụng {(await c.get_me()).mention(style='md')}")
        text = "✅ Đã tạo thành công phiên chuỗi của bạn và gửi cho bạn các tin nhắn đã lưu.\nKiểm tra các tin nhắn đã lưu của bạn hoặc Nhấp vào nút Bên dưới."
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Xem Phiên chuỗi ↗️", url=f"tg://openmessage?user_id={m.chat.id}")]]
        )
        await c.send_message(m.chat.id, text, reply_markup=reply_markup)
    except Exception as e:
        await c.send_message(m.chat.id ,f"**⚠️ ERROR:** `{str(e)}`")
        return
    

@Client.on_message(filters.private & filters.command("help"))
async def help(c, m):
    await help_cb(c, m, cb=False)


@Client.on_callback_query(filters.regex('^help$'))
async def help_cb(c, m, cb=True):
    help_text = """**Này Bạn cần trợ giúp ??👨‍✈️**


>>>> Nhấn nút bắt đầu

>>>> Gửi API_ID của bạn khi bot hỏi.

>>>> Sau đó, gửi API_HASH của bạn khi bot hỏi.

>>>> Gửi số điện thoại di động của bạn.

>>>> Gửi OTP nhận được đến số của bạn theo định dạng `1 2 3 4 5`(Cho khoảng trắng b/w mỗi chữ số)

>>>> (Nếu bạn có xác minh hai bước, hãy gửi cho bot nếu bot hỏi.)


**NOTE:**

Nếu bạn mắc lỗi ở bất kỳ đâu, hãy nhấn /cancel và sau đó nhấn /start
"""

    buttons = [[
        InlineKeyboardButton('📕 Thông tin', callback_data='about'),
        InlineKeyboardButton('❌ Đóng', callback_data='close')
    ]]
    if cb:
        await m.answer()
        await m.message.edit(text=help_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    else:
        await m.reply_text(text=help_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True, quote=True)


@Client.on_message(filters.private & filters.command("about"))
async def about(c, m):
    await about_cb(c, m, cb=False)


@Client.on_callback_query(filters.regex('^about$'))
async def about_cb(c, m, cb=True):
    me = await c.get_me()
    about_text = f"""**CHI TIẾT CỦA TÔI:**

__🤖 My Name:__ {me.mention(style='md')}
    
__📝 Language:__ [Python3](https://www.python.org/)

__🧰 Framework:__ [Pyrogram](https://github.com/pyrogram/pyrogram)

__👨‍💻 Developer:__ [Kuri](https://t.me/Kuri69)

__📢 Channel:__ [Kênh](https://t.me/kenhsex)

__👥 Group:__ [Nhóm](https://t.me/Nangcuc)
"""

    buttons = [[
        InlineKeyboardButton('💡 Hỗ trợ', callback_data='help'),
        InlineKeyboardButton('❌ Đóng', callback_data='close')
    ]]
    if cb:
        await m.answer()
        await m.message.edit(about_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    else:
        await m.reply_text(about_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True, quote=True)


@Client.on_callback_query(filters.regex('^close$'))
async def close(c, m):
    await m.message.delete()
    await m.message.reply_to_message.delete()


async def is_cancel(msg: Message, text: str):
    if text.startswith("/cancel"):
        await msg.reply("⛔ Quá trình đã bị hủy.")
        return True
    return False

