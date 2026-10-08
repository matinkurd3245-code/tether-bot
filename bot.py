import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ============ تنظیمات ============
TOKEN = "8995582835:AAGiTL8S9eIAWEstBKjN9TmI2SqNfrGFW7g"
ADMIN_ID = 7728214777           # آیدی عددی خودت
CARD_NUMBER = "6219861410654957" # شماره کارت
CARD_HOLDER = "متین رسول نژاد"    # صاحب کارت
MIN_AMOUNT = 10                  # حداقل خرید (تتر)

# قیمت اولیه (بعداً با /setprice عوضش کن)
USDT_PRICE = 100000

# ============ لاگ ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ ذخیره وضعیت ============
user_data_store = {}


# ============ دستورات ادمین ============
async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغییر قیمت تتر: /setprice 102000"""
    global USDT_PRICE
    
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ این دستور فقط برای ادمینه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            f"💰 قیمت فعلی: {USDT_PRICE:,} تومان\n\n"
            f"برای تغییر: `/setprice 102000`",
            parse_mode="Markdown"
        )
        return
    
    try:
        new_price = int(context.args[0])
        USDT_PRICE = new_price
        await update.message.reply_text(
            f"✅ قیمت تتر به {new_price:,} تومان تغییر کرد."
        )
    except ValueError:
        await update.message.reply_text("❌ عدد معتبر بفرست. مثال: `/setprice 102000`", parse_mode="Markdown")


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای ادمین"""
    if update.message.from_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "🔧 دستورات ادمین:\n\n"
        "`/setprice 100000` — تغییر قیمت تتر\n"
        "`/price` — دیدن قیمت فعلی\n"
        "`/help_admin` — همین راهنما",
        parse_mode="Markdown"
    )


async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش قیمت فعلی"""
    if update.message.from_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"💰 قیمت فعلی تتر: {USDT_PRICE:,} تومان")


# ============ کاربر عادی ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💰 خرید تتر", callback_data="buy")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"به فروشگاه تتر خوش آمدید 🛍\n\n"
        f"💵 قیمت هر تتر: {USDT_PRICE:,} تومان\n"
        f"📉 حداقل خرید: {MIN_AMOUNT} تتر\n\n"
        f"برای خرید روی دکمه زیر بزن:",
        reply_markup=reply_markup
    )


async def buy_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data_store[user_id] = {"step": "waiting_amount"}
    
    await query.message.reply_text(
        f"چند تتر می‌خوای بخری؟\n"
        f"(قیمت فعلی: {USDT_PRICE:,} تومان)\n\n"
        f"فقط عدد بفرست (مثلاً: 50)"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    state = user_data_store.get(user_id, {})
    step = state.get("step")
    
    # ---- مرحله ۱: دریافت مقدار ----
    if step == "waiting_amount":
        try:
            amount = float(text)
            if amount < MIN_AMOUNT:
                await update.message.reply_text(f"حداقل خرید {MIN_AMOUNT} تتره. دوباره بفرست:")
                return
            total = int(amount * USDT_PRICE)
            state["amount"] = amount
            state["total"] = total
            state["step"] = "waiting_receipt"
            user_data_store[user_id] = state
            
            await update.message.reply_text(
                f"✅ مقدار: {amount} تتر\n"
                f"💰 مبلغ قابل پرداخت: {total:,} تومان\n\n"
                f"💳 لطفاً مبلغ رو به این کارت واریز کن:\n\n"
                f"`{CARD_NUMBER}`\n"
                f"به نام: {CARD_HOLDER}\n\n"
                f"بعد از واریز، عکس رسید رو همینجا بفرست 📸",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("لطفاً فقط عدد بفرست.")
        return
    
    # ---- مرحله ۲: دریافت رسید ----
    if step == "waiting_receipt":
        if not update.message.photo:
            await update.message.reply_text("لطفاً عکس رسید رو بفرست 📸")
            return
        
        photo = update.message.photo[-1]
        state["receipt"] = photo.file_id
        state["step"] = "waiting_approval"
        user_data_store[user_id] = state
        
        keyboard = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=(
                f"🔔 سفارش جدید\n\n"
                f"👤 کاربر: {update.message.from_user.full_name}\n"
                f"🆔 آیدی: `{user_id}`\n"
                f"💵 مقدار: {state['amount']} تتر\n"
                f"💰 مبلغ: {state['total']:,} تومان\n\n"
                f"تأیید می‌کنی؟"
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text("✅ رسیدت دریافت شد.\nدر انتظار تأیید ادمین... ⏳")
        return
    
    # ---- مرحله ۳: دریافت آدرس ولت ----
    if step == "waiting_wallet":
        if not text.startswith("0x") or len(text) != 42:
            await update.message.reply_text(
                "❌ آدرس ولت BEP20 باید با `0x` شروع بشه و ۴۲ کاراکتر باشه.\nدوباره بفرست:",
                parse_mode="Markdown"
            )
            return
        
        state["wallet"] = text
        state["step"] = "done"
        user_data_store[user_id] = state
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📮 آدرس ولت کاربر\n\n"
                f"👤 کاربر: {update.message.from_user.full_name}\n"
                f"💵 مقدار: {state['amount']} تتر\n"
                f"📍 آدرس BEP20:\n`{text}`\n\n"
                f"➡️ حالا تتر رو به این آدرس انتقال بده.",
            ),
            parse_mode="Markdown"
        )
        
        await update.message.reply_text("✅ آدرست ثبت شد.\nبه زودی تتر برات ارسال می‌شه 🚀")
        return
    
    # ---- پیام پیش‌فرض ----
    await update.message.reply_text("برای شروع، دستور /start رو بزن.")


# ============ تأیید/رد ادمین ============
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        if user_id in user_data_store:
            user_data_store[user_id]["step"] = "waiting_wallet"
            
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ پرداختت تأیید شد!\n\n"
                    "حالا آدرس ولت **BEP20** خودت رو بفرست.\n"
                    "⚠️ فقط شبکه BEP20 (شروع با `0x`)",
                ),
                parse_mode="Markdown"
            )
            
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n✅ تأیید شد"
            )
    
    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        if user_id in user_data_store:
            user_data_store[user_id]["step"] = "rejected"
            
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ متأسفانه رسیدت تأیید نشد. اگه مشکلی هست با پشتیبانی تماس بگیر."
            )
            
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n❌ رد شد"
            )


# ============ اجرا ============
def main():
    app = Application.builder().token(TOKEN).build()
    
    # دستورات ادمین
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("price", show_price))
    app.add_handler(CommandHandler("help_admin", admin_help))
    
    # دستورات کاربر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy_button, pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(approve|reject)_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
