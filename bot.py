import json
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

import gspread
from dotenv import load_dotenv
from gspread import Spreadsheet, Worksheet
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ( 
    Application, CallbackQueryHandler, 
    CommandHandler, ContextTypes, 
    ConversationHandler, MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

NAZIONE, VALORE, ANNO, CONFERMA = range(4)
VALID_VALUES = {
    "2,00 €",
    "1,00 €",
    "0,50 €",
    "0,20 €",
    "0,10 €",
    "0,05 €",
    "0,02 €",
    "0,01 €",
}


def normalize_country_name(raw_value: str) -> str:
    return " ".join(part.capitalize() for part in raw_value.strip().split())


def validate_year(raw_value: str) -> Optional[str]:
    year = raw_value.strip()
    if len(year) == 4 and year.isdigit():
        return year
    return None


def build_coin_summary(country: str, value: str, year: str) -> str:
    return f"{country} {value} {year}"


def normalize_sheet_text(value: str) -> str:
    return value.strip().lower()


def normalize_coin_value(raw_value: str) -> str:
    cleaned = raw_value.replace("€", "").replace(" ", "").replace(",", ".").strip()
    try:
        return format(Decimal(cleaned).normalize(), "f").rstrip("0").rstrip(".") or "0"
    except InvalidOperation:
        return cleaned


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_sheet() -> Spreadsheet:
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    sheet_id = get_required_env("GOOGLE_SHEET_ID")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    if creds_json:
        info = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)


def get_worksheet(doc: Spreadsheet, country: str) -> Worksheet:
    try:
        return doc.worksheet(country)
    except gspread.WorksheetNotFound as exc:
        raise ValueError(f"Worksheet not found for country '{country}'.") from exc


def find_coin_cell(ws: Worksheet, value: str, year: str) -> Tuple[int, int]:
    values = ws.get_all_values()
    normalized_value = normalize_coin_value(value)
    normalized_year = year.strip()

    for row_index, row in enumerate(values, start=1):
        normalized_row = [normalize_sheet_text(cell) for cell in row]
        coin_markers = {"coin", "moneta"}
        if not any(cell in coin_markers for cell in normalized_row):
            continue

        coin_col = next(
            index + 1 for index, cell in enumerate(normalized_row) if cell in coin_markers
        )
        years_row_index = row_index + 1
        values_start_row = row_index + 2

        if years_row_index > len(values):
            continue

        years_row = values[years_row_index - 1]

        target_col = None
        for col_index in range(coin_col + 1, len(years_row) + 1):
            if normalize_sheet_text(years_row[col_index - 1]) == normalized_year:
                target_col = col_index
                break

        if target_col is None:
            continue

        current_row = values_start_row
        while current_row <= len(values):
            current_row_values = values[current_row - 1]
            coin_cell = current_row_values[coin_col - 1] if coin_col <= len(current_row_values) else ""
            normalized_coin_cell = normalize_coin_value(coin_cell)
            marker_value = normalize_sheet_text(coin_cell)

            if marker_value in coin_markers:
                break

            if marker_value == "":
                break

            if normalized_coin_cell == normalized_value:
                return current_row, target_col

            current_row += 1

    raise ValueError(
        f"Coin {value} for year {year} was not found in worksheet '{ws.title}'. "
        "Check the worksheet name and table structure."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text(
        "Hi there! I'm CoinKeeper Bot.\n\n"
        "I'm here to help you manage your coin collection.\n"
        "Please note that only euro coins are currently supported.\n\n"
        "How does it work?\n"
        "You'll be asked for the country, face value, and year.\n"
        "I can check whether a coin is already in your collection.\n"
        "If the coin is missing, I can mark it as present after your confirmation "
        "by writing a 'v' in your spreadsheet.\n\n"
        "Use /search to check whether a coin is already in your collection.\n"
        "Use /stop at any time to stop the search."
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🪙 Let's search your collection.\n"
        "Send the coin country (for example: Italy, Belgium, Germany)."
    )
    return NAZIONE


async def handle_nazione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    country = normalize_country_name(update.message.text)

    if not country:
        await update.message.reply_text("Please send a valid country name.")
        return NAZIONE

    context.user_data["nazione"] = country

    keyboard = [
        [
            InlineKeyboardButton("2,00 €", callback_data="2,00 €"),
            InlineKeyboardButton("1,00 €", callback_data="1,00 €"),
        ],
        [
            InlineKeyboardButton("0,50 €", callback_data="0,50 €"),
            InlineKeyboardButton("0,20 €", callback_data="0,20 €"),
        ],
        [
            InlineKeyboardButton("0,10 €", callback_data="0,10 €"),
            InlineKeyboardButton("0,05 €", callback_data="0,05 €"),
        ],
        [
            InlineKeyboardButton("0,02 €", callback_data="0,02 €"),
            InlineKeyboardButton("0,01 €", callback_data="0,01 €"),
        ],
    ]
    await update.message.reply_text(
        f"Country: {country}. Select the face value:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return VALORE


async def handle_valore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data not in VALID_VALUES:
        await query.edit_message_text("Invalid value selected. Please restart with /search.")
        return ConversationHandler.END

    context.user_data["valore"] = query.data
    await query.edit_message_text(
        f"Value: {query.data}. Now send the year using 4 digits (for example: 2022)."
    )
    return ANNO


async def handle_anno(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    year = validate_year(update.message.text)
    if not year:
        await update.message.reply_text("Invalid year. Please send a 4-digit year, for example 2022.")
        return ANNO

    context.user_data["anno"] = year
    country = context.user_data["nazione"]
    value = context.user_data["valore"]
    coin_summary = build_coin_summary(country, value, year)

    await update.message.reply_text(f"🔍 Checking {coin_summary} in Google Sheets...")

    try:
        doc = get_sheet()
        ws = get_worksheet(doc, country)
        row_idx, col_idx = find_coin_cell(ws, value, year)
        context.user_data["cell"] = (row_idx, col_idx)

        cell_value = ws.cell(row_idx, col_idx).value
        normalized_cell_value = (cell_value or "").strip().lower()

        if normalized_cell_value == "v":
            await update.message.reply_text(f"🔴 This coin is already in your collection: {coin_summary}.")
            return ConversationHandler.END

        keyboard = [[
            InlineKeyboardButton("✅ Yes, save it", callback_data="si"),
            InlineKeyboardButton("❌ No, cancel", callback_data="no"),
        ]]
        await update.message.reply_text(
            f"🟢 This coin is missing: {coin_summary}.\nDo you want to mark it as present?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CONFERMA

    except ValueError as exc:
        await update.message.reply_text(f"❌ Lookup error: {exc}")
        return ConversationHandler.END
    except json.JSONDecodeError:
        logger.exception("Invalid GOOGLE_CREDENTIALS JSON")
        await update.message.reply_text("⚠️ Configuration error: invalid Google credentials.")
        return ConversationHandler.END
    except Exception:
        logger.exception("Unexpected error while checking coin data")
        await update.message.reply_text(
            "⚠️ Unexpected error while processing the request. Please try again later."
        )
        return ConversationHandler.END


async def conferma_inserimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    country = context.user_data.get("nazione")
    value = context.user_data.get("valore")
    year = context.user_data.get("anno")
    coin_summary = build_coin_summary(country, value, year)

    if query.data == "no":
        await query.edit_message_text(f"Operation cancelled. No changes saved for {coin_summary}.")
        return ConversationHandler.END

    if query.data != "si":
        await query.edit_message_text("Invalid confirmation choice. Please restart with /search.")
        return ConversationHandler.END

    try:
        doc = get_sheet()
        ws = get_worksheet(doc, country)
        row_idx, col_idx = context.user_data["cell"]
        ws.update_cell(row_idx, col_idx, "v")
        await query.edit_message_text(f"💾 Saved successfully: {coin_summary} is now marked as present.")
    except ValueError as exc:
        await query.edit_message_text(f"❌ Save error: {exc}")
    except json.JSONDecodeError:
        logger.exception("Invalid GOOGLE_CREDENTIALS JSON during save")
        await query.edit_message_text("⚠️ Configuration error: invalid Google credentials.")
    except Exception:
        logger.exception("Unexpected error while saving coin data")
        await query.edit_message_text("⚠️ Unexpected error while saving the coin.")

    return ConversationHandler.END


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Search stopped. No changes were made.")
    return ConversationHandler.END


def main() -> None:
    token = get_required_env("BOT_TOKEN")
    get_sheet()
    logger.info("Coin Keeper bot started successfully.")

    app = Application.builder().token(token).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("search", search)],
        states={
            NAZIONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nazione)],
            VALORE: [CallbackQueryHandler(handle_valore)],
            ANNO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_anno)],
            CONFERMA: [CallbackQueryHandler(conferma_inserimento)],
        },
        fallbacks=[CommandHandler("stop", stop)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
