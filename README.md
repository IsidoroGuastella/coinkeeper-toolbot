# Coin Keeper Tool

Telegram bot for managing a coin collection through Google Sheets.

The bot guides the user in chat through the selection of:
- country
- face value
- year

After checking the sheet:
- if the target cell contains `v`, the bot replies that the coin is already in the collection
- if the target cell is empty, the bot reports that the coin is missing and asks whether it should be recorded
- if the user confirms, the bot writes `v` into the matching cell
- if something goes wrong during reading or updating, the bot returns an error message

## Stack

- Python
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [gspread](https://github.com/burnash/gspread)
- Google Sheets API
- Render

## Current Sheet Structure

The bot assumes this layout for each worksheet:
- the sheet name matches the country, for example `Italy`
- column `A` contains the face values
- row `1` contains the years
- the cell at the intersection of value and year contains `v` when the coin is present in the collection

## Environment Variables

The project uses these variables:
- `BOT_TOKEN`: Telegram bot token
- `GOOGLE_CREDENTIALS`: Google service account JSON stored as a string

For local usage, if `GOOGLE_CREDENTIALS` is not available, the bot falls back to a local `credentials.json` file.

## Local Run

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set the required environment variables or create a `.env` file.
4. Start the bot:

```bash
python bot.py
```

## Deploy on Render

The repository includes [`render.yaml`](/Users/isidoroguastella/GIT-VARIO/coin-keeper-tool/render.yaml) with a basic configuration for a Python `worker` service.

At minimum, these environment variables must be configured on Render:
- `BOT_TOKEN`
- `GOOGLE_CREDENTIALS`

The bot uses `run_polling()`, so the correct Render deployment model is a continuously running worker.

## Project Status

Currently supported features:
- coin lookup through Telegram chat
- presence check against Google Sheets
- sheet update after user confirmation
- compatibility with both local execution and Render deployment
