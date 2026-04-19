import os
import json
import logging
from datetime import datetime
from difflib import get_close_matches
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
AUTO_DELETE_SECONDS = int(os.environ.get("AUTO_DELETE_SECONDS", "300"))

DB_FILE = "movies.json"
HIDDEN = False


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_admin(user_id):
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Movie Bot*\n\n"
        "Just type the name of any movie and I'll send you the download link instantly!\n\n"
        "Example: `Interstellar` or `KGF Chapter 2`",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "👑 *Admin Commands*\n\n"
            "`/add MovieName | https://link.com` — Add a movie\n"
            "`/delete MovieName` — Delete a movie\n"
            "`/list` — List all movies\n"
            "`/backup` — Download full backup\n"
            "`/restore` — Restore from backup file\n"
            "`/hide` — Hide all links (copyright emergency)\n"
            "`/unhide` — Restore all links\n"
            "`/stats` — Bot statistics\n\n"
            "Users just type a movie name to search.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "Just type any movie name to get the download link!\n"
            "Example: `Interstellar`",
            parse_mode="Markdown"
        )


async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        text = " ".join(context.args)
        if "|" not in text:
            await update.message.reply_text(
                "Format: `/add Movie Name | https://your-link.com`",
                parse_mode="Markdown"
            )
            return

        parts = text.split("|", 1)
        name = parts[0].strip()
        link = parts[1].strip()

        if not name or not link:
            await update.message.reply_text("Movie name and link cannot be empty.")
            return

        db = load_db()
        db[name.lower()] = {
            "name": name,
            "link": link,
            "added": datetime.now().isoformat()
        }
        save_db(db)
        await update.message.reply_text(f"Movie *{name}* added successfully!", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    name = " ".join(context.args).strip().lower()
    if not name:
        await update.message.reply_text("Usage: `/delete Movie Name`", parse_mode="Markdown")
        return

    db = load_db()
    if name in db:
        del db[name]
        save_db(db)
        await update.message.reply_text(f"Movie deleted.")
    else:
        await update.message.reply_text("Movie not found in database.")


async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    db = load_db()
    if not db:
        await update.message.reply_text("No movies in database yet.")
        return

    lines = [f"• {v['name']}" for v in db.values()]
    text = f"🎬 *{len(lines)} movies in database:*\n\n" + "\n".join(lines)

    if len(text) > 4000:
        text = text[:4000] + "\n\n_(list truncated)_"

    await update.message.reply_text(text, parse_mode="Markdown")


async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    db = load_db()
    backup_data = json.dumps(db, indent=2).encode("utf-8")
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    await update.message.reply_document(
        document=backup_data,
        filename=filename,
        caption=f"Backup of {len(db)} movies — {datetime.now().strftime('%d %b %Y %H:%M')}"
    )


async def restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    if not update.message.document:
        await update.message.reply_text(
            "Send your backup JSON file with the caption `/restore`",
            parse_mode="Markdown"
        )
        return

    file = await update.message.document.get_file()
    data = await file.download_as_bytearray()
    try:
        new_db = json.loads(data.decode("utf-8"))
        save_db(new_db)
        await update.message.reply_text(f"Restored {len(new_db)} movies successfully!")
    except Exception as e:
        await update.message.reply_text(f"Failed to restore: {e}")


async def hide_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    global HIDDEN
    HIDDEN = True
    await update.message.reply_text(
        "All links are now HIDDEN. Users will see 'not available' until you use /unhide."
    )


async def unhide_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    global HIDDEN
    HIDDEN = False
    await update.message.reply_text("Links are now VISIBLE again.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized.")
        return

    db = load_db()
    status = "HIDDEN (copyright mode)" if HIDDEN else "Visible"
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n"
        f"Total movies: `{len(db)}`\n"
        f"Link status: `{status}`\n"
        f"Auto-delete: `{AUTO_DELETE_SECONDS}s`",
        parse_mode="Markdown"
    )


async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global HIDDEN
    query = update.message.text.strip().lower()

    if not query or query.startswith("/"):
        return

    db = load_db()

    if HIDDEN:
        await update.message.reply_text(
            "Sorry, movies are temporarily unavailable. Please try again later."
        )
        return

    exact = db.get(query)
    if exact:
        sent = await update.message.reply_text(
            f"🎬 *{exact['name']}*\n\n"
            f"[Download Link]({exact['link']})\n\n"
            f"_This message will be deleted in {AUTO_DELETE_SECONDS // 60} minutes._",
            parse_mode="Markdown"
        )
        if AUTO_DELETE_SECONDS > 0:
            context.job_queue.run_once(
                delete_message,
                AUTO_DELETE_SECONDS,
                data={"chat_id": sent.chat_id, "message_id": sent.message_id}
            )
        return

    keys = list(db.keys())
    matches = get_close_matches(query, keys, n=5, cutoff=0.4)

    if not matches:
        await update.message.reply_text(
            f"Movie not found. Try a different spelling?\n\n"
            f"If you want *{update.message.text.strip()}* added, the admin has been notified.",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"User @{update.effective_user.username or update.effective_user.first_name} "
                f"searched for: *{update.message.text.strip()}* (not found)",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if len(matches) == 1:
        movie = db[matches[0]]
        sent = await update.message.reply_text(
            f"🎬 *{movie['name']}*\n\n"
            f"[Download Link]({movie['link']})\n\n"
            f"_This message will be deleted in {AUTO_DELETE_SECONDS // 60} minutes._",
            parse_mode="Markdown"
        )
        if AUTO_DELETE_SECONDS > 0:
            context.job_queue.run_once(
                delete_message,
                AUTO_DELETE_SECONDS,
                data={"chat_id": sent.chat_id, "message_id": sent.message_id}
            )
        return

    buttons = [
        [InlineKeyboardButton(db[m]["name"], callback_data=f"movie:{m}")]
        for m in matches
    ]
    await update.message.reply_text(
        "Did you mean one of these?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global HIDDEN
    query = update.callback_query
    await query.answer()

    if HIDDEN:
        await query.edit_message_text("Sorry, movies are temporarily unavailable.")
        return

    data = query.data
    if data.startswith("movie:"):
        key = data[6:]
        db = load_db()
        movie = db.get(key)
        if movie:
            sent = await query.edit_message_text(
                f"🎬 *{movie['name']}*\n\n"
                f"[Download Link]({movie['link']})\n\n"
                f"_This message will be deleted in {AUTO_DELETE_SECONDS // 60} minutes._",
                parse_mode="Markdown"
            )
            if AUTO_DELETE_SECONDS > 0:
                context.job_queue.run_once(
                    delete_message,
                    AUTO_DELETE_SECONDS,
                    data={"chat_id": sent.chat_id, "message_id": sent.message_id}
                )
        else:
            await query.edit_message_text("Movie not found.")


async def delete_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(
            chat_id=job.data["chat_id"],
            message_id=job.data["message_id"]
        )
    except Exception:
        pass


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_movie))
    app.add_handler(CommandHandler("delete", delete_movie))
    app.add_handler(CommandHandler("list", list_movies))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("restore", restore))
    app.add_handler(CommandHandler("hide", hide_links))
    app.add_handler(CommandHandler("unhide", unhide_links))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
