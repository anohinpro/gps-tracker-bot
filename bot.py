"""
GPS Tracker Telegram Bot
Кнопочный бот с админ-панелью для редактирования контента
"""

import os
import json
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Пути к файлам
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_FILE = os.path.join(DATA_DIR, "content.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
MEDIA_DIR = os.path.join(DATA_DIR, "media")

# Состояния для ConversationHandler (админка)
(ADMIN_AUTH, ADMIN_MENU, EDIT_SELECT_SECTION, EDIT_SELECT_ITEM, 
 EDIT_TEXT, EDIT_MEDIA, ADD_BUTTON, DELETE_BUTTON) = range(8)

# --- Утилиты для работы с данными ---

def load_json(filepath: str) -> dict:
    """Загрузка JSON файла"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(filepath: str, data: dict):
    """Сохранение JSON файла"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_content() -> dict:
    """Получение контента"""
    return load_json(CONTENT_FILE)

def save_content(content: dict):
    """Сохранение контента"""
    save_json(CONTENT_FILE, content)

def get_config() -> dict:
    """Получение конфигурации"""
    return load_json(CONFIG_FILE)

# --- Построение клавиатуры ---

def build_keyboard(buttons: list, back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Построение inline клавиатуры из списка кнопок"""
    keyboard = []
    for btn in buttons:
        if isinstance(btn, list):
            # Несколько кнопок в ряд
            row = []
            for b in btn:
                if "url" in b:
                    row.append(InlineKeyboardButton(b["text"], url=b["url"]))
                else:
                    row.append(InlineKeyboardButton(b["text"], callback_data=b["callback"]))
            keyboard.append(row)
        else:
            # Одна кнопка в ряд
            if "url" in btn:
                keyboard.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
            else:
                keyboard.append([InlineKeyboardButton(btn["text"], callback_data=btn["callback"])])

    if back_callback:
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(keyboard)

# --- Отправка сообщения с медиа ---

async def send_content(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    keyboard: InlineKeyboardMarkup,
    media: Optional[dict] = None,
    edit: bool = True
):
    """Отправка или редактирование сообщения с опциональным медиа"""
    query = update.callback_query
    
    if media and media.get("file_id"):
        media_type = media.get("type", "photo")
        file_id = media["file_id"]
        
        if edit and query:
            try:
                # Пробуем отредактировать медиа
                if media_type == "photo":
                    await query.edit_message_media(
                        media=InputMediaPhoto(media=file_id, caption=text, parse_mode='HTML'),
                        reply_markup=keyboard
                    )
                elif media_type == "video":
                    await query.edit_message_media(
                        media=InputMediaVideo(media=file_id, caption=text, parse_mode='HTML'),
                        reply_markup=keyboard
                    )
                return
            except Exception as e:
                logger.warning(f"Не удалось отредактировать медиа: {e}")
                # Удаляем старое сообщение и отправляем новое
                try:
                    await query.message.delete()
                except:
                    pass
        
        # Отправляем новое сообщение с медиа
        chat_id = query.message.chat_id if query else update.effective_chat.id
        if media_type == "photo":
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        elif media_type == "video":
            await context.bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
    else:
        # Только текст
        if edit and query:
            try:
                # Проверяем, есть ли медиа в текущем сообщении
                if query.message.photo or query.message.video:
                    # Удаляем старое сообщение с медиа и отправляем новое текстовое
                    await query.message.delete()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                else:
                    await query.edit_message_text(
                        text=text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                return
            except Exception as e:
                error_str = str(e).lower()
                # Игнорируем ошибку "message is not modified"
                if "message is not modified" in error_str:
                    return
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                # При других ошибках пробуем отправить новое сообщение

        # Отправляем новое сообщение
        chat_id = query.message.chat_id if query else update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

# --- Основные обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await menu(update, context, edit=False)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = True):
    """Главное меню"""
    content = get_content()
    menu_data = content.get("menu", {})
    
    text = menu_data.get("text", "🔗 <b>GPS-трекер AK-39B</b>\n\nВыберите раздел:")
    buttons = menu_data.get("buttons", [
        {"text": "🔗 Инструкция и функционал", "callback": "section_instruction"},
        {"text": "ℹ️ Об этом устройстве", "callback": "section_about"},
        {"text": "❓ Решение проблем", "callback": "section_problems"},
        {"text": "📞 Поддержка", "callback": "section_support"}
    ])
    media = menu_data.get("media")
    
    keyboard = build_keyboard(buttons)
    await send_content(update, context, text, keyboard, media, edit)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback запросов"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Специальные callbacks
    if callback_data == "menu":
        await menu(update, context)
        return
    
    if callback_data == "back_menu":
        await menu(update, context)
        return
    
    # Обработка динамических разделов
    content = get_content()
    
    if callback_data in content:
        section = content[callback_data]
        text = section.get("text", "")
        buttons = section.get("buttons", [])
        back = section.get("back")
        media = section.get("media")
        
        keyboard = build_keyboard(buttons, back)
        await send_content(update, context, text, keyboard, media)
    else:
        # Callback не найден
        await query.edit_message_text(
            text="⚠️ Раздел не найден. Возвращаемся в меню...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В меню", callback_data="menu")
            ]])
        )

# --- Админ-панель ---

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы с админкой - запрос пароля"""
    logger.info("=== admin_start вызвана ===")
    try:
        await update.message.reply_text(
            "🔐 <b>Админ-панель</b>\n\nВведите пароль:",
            parse_mode='HTML'
        )
        logger.info("Сообщение с запросом пароля отправлено")
        return ADMIN_AUTH
    except Exception as e:
        logger.error(f"Ошибка в admin_start: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def admin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка пароля админки"""
    try:
        config = get_config()
        password = config.get("admin_password", "admin123")

        logger.info(f"Попытка входа в админку. Введённый пароль: {update.message.text}")

        if update.message.text == password:
            context.user_data['is_admin'] = True
            logger.info("Пароль верный, показываем меню")
            await show_admin_menu(update, context)
            return ADMIN_MENU
        else:
            await update.message.reply_text("❌ Неверный пароль. Попробуйте снова или /cancel для выхода.")
            return ADMIN_AUTH
    except Exception as e:
        logger.error(f"Ошибка в admin_auth: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ADMIN_AUTH

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню админки"""
    try:
        logger.info("show_admin_menu вызвана")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Редактировать контент", callback_data="admin_edit")],
            [InlineKeyboardButton("➕ Добавить раздел", callback_data="admin_add")],
            [InlineKeyboardButton("🗑 Удалить раздел", callback_data="admin_delete")],
            [InlineKeyboardButton("📋 Список разделов", callback_data="admin_list")],
            [InlineKeyboardButton("🔑 Сменить пароль", callback_data="admin_password")],
            [InlineKeyboardButton("❌ Выход", callback_data="admin_exit")]
        ])

        text = "⚙️ <b>Админ-панель</b>\n\nВыберите действие:"

        if update.callback_query:
            logger.info("Редактируем сообщение через callback_query")
            await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
        else:
            logger.info("Отправляем новое сообщение через reply_text")
            await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

        logger.info("show_admin_menu успешно завершена")
        return ADMIN_MENU
    except Exception as e:
        logger.error(f"Ошибка в show_admin_menu: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callbacks админки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_exit":
        context.user_data.clear()
        await query.edit_message_text("👋 Вы вышли из админ-панели.")
        return ConversationHandler.END
    
    elif query.data == "admin_list":
        content = get_content()
        sections = "\n".join([f"• <code>{k}</code>" for k in content.keys()])
        text = f"📋 <b>Список разделов:</b>\n\n{sections}"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        ]])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MENU
    
    elif query.data == "admin_back":
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    elif query.data == "admin_edit":
        # Показываем главное меню + его разделы
        content = get_content()
        menu_section = content.get("menu", {})

        buttons = []
        # Кнопка редактирования главного меню
        buttons.append([InlineKeyboardButton("✏️ Редактировать: Главное меню", callback_data="edit_menu")])
        buttons.append([InlineKeyboardButton("─────────────", callback_data="noop")])

        # Подразделы из главного меню
        for btn in menu_section.get("buttons", []):
            btn_text = btn.get("text", "")
            btn_callback = btn.get("callback", "")
            if btn_callback:
                buttons.append([InlineKeyboardButton(f"📂 {btn_text}", callback_data=f"browse_{btn_callback}")])

        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])

        await query.edit_message_text(
            "📝 <b>Редактирование контента</b>\n\n"
            "Выберите раздел для навигации или редактирования:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return EDIT_SELECT_SECTION
    
    elif query.data == "admin_add":
        await query.edit_message_text(
            "➕ <b>Добавление нового раздела</b>\n\n"
            "Введите ID нового раздела (латиницей, без пробелов).\n"
            "Например: <code>section_new</code>\n\n"
            "Или /cancel для отмены.",
            parse_mode='HTML'
        )
        return ADD_BUTTON
    
    elif query.data == "admin_delete":
        content = get_content()
        buttons = []
        for key in content.keys():
            if key != "menu":  # Защищаем главное меню от удаления
                buttons.append([InlineKeyboardButton(f"🗑 {key}", callback_data=f"delete_{key}")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
        
        await query.edit_message_text(
            "🗑 <b>Выберите раздел для удаления:</b>\n\n"
            "⚠️ Это действие необратимо!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return DELETE_BUTTON
    
    elif query.data == "admin_password":
        await query.edit_message_text(
            "🔑 <b>Смена пароля</b>\n\nВведите новый пароль:",
            parse_mode='HTML'
        )
        context.user_data['changing_password'] = True
        return EDIT_TEXT
    
    return ADMIN_MENU

async def edit_section_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор раздела - иерархическая навигация"""
    query = update.callback_query
    await query.answer()

    content = get_content()

    # Игнорируем разделитель
    if query.data == "noop":
        return EDIT_SELECT_SECTION

    if query.data == "admin_back":
        await show_admin_menu(update, context)
        return ADMIN_MENU

    # Возврат в главное меню редактирования
    if query.data == "admin_edit":
        menu_section = content.get("menu", {})
        buttons = []
        buttons.append([InlineKeyboardButton("✏️ Редактировать: Главное меню", callback_data="edit_menu")])
        buttons.append([InlineKeyboardButton("─────────────", callback_data="noop")])
        for btn in menu_section.get("buttons", []):
            btn_text = btn.get("text", "")
            btn_callback = btn.get("callback", "")
            if btn_callback:
                buttons.append([InlineKeyboardButton(f"📂 {btn_text}", callback_data=f"browse_{btn_callback}")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
        await query.edit_message_text(
            "📝 <b>Редактирование контента</b>\n\n"
            "Выберите раздел для навигации или редактирования:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return EDIT_SELECT_SECTION

    # Навигация по разделам (browse_SECTION)
    if query.data.startswith("browse_"):
        section_id = query.data.replace("browse_", "")
        section = content.get(section_id, {})
        section_text = section.get("text", "").split("\n")[0][:50]  # Первая строка текста

        buttons = []
        # Кнопка редактирования текущего раздела
        buttons.append([InlineKeyboardButton(f"✏️ Редактировать этот раздел", callback_data=f"edit_{section_id}")])

        # Подразделы (если есть кнопки)
        section_buttons = section.get("buttons", [])
        if section_buttons:
            buttons.append([InlineKeyboardButton("─────────────", callback_data="noop")])
            for btn in section_buttons:
                btn_text = btn.get("text", "")
                btn_callback = btn.get("callback", "")
                # Пропускаем URL-кнопки
                if btn_callback and "url" not in btn:
                    buttons.append([InlineKeyboardButton(f"📂 {btn_text}", callback_data=f"browse_{btn_callback}")])

        # Кнопка назад - к родителю или в главное меню редактирования
        back_section = section.get("back", "menu")
        if back_section == "menu":
            buttons.append([InlineKeyboardButton("◀️ В главное меню", callback_data="admin_edit")])
        else:
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"browse_{back_section}")])

        await query.edit_message_text(
            f"📂 <b>{section_text}</b>\n\n"
            f"<code>{section_id}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return EDIT_SELECT_SECTION

    # Переход к редактированию раздела (edit_SECTION)
    if query.data.startswith("edit_"):
        section_id = query.data.replace("edit_", "")
        context.user_data['editing_section'] = section_id
        section = content.get(section_id, {})
        section_text = section.get("text", "").split("\n")[0][:50]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Текст", callback_data="edit_text")],
            [InlineKeyboardButton("🖼 Медиа (фото/видео)", callback_data="edit_media")],
            [InlineKeyboardButton("🔘 Кнопки", callback_data="edit_buttons")],
            [InlineKeyboardButton("◀️ Назад", callback_data=f"browse_{section_id}")]
        ])

        await query.edit_message_text(
            f"✏️ <b>Редактирование:</b>\n{section_text}\n\n"
            f"<code>{section_id}</code>\n\nЧто изменить?",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return EDIT_SELECT_ITEM

    return EDIT_SELECT_SECTION

async def edit_item_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора элемента для редактирования"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("browse_"):
        # Возврат к навигации по разделу
        # Эмулируем вызов edit_section_select
        return await edit_section_select(update, context)
    
    section_id = context.user_data.get('editing_section')
    content = get_content()
    section = content.get(section_id, {})
    
    if query.data == "edit_text":
        current_text = section.get("text", "Текст не задан")
        await query.edit_message_text(
            f"📝 <b>Текущий текст:</b>\n\n{current_text}\n\n"
            "─────────────────\n"
            "Отправьте новый текст (поддерживается HTML-разметка).\n"
            "Или /cancel для отмены.",
            parse_mode='HTML'
        )
        context.user_data['edit_type'] = 'text'
        return EDIT_TEXT
    
    elif query.data == "edit_media":
        current_media = section.get("media", {})
        media_info = "Не задано"
        if current_media.get("file_id"):
            media_info = f"Тип: {current_media.get('type', 'photo')}\nID: {current_media.get('file_id', '')[:20]}..."
        
        await query.edit_message_text(
            f"🖼 <b>Текущее медиа:</b>\n{media_info}\n\n"
            "─────────────────\n"
            "Отправьте фото или видео для замены.\n"
            "Отправьте /clear чтобы удалить медиа.\n"
            "Или /cancel для отмены.",
            parse_mode='HTML'
        )
        context.user_data['edit_type'] = 'media'
        return EDIT_MEDIA
    
    elif query.data == "edit_buttons":
        buttons = section.get("buttons", [])
        buttons_text = "\n".join([f"{i+1}. {b.get('text', '')} → {b.get('callback', '')}" 
                                  for i, b in enumerate(buttons)])
        if not buttons_text:
            buttons_text = "Кнопки не заданы"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить кнопку", callback_data="btn_add")],
            [InlineKeyboardButton("🗑 Удалить кнопку", callback_data="btn_delete")],
            [InlineKeyboardButton("✏️ Изменить кнопку", callback_data="btn_edit")],
            [InlineKeyboardButton("◀️ Назад", callback_data="edit_back")]
        ])
        
        await query.edit_message_text(
            f"🔘 <b>Текущие кнопки:</b>\n\n{buttons_text}\n\n"
            "Выберите действие:",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return EDIT_SELECT_ITEM
    
    elif query.data == "btn_add":
        await query.edit_message_text(
            "➕ <b>Добавление кнопки</b>\n\n"
            "Введите данные кнопки в формате:\n"
            "<code>Текст кнопки | callback_id</code>\n\n"
            "Пример: <code>📱 Инструкция | section_instruction</code>\n\n"
            "Или /cancel для отмены.",
            parse_mode='HTML'
        )
        context.user_data['edit_type'] = 'btn_add'
        return EDIT_TEXT
    
    elif query.data == "btn_delete":
        buttons = section.get("buttons", [])
        if not buttons:
            await query.answer("Кнопок нет!", show_alert=True)
            return EDIT_SELECT_ITEM
        
        kb = []
        for i, b in enumerate(buttons):
            kb.append([InlineKeyboardButton(f"🗑 {b.get('text', '')}", callback_data=f"delbtn_{i}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="edit_buttons")])
        
        await query.edit_message_text(
            "🗑 <b>Выберите кнопку для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return EDIT_SELECT_ITEM
    
    elif query.data.startswith("delbtn_"):
        btn_index = int(query.data.replace("delbtn_", ""))
        content = get_content()
        section = content.get(section_id, {})
        buttons = section.get("buttons", [])
        
        if 0 <= btn_index < len(buttons):
            deleted = buttons.pop(btn_index)
            section["buttons"] = buttons
            content[section_id] = section
            save_content(content)
            await query.answer(f"Кнопка '{deleted.get('text')}' удалена!", show_alert=True)
        
        # Возврат к редактированию кнопок
        query.data = "edit_buttons"
        return await edit_item_select(update, context)
    
    elif query.data == "btn_edit":
        buttons = section.get("buttons", [])
        if not buttons:
            await query.answer("Кнопок нет!", show_alert=True)
            return EDIT_SELECT_ITEM
        
        kb = []
        for i, b in enumerate(buttons):
            kb.append([InlineKeyboardButton(f"✏️ {b.get('text', '')}", callback_data=f"editbtn_{i}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="edit_buttons")])
        
        await query.edit_message_text(
            "✏️ <b>Выберите кнопку для редактирования:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return EDIT_SELECT_ITEM
    
    elif query.data.startswith("editbtn_"):
        btn_index = int(query.data.replace("editbtn_", ""))
        context.user_data['editing_btn_index'] = btn_index
        
        content = get_content()
        section = content.get(section_id, {})
        buttons = section.get("buttons", [])
        btn = buttons[btn_index] if btn_index < len(buttons) else {}
        
        await query.edit_message_text(
            f"✏️ <b>Редактирование кнопки:</b>\n"
            f"Текущий текст: {btn.get('text', '')}\n"
            f"Текущий callback: {btn.get('callback', '')}\n\n"
            "Введите новые данные в формате:\n"
            "<code>Текст кнопки | callback_id</code>\n\n"
            "Или /cancel для отмены.",
            parse_mode='HTML'
        )
        context.user_data['edit_type'] = 'btn_edit'
        return EDIT_TEXT
    
    return EDIT_SELECT_ITEM

async def process_text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых изменений"""
    text = update.message.text
    
    if text == "/cancel":
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    # Смена пароля
    if context.user_data.get('changing_password'):
        config = get_config()
        config['admin_password'] = text
        save_json(CONFIG_FILE, config)
        context.user_data.pop('changing_password', None)
        await update.message.reply_text("✅ Пароль успешно изменён!")
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    section_id = context.user_data.get('editing_section')
    edit_type = context.user_data.get('edit_type')
    content = get_content()
    
    if edit_type == 'text':
        if section_id not in content:
            content[section_id] = {}
        content[section_id]['text'] = text
        save_content(content)
        await update.message.reply_text("✅ Текст успешно обновлён!")
    
    elif edit_type == 'btn_add':
        if '|' not in text:
            await update.message.reply_text("❌ Неверный формат. Используйте: Текст | callback")
            return EDIT_TEXT
        
        parts = text.split('|')
        btn_text = parts[0].strip()
        btn_callback = parts[1].strip()
        
        if section_id not in content:
            content[section_id] = {}
        if 'buttons' not in content[section_id]:
            content[section_id]['buttons'] = []
        
        content[section_id]['buttons'].append({
            "text": btn_text,
            "callback": btn_callback
        })
        save_content(content)
        await update.message.reply_text(f"✅ Кнопка '{btn_text}' добавлена!")
    
    elif edit_type == 'btn_edit':
        if '|' not in text:
            await update.message.reply_text("❌ Неверный формат. Используйте: Текст | callback")
            return EDIT_TEXT
        
        parts = text.split('|')
        btn_text = parts[0].strip()
        btn_callback = parts[1].strip()
        btn_index = context.user_data.get('editing_btn_index', 0)
        
        if section_id in content and 'buttons' in content[section_id]:
            if btn_index < len(content[section_id]['buttons']):
                content[section_id]['buttons'][btn_index] = {
                    "text": btn_text,
                    "callback": btn_callback
                }
                save_content(content)
                await update.message.reply_text(f"✅ Кнопка обновлена!")
    
    await show_admin_menu(update, context)
    return ADMIN_MENU

async def process_media_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиа"""
    section_id = context.user_data.get('editing_section')
    content = get_content()
    
    if update.message.text == "/clear":
        if section_id in content:
            content[section_id]['media'] = {}
            save_content(content)
        await update.message.reply_text("✅ Медиа удалено!")
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    if update.message.text == "/cancel":
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id  # Берём наибольшее разрешение
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"
    else:
        await update.message.reply_text("❌ Отправьте фото или видео!")
        return EDIT_MEDIA
    
    if section_id not in content:
        content[section_id] = {}
    
    content[section_id]['media'] = {
        "type": media_type,
        "file_id": file_id
    }
    save_content(content)
    
    await update.message.reply_text(f"✅ {media_type.capitalize()} успешно обновлено!")
    await show_admin_menu(update, context)
    return ADMIN_MENU

async def add_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление нового раздела"""
    text = update.message.text
    
    if text == "/cancel":
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    # Проверка формата ID
    if ' ' in text or not text.isascii():
        await update.message.reply_text(
            "❌ ID должен быть на латинице без пробелов!\n"
            "Пример: <code>section_new</code>",
            parse_mode='HTML'
        )
        return ADD_BUTTON
    
    content = get_content()
    
    if text in content:
        await update.message.reply_text("❌ Раздел с таким ID уже существует!")
        return ADD_BUTTON
    
    # Создаём новый раздел
    content[text] = {
        "text": "Новый раздел. Отредактируйте текст в админ-панели.",
        "buttons": [],
        "back": "menu"
    }
    save_content(content)
    
    await update.message.reply_text(
        f"✅ Раздел <code>{text}</code> создан!\n\n"
        "Теперь отредактируйте его содержимое в админ-панели.",
        parse_mode='HTML'
    )
    await show_admin_menu(update, context)
    return ADMIN_MENU

async def delete_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление раздела"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_back":
        await show_admin_menu(update, context)
        return ADMIN_MENU
    
    section_id = query.data.replace("delete_", "")
    content = get_content()
    
    if section_id in content:
        del content[section_id]
        save_content(content)
        await query.answer(f"Раздел '{section_id}' удалён!", show_alert=True)
    
    await show_admin_menu(update, context)
    return ADMIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    context.user_data.clear()
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

# --- Главная функция ---

def main():
    """Запуск бота"""
    config = get_config()
    token = config.get("bot_token") or os.environ.get("BOT_TOKEN")
    
    if not token:
        print("❌ Ошибка: Укажите токен бота в config.json или переменной окружения BOT_TOKEN")
        return
    
    # Создаём приложение
    app = Application.builder().token(token).build()
    
    # Обработчик админ-панели (ConversationHandler)
    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_auth)],
            ADMIN_MENU: [CallbackQueryHandler(admin_callback)],
            EDIT_SELECT_SECTION: [CallbackQueryHandler(edit_section_select)],
            EDIT_SELECT_ITEM: [CallbackQueryHandler(edit_item_select)],
            EDIT_TEXT: [MessageHandler(filters.TEXT, process_text_edit)],
            EDIT_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO, process_media_edit),
                MessageHandler(filters.TEXT, process_media_edit)
            ],
            ADD_BUTTON: [MessageHandler(filters.TEXT, add_section)],
            DELETE_BUTTON: [CallbackQueryHandler(delete_section)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Добавляем обработчики
    app.add_handler(admin_handler)
    logger.info("admin_handler добавлен")
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Запускаем бота
    logger.info("Все обработчики добавлены, запускаем polling...")
    print("🚀 Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
