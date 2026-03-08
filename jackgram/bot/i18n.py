from typing import Dict

from jackgram.bot.bot import BOT_LANGUAGE


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "common.prev": "⬅️ Prev",
        "common.next": "Next ➡️",
        "common.back": "⬅️ Back",
        "common.close": "❌ Close",
        "common.cancel": "❌ Cancel",
        "common.invalid_action": "Invalid action.",
        "common.not_authorized": "⛔ Not authorized.",
        "common.not_authorized_command": "⛔ You are not authorized to use this command.",
        "common.error_processing_action": "Error processing this action.",
        "common.movie": "Movie",
        "common.tv_show": "TV Show",
        "common.bot": "Bot",
        "common.user": "User",
        "common.unknown": "Unknown",
        "common.unknown_movie": "Unknown movie",
        "common.unknown_series": "Unknown series",
        "common.unknown_file": "Unknown file",
        "common.raw_file": "Raw file",
        "common.series": "Series",
        "common.unknown_year": "Unknown",
        "common.yes_delete": "✅ Yes, delete",
        "common.yes_delete_it": "✅ Yes, delete it",
        "common.confirm_and_index": "✅ Confirm & Index",
        "command.start": "Start interaction and show help message",
        "command.index": "Index files from a channel (wizard or direct)",
        "command.search": "Search indexed files",
        "command.count": "Database statistics",
        "command.save_db": "Back up the database",
        "command.load_db": "Restore from backup (reply to JSON)",
        "command.del": "Delete a TMDb entry",
        "command.del_channel": "Delete all entries for a chat ID",
        "command.del_db": "Delete a database",
        "command.token": "Generate an API access token",
        "command.log": "Download the bot log file",
        "start.welcome": (
            "🚀 **Jackgram v{version}**\n\n"
            "👋 **Welcome to JackgramBot!**\n\n"
            "**📌 Indexing**\n"
            "/index — Index files from a channel (wizard or direct)\n\n"
            "**🔍 Search & Browse**\n"
            "/search `<query>` — Find indexed files\n"
            "/count — Database statistics\n\n"
            "**🗃️ Database Management**\n"
            "/del `<tmdb_id>` — Delete a TMDb entry\n"
            "/del_channel `<chat_id>` — Delete all entries for a chat\n"
            "/save_db — Back up the database\n"
            "/load_db — Restore from backup (reply to JSON)\n"
            "/del_db `<name>` — Delete a database\n\n"
            "**🔧 Admin**\n"
            "/token — Generate an API access token\n"
            "/log — Download the bot log file\n\n"
            "🧙‍♂️ **Contribute:** Send a media file directly to start the contribution wizard!\n"
            "🚀 Files posted in indexed channels are auto-processed!"
        ),
        "search.use_query": "Use /search <query>",
        "search.no_results": 'No results found for "{query}".',
        "search.failed_session": "❌ Failed to create search session. Please try again.",
        "search.results_view": (
            "🔍 Results for: **{query}**\n"
            "Page `{page}/{total_pages}` • Total: **{total_results}**\n\n"
            "Select a result:"
        ),
        "search.series_not_found": "❌ Series not found in the active session.",
        "search.seasons_view": (
            "📺 **{title}**\n"
            "Seasons • Page `{page}/{total_pages}`\n\n"
            "Choose a season:"
        ),
        "search.season_label": "Season {season_number} ({episode_count} eps)",
        "search.season_not_selected": "❌ Season not selected.",
        "search.episodes_view": (
            "📺 **{title}**\n"
            "Season **{season_number}** • Page `{page}/{total_pages}`\n\n"
            "Choose an episode:"
        ),
        "search.episode_fallback_title": "Episode {episode_number}",
        "search.episode_label": "E{episode_number:02d} • {episode_title} ({files_count} files)",
        "search.selected_item_not_found": "❌ Selected item not found.",
        "search.quality_view": (
            "{header}\n"
            "Files • Page `{page}/{total_pages}`\n\n"
            "Choose quality/file:"
        ),
        "search.this_search_expired": "This search has expired.",
        "search.this_search_expired_retry": "This search has expired. Send your query again.",
        "search.these_buttons_not_for_you": "These buttons are not for you.",
        "search.closed": "❌ Search closed.",
        "search.invalid_page": "Invalid page.",
        "search.invalid_selection": "Invalid selection.",
        "search.invalid_season": "Invalid season.",
        "search.invalid_series_selection": "Invalid series selection.",
        "search.invalid_episode": "Invalid episode.",
        "search.invalid_episode_selection": "Invalid episode selection.",
        "search.invalid_file_selection": "Invalid file selection.",
        "search.file_source_not_found": "File source not found.",
        "search.preparing_file": "Preparing file...",
        "search.source_channel_inaccessible": (
            "Bot cannot access the source channel message. Check bot access to the logs channel."
        ),
        "search.telegram_did_not_forward": "Telegram did not forward this file. Try again.",
        "search.file_sent": "✅ File sent.",
        "search.invalid_navigation": "Invalid navigation.",
        "search.unknown_action": "Unknown action.",
        "search.floodwait": "FloodWait: wait {seconds}s.",
        "index.invalid_client_type": "Invalid client type. Use 'bot' or 'user'.",
        "index.count_must_be_greater_than_zero": "The count must be greater than 0.",
        "index.invalid_ids": "Invalid IDs. Please provide numbers.",
        "index.wizard_intro": (
            "🔍 **Indexing Wizard**\n\n"
            "Please send the **Chat ID** or **Username** of the channel you want to index."
        ),
        "index.invalid_chat_id_or_username": "❌ Invalid Chat ID or Username.",
        "index.range_prompt": (
            "🔢 Send the **Start Message ID** and the **Count of Messages** to index separated by a space (e.g., `1 100`)."
        ),
        "index.invalid_range_format": "❌ Invalid format. Please send two numbers separated by a space.",
        "index.which_logs_channel": "📂 **Which Logs Channel should I use?**",
        "index.cancelled": "❌ Indexing cancelled.",
        "index.selected_logs_channel": "✅ Selected Logs Channel: **{channel_name}**",
        "index.which_client": (
            "🤖 **Which client should I use for indexing?**\n\n"
            "• **Bot**: Faster to start, but subject to strict bot limits.\n"
            "• **User**: Uses your multi-session user accounts, better for large channels."
        ),
        "index.selected_client_starting": "✅ Selected: **{client_type}**\n⏳ Starting index...",
        "index.wizard_timed_out": "⏳ Indexing wizard timed out.",
        "index.error": "❌ Error: {error}",
        "index.quick_usage": (
            "🚀 **Quick Indexing**\n\n"
            "Usage: `/index chat_id first_id count client_type [logs_channel]`\n"
            "Example: `/index -10012345 1 500 bot`\n\n"
            "💡 Or just send `/index` without parameters to use the **wizard**!"
        ),
        "index.selected_client_unavailable": "❌ Selected client is not available or configured.",
        "index.progress_start": (
            "🔄 **Indexing in progress...**\n\n"
            "📡 Channel: `{chat_id}`\n"
            "📨 Range: `{first_id}` → `{last_id}` ({total_range} messages)\n"
            "📂 Output: `{selected_log_channel}`\n\n"
            "⏳ 0% — Starting...\n\n"
            "🚫 Do not start another index until this completes."
        ),
        "index.progress_update": (
            "🔄 **Indexing in progress...**\n\n"
            "📡 Channel: `{chat_id}`\n"
            "`{bar}` **{pct}%**\n\n"
            "  ✅ Indexed: **{indexed}**\n"
            "  ⏭️ Skipped: {skipped}\n"
            "  ❌ Errors: {errors}\n\n"
            "📨 Message `{current_id}` / `{last_id}`"
        ),
        "index.complete_summary": (
            "✅ **Indexing complete!**\n\n"
            "📊 **Stats:**\n"
            "  • Indexed: **{indexed}**\n"
            "  • Skipped (too small): {skipped_size}\n"
            "  • Skipped (adult keyword): {skipped_keyword}\n"
            "  • Skipped (invalid ext): {skipped_ext}\n"
            "  • Skipped (no media): {skipped_no_media}\n"
            "  • Errors: {errors}\n\n"
            "Total skipped by filters: **{total_skipped}**"
        ),
        "index.floodwait": "⏳ Got FloodWait of {seconds}s",
        "wizard.multipart_rejected": (
            "❌ **Upload Rejected**\n\n"
            "This appears to be a split/multipart file (e.g., Part 1, CD 2). These are not supported because they cannot be streamed natively."
        ),
        "wizard.prompt_with_imdb": (
            "🧙‍♂️ **User Contribution Wizard**\n\n"
            "I detected a media file.\n\n"
            "🔍 **Auto-detected IMDb ID:** `{imdb_id}`\n"
            "Is this a Movie or a TV Show?"
        ),
        "wizard.prompt_without_imdb": (
            "🧙‍♂️ **User Contribution Wizard**\n\n"
            "I detected a media file. Is this a Movie or a TV Show?"
        ),
        "wizard.cancelled": "❌ Wizard cancelled.",
        "wizard.selected_type": "✅ Selected: **{type_name}**",
        "wizard.fetching_tmdb": "🔍 Fetching TMDb data for `{imdb_id}`...",
        "wizard.ask_tmdb_or_title": "Please send the **TMDb ID** or the **exact title** of the {type_name}.",
        "wizard.searching_tmdb": "🔍 Searching TMDb...",
        "wizard.tmdb_match_not_found": "❌ Could not find a match on TMDb. Wizard cancelled.",
        "wizard.tmdb_details_failed": "❌ Failed to fetch TMDb details. Wizard cancelled.",
        "wizard.ask_season_episode": (
            "This is a TV Show, but I couldn't detect the Season and Episode from the filename.\n\n"
            "Please reply with Season and Episode in the format: `S01E05`"
        ),
        "wizard.invalid_format_cancelled": "❌ Invalid format. Wizard cancelled.",
        "wizard.which_logs_channel": "📂 **Which Logs Channel should I use to store this file?**",
        "wizard.selected_logs_channel": "✅ Selected Logs Channel: **{channel_name}**",
        "wizard.confirm_indexing": (
            "🍿 **Confirm Indexing**\n\n"
            "Title: **{title}** ({year})\n"
            "Type: **{type_name}**"
        ),
        "wizard.confirm_indexing_series_extra": "\nSeason: **{season}** | Episode: **{episode}**",
        "wizard.indexing": "⏳ Indexing...",
        "wizard.success": (
            "🎉 **Successfully Indexed!**\n\n"
            "The media has been validated by you and perfectly added to the database."
        ),
        "wizard.timed_out_restart": "⏳ Wizard timed out. Please send the file again to restart.",
        "wizard.unexpected_error": "❌ An unexpected error occurred while processing.",
        "delete.invalid_tmdb_id": "❌ Invalid TMDb ID. Please provide a number.",
        "delete.use_del": "Use /del <tmdb_id>",
        "delete.entry_deleted": "✅ Entry deleted successfully.",
        "delete.no_document": "No document found with the given TMDb ID.",
        "delete_channel.invalid_chat_id": "❌ Invalid Chat ID. Please provide a number (e.g. `-10012345`).",
        "delete_channel.use_del_channel": "Use /del_channel <chat_id>",
        "delete_channel.confirm": "⚠️ **Are you sure you want to delete all entries associated with chat `{chat_id}`?**",
        "delete_channel.deletion_cancelled": "❌ Deletion cancelled.",
        "delete_channel.deleting": "⏳ Deleting entries for `{chat_id}`...",
        "delete_channel.summary": (
            "✅ **Deletion Complete!**\n\n"
            "📊 **Stats:**\n"
            "  • Raw Files Deleted: **{raw_deleted}**\n"
            "  • Movies Modified: **{movies_modified}**\n"
            "  • TV Shows Modified: **{tv_modified}**\n\n"
            "Entries with no remaining files were also removed."
        ),
        "count.summary": (
            "📊 **Database Statistics**\n\n"
            "🎬 Movies: **{movies}**\n"
            "📺 TV Shows: **{tv}**\n"
            "📁 Raw Files: **{files}**\n"
            "━━━━━━━━━━━━━━━━━\n"
            "📦 Total entries: **{total}**\n"
            "💾 Total storage: **{storage}**"
        ),
        "backup.starting": "⏳ **Starting database backup...**",
        "backup.permission_denied": (
            "❌ Cannot create backup directory `{backup_dir}` — permission denied.\n"
            "💡 Set `BACKUP_DIR` in config.env to a writable path."
        ),
        "backup.progress": (
            "⏳ **Backing up database...**\n"
            "Processing collection: `{collection_name}` ({current}/{total})"
        ),
        "backup.writing_file": "💾 **Writing backup file...**",
        "backup.write_failed": "❌ Failed to write backup file: {error}",
        "backup.starting_upload": "📤 **Starting upload to Telegram...**",
        "backup.upload_progress": (
            "📤 **Uploading backup file to Telegram...**\n\n"
            "`{bar}` **{pct}%**\n"
            "📦 {current_size} / {total_size}"
        ),
        "backup.completed_caption": (
            "✅ **Backup completed!**\n\n"
            "All collections and fields (including new poster data) have been exported."
        ),
        "restore.reply_with_json": "Please reply to a JSON file with this command.",
        "restore.file_must_be_json": "The file must be a JSON file.",
        "restore.invalid_json_file": "Failed to load the file. Please ensure it is a valid JSON file.",
        "restore.invalid_json_structure": (
            "Invalid JSON structure. The file must contain a dictionary with collection names as keys."
        ),
        "restore.invalid_collection_data": "Invalid data for collection '{collection_name}'. Expected a list of documents.",
        "restore.success": "Database restored successfully from the uploaded file!",
        "delete_db.use_del_db": "Use /del_db <database_name>",
        "delete_db.confirm": (
            "⚠️ **Are you sure you want to DELETE the entire `{database_name}` database?**\n\n"
            "This action is **irreversible**."
        ),
        "delete_db.cancelled": "❌ Database deletion cancelled.",
        "delete_db.deleted": "✅ Database `{database_name}` has been deleted.",
        "log.caption": "Here is the bot.log file.",
        "log.not_found": "The bot.log file does not exist.",
    },
    "es": {
        "common.prev": "⬅️ Anterior",
        "common.next": "Siguiente ➡️",
        "common.back": "⬅️ Atras",
        "common.close": "❌ Cerrar",
        "common.cancel": "❌ Cancelar",
        "common.invalid_action": "Accion invalida.",
        "common.not_authorized": "⛔ No autorizado.",
        "common.not_authorized_command": "⛔ No estas autorizado para usar este comando.",
        "common.error_processing_action": "Error al procesar esta accion.",
        "common.movie": "Pelicula",
        "common.tv_show": "Serie",
        "common.bot": "Bot",
        "common.user": "Usuario",
        "common.unknown": "Desconocido",
        "common.unknown_movie": "Pelicula desconocida",
        "common.unknown_series": "Serie desconocida",
        "common.unknown_file": "Archivo desconocido",
        "common.raw_file": "Archivo sin clasificar",
        "common.series": "Serie",
        "common.unknown_year": "Desconocido",
        "common.yes_delete": "✅ Si, borrar",
        "common.yes_delete_it": "✅ Si, borrarla",
        "common.confirm_and_index": "✅ Confirmar e indexar",
        "command.start": "Inicia la interaccion y muestra la ayuda",
        "command.index": "Indexa archivos de un canal (asistente o directo)",
        "command.search": "Busca archivos indexados",
        "command.count": "Estadisticas de la base de datos",
        "command.save_db": "Crea una copia de seguridad",
        "command.load_db": "Restaura desde una copia (respondiendo a un JSON)",
        "command.del": "Elimina una entrada de TMDb",
        "command.del_channel": "Elimina todas las entradas de un chat ID",
        "command.del_db": "Elimina una base de datos",
        "command.token": "Genera un token de acceso para la API",
        "command.log": "Descarga el archivo de log del bot",
        "start.welcome": (
            "🚀 **Jackgram v{version}**\n\n"
            "👋 **Bienvenido a JackgramBot!**\n\n"
            "**📌 Indexacion**\n"
            "/index — Indexa archivos de un canal (asistente o directo)\n\n"
            "**🔍 Busqueda y exploracion**\n"
            "/search `<query>` — Busca archivos indexados\n"
            "/count — Estadisticas de la base de datos\n\n"
            "**🗃️ Gestion de base de datos**\n"
            "/del `<tmdb_id>` — Elimina una entrada de TMDb\n"
            "/del_channel `<chat_id>` — Elimina todas las entradas de un chat\n"
            "/save_db — Crea una copia de seguridad\n"
            "/load_db — Restaura una copia (respondiendo a un JSON)\n"
            "/del_db `<name>` — Elimina una base de datos\n\n"
            "**🔧 Admin**\n"
            "/token — Genera un token de acceso para la API\n"
            "/log — Descarga el archivo `bot.log`\n\n"
            "🧙‍♂️ **Contribuir:** envia un archivo multimedia para iniciar el asistente de contribucion!\n"
            "🚀 Los archivos publicados en canales indexados se procesan automaticamente!"
        ),
        "search.use_query": "Usa /search <query>",
        "search.no_results": 'No se encontraron resultados para "{query}".',
        "search.failed_session": "❌ No se pudo crear la sesion de busqueda. Intentalo de nuevo.",
        "search.results_view": (
            "🔍 Resultados para: **{query}**\n"
            "Pagina `{page}/{total_pages}` • Total: **{total_results}**\n\n"
            "Selecciona un resultado:"
        ),
        "search.series_not_found": "❌ No se encontro la serie en la sesion activa.",
        "search.seasons_view": (
            "📺 **{title}**\n"
            "Temporadas • Pagina `{page}/{total_pages}`\n\n"
            "Elige una temporada:"
        ),
        "search.season_label": "Temporada {season_number} ({episode_count} eps)",
        "search.season_not_selected": "❌ No se ha seleccionado una temporada.",
        "search.episodes_view": (
            "📺 **{title}**\n"
            "Temporada **{season_number}** • Pagina `{page}/{total_pages}`\n\n"
            "Elige un episodio:"
        ),
        "search.episode_fallback_title": "Episodio {episode_number}",
        "search.episode_label": "E{episode_number:02d} • {episode_title} ({files_count} archivos)",
        "search.selected_item_not_found": "❌ No se encontro el elemento seleccionado.",
        "search.quality_view": (
            "{header}\n"
            "Archivos • Pagina `{page}/{total_pages}`\n\n"
            "Elige calidad/archivo:"
        ),
        "search.this_search_expired": "Esta busqueda ha expirado.",
        "search.this_search_expired_retry": "Esta busqueda ha expirado. Envia tu consulta otra vez.",
        "search.these_buttons_not_for_you": "Estos botones no son para ti.",
        "search.closed": "❌ Busqueda cerrada.",
        "search.invalid_page": "Pagina invalida.",
        "search.invalid_selection": "Seleccion invalida.",
        "search.invalid_season": "Temporada invalida.",
        "search.invalid_series_selection": "Seleccion de serie invalida.",
        "search.invalid_episode": "Episodio invalido.",
        "search.invalid_episode_selection": "Seleccion de episodio invalida.",
        "search.invalid_file_selection": "Seleccion de archivo invalida.",
        "search.file_source_not_found": "No se encontro el origen del archivo.",
        "search.preparing_file": "Preparando archivo...",
        "search.source_channel_inaccessible": (
            "El bot no puede acceder al mensaje del canal de origen. Revisa el acceso del bot al canal de logs."
        ),
        "search.telegram_did_not_forward": "Telegram no reenvio este archivo. Intentalo de nuevo.",
        "search.file_sent": "✅ Archivo enviado.",
        "search.invalid_navigation": "Navegacion invalida.",
        "search.unknown_action": "Accion desconocida.",
        "search.floodwait": "FloodWait: espera {seconds}s.",
        "index.invalid_client_type": "Tipo de cliente invalido. Usa 'bot' o 'user'.",
        "index.count_must_be_greater_than_zero": "La cantidad debe ser mayor que 0.",
        "index.invalid_ids": "IDs invalidos. Debes enviar numeros.",
        "index.wizard_intro": (
            "🔍 **Asistente de indexacion**\n\n"
            "Envia el **Chat ID** o el **Username** del canal que quieres indexar."
        ),
        "index.invalid_chat_id_or_username": "❌ Chat ID o Username invalido.",
        "index.range_prompt": (
            "🔢 Envia el **ID del mensaje inicial** y la **cantidad de mensajes** a indexar separados por un espacio (por ejemplo, `1 100`)."
        ),
        "index.invalid_range_format": "❌ Formato invalido. Envia dos numeros separados por un espacio.",
        "index.which_logs_channel": "📂 **Que canal de logs debo usar?**",
        "index.cancelled": "❌ Indexacion cancelada.",
        "index.selected_logs_channel": "✅ Canal de logs seleccionado: **{channel_name}**",
        "index.which_client": (
            "🤖 **Que cliente debo usar para indexar?**\n\n"
            "• **Bot**: Arranca mas rapido, pero tiene limites mas estrictos.\n"
            "• **User**: Usa tus cuentas de usuario en multi-sesion y va mejor para canales grandes."
        ),
        "index.selected_client_starting": "✅ Seleccionado: **{client_type}**\n⏳ Iniciando indexacion...",
        "index.wizard_timed_out": "⏳ El asistente de indexacion expiro.",
        "index.error": "❌ Error: {error}",
        "index.quick_usage": (
            "🚀 **Indexacion rapida**\n\n"
            "Uso: `/index chat_id first_id count client_type [logs_channel]`\n"
            "Ejemplo: `/index -10012345 1 500 bot`\n\n"
            "💡 O simplemente envia `/index` sin parametros para usar el **asistente**!"
        ),
        "index.selected_client_unavailable": "❌ El cliente seleccionado no esta disponible o no esta configurado.",
        "index.progress_start": (
            "🔄 **Indexacion en curso...**\n\n"
            "📡 Canal: `{chat_id}`\n"
            "📨 Rango: `{first_id}` → `{last_id}` ({total_range} mensajes)\n"
            "📂 Destino: `{selected_log_channel}`\n\n"
            "⏳ 0% — Iniciando...\n\n"
            "🚫 No inicies otra indexacion hasta que esta termine."
        ),
        "index.progress_update": (
            "🔄 **Indexacion en curso...**\n\n"
            "📡 Canal: `{chat_id}`\n"
            "`{bar}` **{pct}%**\n\n"
            "  ✅ Indexados: **{indexed}**\n"
            "  ⏭️ Omitidos: {skipped}\n"
            "  ❌ Errores: {errors}\n\n"
            "📨 Mensaje `{current_id}` / `{last_id}`"
        ),
        "index.complete_summary": (
            "✅ **Indexacion completada!**\n\n"
            "📊 **Estadisticas:**\n"
            "  • Indexados: **{indexed}**\n"
            "  • Omitidos (muy pequenos): {skipped_size}\n"
            "  • Omitidos (palabra clave adulta): {skipped_keyword}\n"
            "  • Omitidos (extension invalida): {skipped_ext}\n"
            "  • Omitidos (sin media): {skipped_no_media}\n"
            "  • Errores: {errors}\n\n"
            "Total omitidos por filtros: **{total_skipped}**"
        ),
        "index.floodwait": "⏳ Se recibio un FloodWait de {seconds}s",
        "wizard.multipart_rejected": (
            "❌ **Subida rechazada**\n\n"
            "Parece un archivo dividido/multipart (por ejemplo, Part 1 o CD 2). No se admite porque no puede reproducirse de forma nativa."
        ),
        "wizard.prompt_with_imdb": (
            "🧙‍♂️ **Asistente de contribucion**\n\n"
            "He detectado un archivo multimedia.\n\n"
            "🔍 **IMDb detectado automaticamente:** `{imdb_id}`\n"
            "Es una Pelicula o una Serie?"
        ),
        "wizard.prompt_without_imdb": (
            "🧙‍♂️ **Asistente de contribucion**\n\n"
            "He detectado un archivo multimedia. Es una Pelicula o una Serie?"
        ),
        "wizard.cancelled": "❌ Asistente cancelado.",
        "wizard.selected_type": "✅ Seleccionado: **{type_name}**",
        "wizard.fetching_tmdb": "🔍 Obteniendo datos de TMDb para `{imdb_id}`...",
        "wizard.ask_tmdb_or_title": "Envia el **TMDb ID** o el **titulo exacto** de la {type_name}.",
        "wizard.searching_tmdb": "🔍 Buscando en TMDb...",
        "wizard.tmdb_match_not_found": "❌ No se encontro coincidencia en TMDb. Asistente cancelado.",
        "wizard.tmdb_details_failed": "❌ No se pudieron obtener los detalles de TMDb. Asistente cancelado.",
        "wizard.ask_season_episode": (
            "Es una Serie, pero no pude detectar la Temporada y el Episodio desde el nombre del archivo.\n\n"
            "Responde con Temporada y Episodio en el formato: `S01E05`"
        ),
        "wizard.invalid_format_cancelled": "❌ Formato invalido. Asistente cancelado.",
        "wizard.which_logs_channel": "📂 **Que canal de logs debo usar para guardar este archivo?**",
        "wizard.selected_logs_channel": "✅ Canal de logs seleccionado: **{channel_name}**",
        "wizard.confirm_indexing": (
            "🍿 **Confirmar indexacion**\n\n"
            "Titulo: **{title}** ({year})\n"
            "Tipo: **{type_name}**"
        ),
        "wizard.confirm_indexing_series_extra": "\nTemporada: **{season}** | Episodio: **{episode}**",
        "wizard.indexing": "⏳ Indexando...",
        "wizard.success": (
            "🎉 **Indexado correctamente!**\n\n"
            "El contenido ha sido validado por ti y anadido correctamente a la base de datos."
        ),
        "wizard.timed_out_restart": "⏳ El asistente expiro. Envia el archivo otra vez para reiniciar.",
        "wizard.unexpected_error": "❌ Ocurrio un error inesperado mientras se procesaba.",
        "delete.invalid_tmdb_id": "❌ TMDb ID invalido. Debes enviar un numero.",
        "delete.use_del": "Usa /del <tmdb_id>",
        "delete.entry_deleted": "✅ Entrada eliminada correctamente.",
        "delete.no_document": "No se encontro ningun documento con ese TMDb ID.",
        "delete_channel.invalid_chat_id": "❌ Chat ID invalido. Debes enviar un numero (por ejemplo `-10012345`).",
        "delete_channel.use_del_channel": "Usa /del_channel <chat_id>",
        "delete_channel.confirm": "⚠️ **Estas seguro de que quieres eliminar todas las entradas asociadas al chat `{chat_id}`?**",
        "delete_channel.deletion_cancelled": "❌ Eliminacion cancelada.",
        "delete_channel.deleting": "⏳ Eliminando entradas para `{chat_id}`...",
        "delete_channel.summary": (
            "✅ **Eliminacion completada!**\n\n"
            "📊 **Estadisticas:**\n"
            "  • Archivos sin clasificar eliminados: **{raw_deleted}**\n"
            "  • Peliculas modificadas: **{movies_modified}**\n"
            "  • Series modificadas: **{tv_modified}**\n\n"
            "Tambien se eliminaron las entradas que se quedaron sin archivos."
        ),
        "count.summary": (
            "📊 **Estadisticas de la base de datos**\n\n"
            "🎬 Peliculas: **{movies}**\n"
            "📺 Series: **{tv}**\n"
            "📁 Archivos sin clasificar: **{files}**\n"
            "━━━━━━━━━━━━━━━━━\n"
            "📦 Total de entradas: **{total}**\n"
            "💾 Almacenamiento total: **{storage}**"
        ),
        "backup.starting": "⏳ **Iniciando copia de seguridad de la base de datos...**",
        "backup.permission_denied": (
            "❌ No se puede crear el directorio de copias `{backup_dir}` — permiso denegado.\n"
            "💡 Configura `BACKUP_DIR` en config.env con una ruta que permita escritura."
        ),
        "backup.progress": (
            "⏳ **Creando copia de seguridad...**\n"
            "Procesando coleccion: `{collection_name}` ({current}/{total})"
        ),
        "backup.writing_file": "💾 **Escribiendo archivo de copia...**",
        "backup.write_failed": "❌ Error al escribir el archivo de copia: {error}",
        "backup.starting_upload": "📤 **Iniciando subida a Telegram...**",
        "backup.upload_progress": (
            "📤 **Subiendo archivo de copia a Telegram...**\n\n"
            "`{bar}` **{pct}%**\n"
            "📦 {current_size} / {total_size}"
        ),
        "backup.completed_caption": (
            "✅ **Copia completada!**\n\n"
            "Se han exportado todas las colecciones y campos, incluyendo los nuevos datos de posters."
        ),
        "restore.reply_with_json": "Responde a un archivo JSON con este comando.",
        "restore.file_must_be_json": "El archivo debe ser un JSON.",
        "restore.invalid_json_file": "No se pudo cargar el archivo. Asegurate de que sea un JSON valido.",
        "restore.invalid_json_structure": (
            "Estructura JSON invalida. El archivo debe contener un diccionario con nombres de coleccion como claves."
        ),
        "restore.invalid_collection_data": "Datos invalidos para la coleccion '{collection_name}'. Se esperaba una lista de documentos.",
        "restore.success": "Base de datos restaurada correctamente desde el archivo subido!",
        "delete_db.use_del_db": "Usa /del_db <database_name>",
        "delete_db.confirm": (
            "⚠️ **Estas seguro de que quieres ELIMINAR por completo la base de datos `{database_name}`?**\n\n"
            "Esta accion es **irreversible**."
        ),
        "delete_db.cancelled": "❌ Eliminacion de la base de datos cancelada.",
        "delete_db.deleted": "✅ La base de datos `{database_name}` ha sido eliminada.",
        "log.caption": "Aqui tienes el archivo bot.log.",
        "log.not_found": "El archivo bot.log no existe.",
    },
}


def get_bot_language() -> str:
    language = (BOT_LANGUAGE or "en").strip().lower()
    if language.startswith("es"):
        return "es"
    return "en"


def t(key: str, **kwargs) -> str:
    language = get_bot_language()
    template = TRANSLATIONS.get(language, {}).get(key)
    if template is None:
        template = TRANSLATIONS["en"].get(key, key)

    if not kwargs:
        return template

    try:
        return template.format(**kwargs)
    except Exception:
        return template
