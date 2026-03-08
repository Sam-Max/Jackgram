# Bot Localization

This project supports a global bot language controlled from `config.env`.

## Goal

- Keep the existing English strings as the canonical source.
- Add Spanish translations for user-facing bot messages and buttons.
- Add Spanish translations for Telegram command descriptions.
- Switch the bot language globally through an environment variable.
- Fall back to English if a translation key is missing or an unsupported locale is configured.

## Configuration

Add this variable to `config.env`:

```env
BOT_LANGUAGE = "en"
```

Supported values:

- `en` - English
- `es` - Spanish

If `BOT_LANGUAGE` is not set, the bot uses `en`.

## Implementation Overview

The bot localization layer is intentionally simple.

- `jackgram/bot/bot.py` reads the global `BOT_LANGUAGE` setting.
- `jackgram/bot/i18n.py` stores translations and exposes a helper function.
- Bot plugins call `t("translation.key")` instead of hardcoding visible strings.
- Bot command registration also uses `t(...)` so the Telegram command menu matches the selected language.

## Translation Helper

Use the shared helper for every user-facing bot string:

```python
from jackgram.bot.i18n import t

message = t("wizard.cancelled")
button = t("common.cancel")
formatted = t("search.no_results", query=query)
```

Behavior:

- Resolve the active language from `BOT_LANGUAGE`.
- Look up the key in the selected language.
- Fall back to English if the key does not exist in the selected language.
- Fall back to the key itself if it is missing everywhere.
- Apply Python `str.format()` placeholders when keyword arguments are provided.

## Key Naming

Keys should stay grouped by feature so they are easy to maintain.

Examples:

- `common.cancel`
- `common.close`
- `search.no_results`
- `search.invalid_page`
- `wizard.cancelled`
- `wizard.confirm_index`
- `index.progress_start`
- `database.backup_started`

## Scope

This localization layer is currently global for the whole bot process.

- All users see the same language.
- There is no per-user locale selection yet.
- The API metadata language remains controlled separately by `TMDB_LANGUAGE`.

## Adding New Translations

When adding a new bot message:

1. Add the English text to the `en` dictionary.
2. Add the Spanish equivalent to the `es` dictionary.
3. Replace the hardcoded string in the plugin with `t("...")`.
4. Prefer placeholders instead of string concatenation for dynamic values.

Example:

```python
t("search.results_header", query=query, page=page, total_pages=total_pages)
```

## Validation

Recommended checks after changing translations:

```bash
python -m compileall jackgram tests
```

Manual verification:

- Start with `BOT_LANGUAGE="en"` and confirm current bot text stays unchanged.
- Start with `BOT_LANGUAGE="es"` and confirm bot replies/buttons appear in Spanish.
- Trigger search, indexing wizard, backup, delete, and restore flows.
