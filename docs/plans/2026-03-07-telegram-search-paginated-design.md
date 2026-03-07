# Diseno: busqueda interactiva en el bot de Telegram

Fecha: 2026-03-07
Proyecto: Jackgram
Estado: Aprobado por usuario

## 1) Objetivo

Permitir que un usuario escriba el nombre de una pelicula o serie en el chat privado del bot y reciba una botonera con resultados paginados. Al seleccionar un resultado:

- Pelicula o raw: mostrar botonera de calidades/archivos.
- Serie: mostrar botonera de temporadas, luego episodios, y luego calidades/archivos.
- Al elegir una calidad, el bot envia el archivo real de Telegram en el mismo chat.

## 2) Requisitos acordados

- Acceso: disponible para todos los usuarios en chat privado.
- Activacion: texto libre + comando `/search`.
- Series: flujo con segunda botonera (temporadas/episodios).
- Multiples archivos/calidades: mostrar botonera para elegir.
- Entrega final: enviar archivo de Telegram (no solo link).
- Tipo de resultados: incluir resultados TMDb y archivos raw.

## 3) Enfoque elegido

Se implementara sesion en memoria con expiracion (TTL) por busqueda.

### Justificacion

- Menor complejidad que persistir sesiones en MongoDB.
- Mejor UX que un enfoque totalmente stateless para navegacion multinivel.
- Adecuado para callbacks y paginacion en Telethon.

### Trade-off aceptado

- Si el bot reinicia, los botones viejos pueden expirar y se pide repetir la busqueda.

## 4) Arquitectura propuesta

### 4.1 Modulos

- `jackgram/bot/plugins/start.py`
  - Mantener `/search`.
  - Agregar handler de texto libre en privado (ignorar mensajes que empiezan por `/`).
  - Delegar en funciones comunes para no duplicar logica.

- `jackgram/bot/search_sessions.py` (nuevo)
  - Store en memoria para sesiones de busqueda.
  - API sugerida:
    - `create_session(sender_id, query, results)`
    - `get_session(session_id)`
    - `update_session(session_id, **state)`
    - `delete_session(session_id)`
    - `cleanup_expired()`
  - TTL configurable (por defecto 10-15 min).

- `jackgram/utils/database.py`
  - Reusar `search_tmdb(query, page, per_page)` para traer resultados.
  - No cambiar esquema de datos.

### 4.2 Modelo de estado de sesion

Cada sesion guarda:

- `session_id`
- `sender_id`
- `query`
- `created_at`, `expires_at`
- `results` (snapshot de IDs y metadatos minimos para UI)
- `page`
- `view` actual (`results`, `series_seasons`, `series_episodes`, `qualities`)
- `selected_item` (cuando aplique)

## 5) Flujo de interaccion

### 5.1 Inicio de busqueda

Entrada valida:

- `/search <query>`
- Texto libre en privado (no comando)

Pasos:

1. Validar query no vacia.
2. Buscar en DB.
3. Crear sesion.
4. Enviar mensaje con botonera de resultados paginados.

### 5.2 Nivel 1: resultados

- Boton por item con icono y titulo:
  - `🎬` pelicula
  - `📺` serie
  - `📁` raw
- Navegacion: `⬅️` / `➡️`
- Control: `❌ Cerrar`

### 5.3 Nivel 2 (solo series): temporadas

- Botones por temporada detectada en `seasons`.
- Boton `⬅️ Volver` a resultados.

### 5.4 Nivel 3 (solo series): episodios

- Botones por episodio disponible en la temporada.
- Boton `⬅️ Volver` a temporadas.

### 5.5 Nivel final: calidades/archivos

- Mostrar una opcion por archivo disponible (pelicula/raw o episodio):
  - Calidad
  - Tamaño legible
  - Codec/fuente si existe
- Al seleccionar:
  - Obtener `chat_id` y `message_id` del `file_info`.
  - Enviar el archivo al chat privado del usuario.
  - Confirmar con mensaje breve.

## 6) Callback protocol (compacto)

Prefijo recomendado: `srch`.

Ejemplos de acciones:

- `srch:<sid>:page:<n>`
- `srch:<sid>:pick:<idx>`
- `srch:<sid>:season:<n>`
- `srch:<sid>:episode:<n>`
- `srch:<sid>:quality:<idx>`
- `srch:<sid>:back:<view>`
- `srch:<sid>:close`

Reglas:

- Mantener callback corto (< 64 bytes).
- Nunca confiar en indice sin validar contra estado de sesion.

## 7) Seguridad y validaciones

- Callback bloqueado si `event.sender_id != session.sender_id`.
- Sesion expirada -> alerta: "Esta busqueda expiro, envia el titulo de nuevo".
- Indices/paginas fuera de rango -> ignorar o responder con alerta.
- Errores Telethon (FloodWait, chat privado, mensaje invalido) -> mensaje amigable.

## 8) Manejo de errores UX

- Sin resultados: mensaje claro con sugerencia de reintento.
- Resultado no disponible por cambio de DB: notificar y volver a resultados.
- Archivo inaccesible: notificar y permitir elegir otra calidad.

## 9) Pruebas de aceptacion

1. Texto libre -> resultados paginados -> pelicula -> calidad -> archivo enviado.
2. Texto libre -> resultados -> serie -> temporada -> episodio -> calidad -> archivo enviado.
3. `/search` mantiene el mismo flujo.
4. Paginacion correcta en primera/intermedia/ultima pagina.
5. Callback de sesion expirada devuelve alerta.
6. Usuario distinto no puede usar botones de otra sesion.
7. Resultados mezclados TMDb + raw se renderizan correctamente.

## 10) Fuera de alcance en esta iteracion

- Persistencia de sesiones en MongoDB.
- Sincronizacion entre multiples instancias de bot para sesiones.
- Ranking avanzado de resultados por fuzzy score custom.

## 11) Criterio de exito

El usuario puede buscar por texto y navegar por botoneras paginadas hasta seleccionar un archivo, y el bot envia ese archivo en el mismo chat privado sin usar enlaces externos como flujo principal.
