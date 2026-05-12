"""Loads and registers modules with trust check"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import ast
import asyncio
import contextlib
import functools
import importlib
import difflib
import inspect
import io
import logging
import os
import re
import shutil
import sys
import time
import typing
import uuid
import tempfile
from collections import ChainMap
from importlib.machinery import ModuleSpec
from urllib.parse import urlparse

import requests
from hikkatl.errors.rpcerrorlist import MediaCaptionTooLongError
from hikkatl.tl.functions.channels import JoinChannelRequest
from hikkatl.tl.types import Channel, Message, PeerUser

from .. import loader, main, utils
from .._local_storage import RemoteStorage
from ..compat import geek
from ..inline.types import InlineCall
from ..types import CoreOverwriteError, CoreUnloadError

logger = logging.getLogger(__name__)

TRUSTED_DEVS = [
    "@FrontendVSCode",
    "@hikariatama",
    "@Python_Javs",
    "@NEBULASoftware",
    "@ETHERION_official",
]

TRUSTED_LINKS = [
    "tg://chat?id=3767066236",
    "tg://chat?id=2362604203",
    "tg://chat?id=3837206192",
    "tg://user?id=8174117949",
    "https://t.me/Python_Javs",
    "https://t.me/NEBULASoftware",
    "https://t.me/ETHERION_official",
    "https://raw.githubusercontent.com/Alia-Ether/Hikka/refs/heads/main",
    "https://raw.githubusercontent.com/Puthon-javs/my_module.hikka/refs/heads/main",
]

DEFAULT_REPO = "https://raw.githubusercontent.com/Alia-Ether/Hikka/refs/heads/main"
SECONDARY_REPO = "https://raw.githubusercontent.com/Puthon-javs/my_module.hikka/refs/heads/main"

OVERWRITE_IMAGE = "https://i.pinimg.com/736x/56/4b/ff/564bffbec8e597023f82b747e2ff61d8.jpg"


class FakeOne:
    def __eq__(self, other):
        return other == -1 or isinstance(other, FakeOne)

    def __bool__(self):
        return False


MODULE_LOADING_FORBIDDEN = FakeOne()
MODULE_LOADING_FAILED = 0
MODULE_LOADING_SUCCESS = 1


@loader.tds
class LoaderMod(loader.Module):
    strings = {
        "name": "Loader",
        "trusted_source": "✅ Доверенный источник",
        "untrusted_install_message": "\n\n🍇 <b>Важно знать</b>\n\nВы установили модуль из непроверенного источника 🌸\n\nМы не несем ответственности за:\n▫️ Состояние устройства\n▫️ Сохранность аккаунта\n▫️ Потерю данных",
        "overwrite_warning": "<blockquote>😖 <b>Этот модуль попытался перезаписать встроенную команду</b> <code>{}{}</code>\n\n🍇 <i>Это не ошибка, а мера безопасности, требуемая для предотвращения замены команд встроенных модулей всяким хламом. Не сообщайте о ней в support чате</i></blockquote>",
        "confirm_overwrite": "✅ Подтвердить перезапись",
        "close_btn": "❌ Отмена",
        "overwrite_success": "✅ Перезапись выполнена успешно!",
        "overwrite_error": "❌ Ошибка при перезаписи: {}",
        "usage_re": "⚠️ Использование:\n.re raw <ссылка>\n.re file",
        "need_raw_url": "⚠️ Укажи raw-ссылку на модуль",
        "invalid_mode": "⚠️ Неверный режим. Используй raw или file",
        "overwrite_in_progress": "🔄 Выполняется перезапись...",
        "download_error": "❌ Ошибка загрузки: {}",
        "no_file_or_reply": "⚠️ Нет файла или реплая на файл",
        "file_read_error": "❌ Ошибка чтения файла: {}",
        "cannot_get_code": "❌ Не удалось получить код модуля",
        "searching_modules": "🔍 Ищу модуль в репозиториях...",
        "available_modules": "📦 Доступные модули\n\n☁️ {}\n\n{}",
        "loading_modules": "Loading modules: {}",
        "module_not_found": "❌ Модуль не найден в репозиториях",
        "downloading_module": "📥 Устанавливаю <code>{}</code>...",
        "download_failed": "❌ Не удалось загрузить модуль",
        "loading_from_file": "📥 Загружаю модуль из файла...",
        "invalid_encoding": "❌ Неверная кодировка файла",
        "save_module_prompt": "💾 Сохранить модуль в файловую систему?",
        "save_yes": "✅ Да, сохранить",
        "save_no": "❌ Нет, не сохранять",
        "save_always": "💾 Всегда сохранять",
        "save_never": "🚫 Никогда не сохранять",
        "ffmpeg_required": "🎬 Требуется ffmpeg\nУстановите: apt install ffmpeg",
        "inline_not_initialized": "🔘 Inline не инициализирован\nВозможно, бот не запущен",
        "hikka_version_required": "⚠️ Требуется Hikka v{} или новее",
        "update_button": "🔄 Обновить",
        "cancel_button": "❌ Отмена",
        "install_deps": "📦 Устанавливаю зависимости:\n{}",
        "termux_error": "⚠️ Ошибка установки в Termux\nПопробуйте установить вручную",
        "deps_error": "⚠️ Ошибка установки зависимостей",
        "load_error": "😖 {}",
        "module_load_error": "❌ Ошибка загрузки модуля",
        "requires_approval": "⏳ Модуль {} требует подтверждения\nКанал: {}\nПричина: {}",
        "self_unload": "👋 Модуль выгрузил сам себя\nПричина: {}",
        "self_suspend": "🥶 Модуль приостановлен\nПричина: {}",
        "init_error": "❌ Ошибка при инициализации модуля",
        "module_loaded_template": "🍇 Модуль <code>{}</code> загружен {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "no_description": "Нет описания",
        "too_many_commands_template": "🍇 Модуль <code>{}</code> загружен {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "subscribed": "✅ Подписался!",
        "not_subscribed": "❌ Не подписался",
        "specify_module": "⚠️ Укажи имя модуля",
        "cannot_unload_library": "📚 Нельзя выгрузить библиотеку",
        "cannot_unload_core": "❌ Нельзя выгрузить core-модуль\n{}",
        "unloaded_modules": "✅ Выгружены модули: {}",
        "nothing_unloaded": "❌ Ничего не выгружено",
        "clear_modules_confirm": "⚠️ Вы уверены, что хотите удалить ВСЕ модули?\n\nПосле удаления потребуется перезагрузка юзербота",
        "delete_all": "✅ Да, удалить всё",
        "cancel": "❌ Нет, отмена",
        "all_modules_deleted": "🗑️ Все модули удалены\n🔄 Перезагрузка...",
        "specify_module_mlcmd": "⚠️ Укажи имя модуля",
        "module_not_found_mlcmd": "❌ Модуль не найден",
        "module_info": "📦 Модуль: <code>{}</code>\n📝 Описание: {}\n🔧 Команд: {}\n",
        "exact_not_found": "\n⚠️ Точное совпадение не найдено",
        "module_get_error": "❌ Ошибка получения модуля",
        "specify_repo_url": "⚠️ Укажи ссылку на репозиторий\nПример: .addrepo https://example.com/repo",
        "invalid_repo": "❌ Невалидный репозиторий\n(нет full.txt или пустой список)",
        "repo_already_added": "📁 Репозиторий уже добавлен\n{}",
        "repo_added": "✅ Репозиторий добавлен\n{}",
        "specify_repo_del": "⚠️ Укажи ссылку на репозиторий",
        "repo_not_found": "❌ Репозиторий не найден",
        "repo_deleted": "🗑️ Репозиторий удалён\n{}",
        "save_all_modules": "💾 Буду сохранять все модули",
        "joined_channel": "🍇 Joined <a href=\"https://t.me/{}\">{}</a>",
        "file_source": "файл",
        "direct_link": "прямая ссылка: {}",
        "repository": "репозиторий: {}",
        "restart_required": "🔄 Требуется перезагрузка после установки {}",
        "installing": "📥 Устанавливаю <code>{}</code>...",
        "developer_label": "\n🫶 Разработчик: {}",
        "description_prefix": "ℹ️ {}",
        "info_prefix": "🍇 Модуль <code>{}</code> загружен {}{}",
        "blockquote_start": "<blockquote>",
        "blockquote_end": "</blockquote>",
        "too_many_commands": "⚠️ Слишком много команд для отображения\n",
    }

    strings_ua = {
        "trusted_source": "✅ Довірене джерело",
        "untrusted_install_message": "\n\n🍇 <b>Важливо знати</b>\n\nВи встановили модуль з неперевіреного джерела 🌸\n\nМи не несемо відповідальності за:\n▫️ Стан пристрою\n▫️ Збереження акаунта\n▫️ Втрату даних",
        "overwrite_warning": "<blockquote>😖 <b>Цей модуль спробував перезаписати вбудовану команду</b> <code>{}{}</code>\n\n🍇 <i>Це не помилка, а захід безпеки, необхідний для запобігання заміни команд вбудованих модулів усіляким мотлохом. Не повідомляйте про це в support чаті</i></blockquote>",
        "confirm_overwrite": "✅ Підтвердити перезапис",
        "close_btn": "❌ Скасувати",
        "overwrite_success": "✅ Перезапис виконано успішно!",
        "overwrite_error": "❌ Помилка при перезаписі: {}",
        "usage_re": "⚠️ Використання:\n.re raw <посилання>\n.re file",
        "need_raw_url": "⚠️ Вкажи raw-посилання на модуль",
        "invalid_mode": "⚠️ Невірний режим. Використовуй raw або file",
        "overwrite_in_progress": "🔄 Виконується перезапис...",
        "download_error": "❌ Помилка завантаження: {}",
        "no_file_or_reply": "⚠️ Немає файлу або реплая на файл",
        "file_read_error": "❌ Помилка читання файлу: {}",
        "cannot_get_code": "❌ Не вдалося отримати код модуля",
        "searching_modules": "🔍 Шукаю модуль в репозиторіях...",
        "available_modules": "📦 Доступні модулі\n\n☁️ {}\n\n{}",
        "module_not_found": "❌ Модуль не знайдено в репозиторіях",
        "downloading_module": "📥 Встановлюю <code>{}</code>...",
        "download_failed": "❌ Не вдалося завантажити модуль",
        "loading_from_file": "📥 Завантажую модуль з файлу...",
        "invalid_encoding": "❌ Невірне кодування файлу",
        "save_module_prompt": "💾 Зберегти модуль у файлову систему?",
        "save_yes": "✅ Так, зберегти",
        "save_no": "❌ Ні, не зберігати",
        "save_always": "💾 Завжди зберігати",
        "save_never": "🚫 Ніколи не зберігати",
        "ffmpeg_required": "🎬 Потрібен ffmpeg\nВстановіть: apt install ffmpeg",
        "inline_not_initialized": "🔘 Inline не ініціалізовано\nМожливо, бот не запущено",
        "hikka_version_required": "⚠️ Потрібна Hikka v{} або новіша",
        "update_button": "🔄 Оновити",
        "cancel_button": "❌ Скасувати",
        "install_deps": "📦 Встановлюю залежності:\n{}",
        "termux_error": "⚠️ Помилка встановлення в Termux\nСпробуйте встановити вручну",
        "deps_error": "⚠️ Помилка встановлення залежностей",
        "load_error": "😖 {}",
        "module_load_error": "❌ Помилка завантаження модуля",
        "requires_approval": "⏳ Модуль {} вимагає підтвердження\nКанал: {}\nПричина: {}",
        "self_unload": "👋 Модуль вивантажив сам себе\nПричина: {}",
        "self_suspend": "🥶 Модуль призупинено\nПричина: {}",
        "init_error": "❌ Помилка при ініціалізації модуля",
        "module_loaded_template": "🍇 Модуль <code>{}</code> завантажено {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "no_description": "Немає опису",
        "too_many_commands_template": "🍇 Модуль <code>{}</code> завантажено {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "subscribed": "✅ Підписався!",
        "not_subscribed": "❌ Не підписався",
        "specify_module": "⚠️ Вкажи ім'я модуля",
        "cannot_unload_library": "📚 Не можна вивантажити бібліотеку",
        "cannot_unload_core": "❌ Не можна вивантажити core-модуль\n{}",
        "unloaded_modules": "✅ Вивантажено модулі: {}",
        "nothing_unloaded": "❌ Нічого не вивантажено",
        "clear_modules_confirm": "⚠️ Ви впевнені, що хочете видалити ВСІ модулі?\n\nПісля видалення потрібне перезавантаження юзербота",
        "delete_all": "✅ Так, видалити все",
        "cancel": "❌ Ні, скасувати",
        "all_modules_deleted": "🗑️ Всі модулі видалено\n🔄 Перезавантаження...",
        "specify_module_mlcmd": "⚠️ Вкажи ім'я модуля",
        "module_not_found_mlcmd": "❌ Модуль не знайдено",
        "module_info": "📦 Модуль: <code>{}</code>\n📝 Опис: {}\n🔧 Команд: {}\n",
        "exact_not_found": "\n⚠️ Точного збігу не знайдено",
        "module_get_error": "❌ Помилка отримання модуля",
        "specify_repo_url": "⚠️ Вкажи посилання на репозиторій\nПриклад: .addrepo https://example.com/repo",
        "invalid_repo": "❌ Невірний репозиторій\n(немає full.txt або порожній список)",
        "repo_already_added": "📁 Репозиторій вже додано\n{}",
        "repo_added": "✅ Репозиторій додано\n{}",
        "specify_repo_del": "⚠️ Вкажи посилання на репозиторій",
        "repo_not_found": "❌ Репозиторій не знайдено",
        "repo_deleted": "🗑️ Репозиторій видалено\n{}",
        "save_all_modules": "💾 Буду зберігати всі модулі",
        "joined_channel": "🍇 Joined <a href=\"https://t.me/{}\">{}</a>",
        "file_source": "файл",
        "direct_link": "пряме посилання: {}",
        "repository": "репозиторій: {}",
        "restart_required": "🔄 Потрібне перезавантаження після встановлення {}",
        "installing": "📥 Встановлюю <code>{}</code>...",
        "developer_label": "\n🫶 Розробник: {}",
        "description_prefix": "ℹ️ {}",
        "info_prefix": "🍇 Модуль <code>{}</code> завантажено {}{}",
        "blockquote_start": "<blockquote>",
        "blockquote_end": "</blockquote>",
        "too_many_commands": "⚠️ Занадто багато команд для відображення\n",
    }

    strings_en = {
        "trusted_source": "✅ Trusted source",
        "untrusted_install_message": "\n\n🍇 <b>Important to know</b>\n\nYou have installed a module from an untrusted source 🌸\n\nWe are not responsible for:\n▫️ Your device\n▫️ Your account\n▫️ Data loss",
        "overwrite_warning": "<blockquote>😖 <b>This module attempted to overwrite built-in command</b> <code>{}{}</code>\n\n🍇 <i>This is not an error, but a security measure required to prevent replacing built-in module commands with junk. Do not report this in the support chat</i></blockquote>",
        "confirm_overwrite": "✅ Confirm overwrite",
        "close_btn": "❌ Cancel",
        "overwrite_success": "✅ Overwrite successful!",
        "overwrite_error": "❌ Overwrite error: {}",
        "usage_re": "⚠️ Usage:\n.re raw <link>\n.re file",
        "need_raw_url": "⚠️ Provide raw link to module",
        "invalid_mode": "⚠️ Invalid mode. Use raw or file",
        "overwrite_in_progress": "🔄 Overwriting...",
        "download_error": "❌ Download error: {}",
        "no_file_or_reply": "⚠️ No file or reply to file",
        "file_read_error": "❌ File read error: {}",
        "cannot_get_code": "❌ Failed to get module code",
        "searching_modules": "🔍 Searching for module in repositories...",
        "available_modules": "📦 Available modules\n\n☁️ {}\n\n{}",
        "module_not_found": "❌ Module not found in repositories",
        "downloading_module": "📥 Installing <code>{}</code>...",
        "download_failed": "❌ Failed to download module",
        "loading_from_file": "📥 Loading module from file...",
        "invalid_encoding": "❌ Invalid file encoding",
        "save_module_prompt": "💾 Save module to filesystem?",
        "save_yes": "✅ Yes, save",
        "save_no": "❌ No, don't save",
        "save_always": "💾 Always save",
        "save_never": "🚫 Never save",
        "ffmpeg_required": "🎬 ffmpeg required\nInstall: apt install ffmpeg",
        "inline_not_initialized": "🔘 Inline not initialized\nPossibly bot is not running",
        "hikka_version_required": "⚠️ Hikka v{} or newer required",
        "update_button": "🔄 Update",
        "cancel_button": "❌ Cancel",
        "install_deps": "📦 Installing dependencies:\n{}",
        "termux_error": "⚠️ Installation error in Termux\nTry installing manually",
        "deps_error": "⚠️ Dependency installation error",
        "load_error": "😖 {}",
        "module_load_error": "❌ Module load error",
        "requires_approval": "⏳ Module {} requires approval\nChannel: {}\nReason: {}",
        "self_unload": "👋 Module unloaded itself\nReason: {}",
        "self_suspend": "🥶 Module suspended\nReason: {}",
        "init_error": "❌ Module initialization error",
        "module_loaded_template": "🍇 Module <code>{}</code> loaded {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "no_description": "No description",
        "too_many_commands_template": "🍇 Module <code>{}</code> loaded {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "subscribed": "✅ Subscribed!",
        "not_subscribed": "❌ Not subscribed",
        "specify_module": "⚠️ Specify module name",
        "cannot_unload_library": "📚 Cannot unload library",
        "cannot_unload_core": "❌ Cannot unload core module\n{}",
        "unloaded_modules": "✅ Unloaded modules: {}",
        "nothing_unloaded": "❌ Nothing unloaded",
        "clear_modules_confirm": "⚠️ Are you sure you want to delete ALL modules?\n\nReboot required after deletion",
        "delete_all": "✅ Yes, delete all",
        "cancel": "❌ No, cancel",
        "all_modules_deleted": "🗑️ All modules deleted\n🔄 Rebooting...",
        "specify_module_mlcmd": "⚠️ Specify module name",
        "module_not_found_mlcmd": "❌ Module not found",
        "module_info": "📦 Module: <code>{}</code>\n📝 Description: {}\n🔧 Commands: {}\n",
        "exact_not_found": "\n⚠️ Exact match not found",
        "module_get_error": "❌ Error getting module",
        "specify_repo_url": "⚠️ Specify repository URL\nExample: .addrepo https://example.com/repo",
        "invalid_repo": "❌ Invalid repository\n(no full.txt or empty list)",
        "repo_already_added": "📁 Repository already added\n{}",
        "repo_added": "✅ Repository added\n{}",
        "specify_repo_del": "⚠️ Specify repository URL",
        "repo_not_found": "❌ Repository not found",
        "repo_deleted": "🗑️ Repository deleted\n{}",
        "save_all_modules": "💾 Will save all modules",
        "joined_channel": "🍇 Joined <a href=\"https://t.me/{}\">{}</a>",
        "file_source": "file",
        "direct_link": "direct link: {}",
        "repository": "repository: {}",
        "restart_required": "🔄 Restart required after installing {}",
        "installing": "📥 Installing <code>{}</code>...",
        "developer_label": "\n🫶 Developer: {}",
        "description_prefix": "ℹ️ {}",
        "info_prefix": "🍇 Module <code>{}</code> loaded {}{}",
        "blockquote_start": "<blockquote>",
        "blockquote_end": "</blockquote>",
        "too_many_commands": "⚠️ Too many commands to display\n",
    }

    strings_de = {
        "trusted_source": "✅ Vertrauenswürdige Quelle",
        "untrusted_install_message": "\n\n🍇 <b>Wichtig zu wissen</b>\n\nSie haben ein Modul aus einer nicht vertrauenswürdigen Quelle installiert 🌸\n\nWir übernehmen keine Verantwortung für:\n▫️ Ihr Gerät\n▫️ Ihren Account\n▫️ Datenverlust",
        "overwrite_warning": "<blockquote>😖 <b>Dieses Modul versuchte, den eingebauten Befehl zu überschreiben</b> <code>{}{}</code>\n\n🍇 <i>Dies ist kein Fehler, sondern eine Sicherheitsmaßnahme, um zu verhindern, dass eingebaute Modulbefehle durch Müll ersetzt werden. Melden Sie dies nicht im Support-Chat</i></blockquote>",
        "confirm_overwrite": "✅ Überschreiben bestätigen",
        "close_btn": "❌ Abbrechen",
        "overwrite_success": "✅ Überschreiben erfolgreich!",
        "overwrite_error": "❌ Fehler beim Überschreiben: {}",
        "usage_re": "⚠️ Verwendung:\n.re raw <Link>\n.re file",
        "need_raw_url": "⚠️ Raw-Link zum Modul angeben",
        "invalid_mode": "⚠️ Ungültiger Modus. Verwenden Sie raw oder file",
        "overwrite_in_progress": "🔄 Überschreiben...",
        "download_error": "❌ Download-Fehler: {}",
        "no_file_or_reply": "⚠️ Keine Datei oder Antwort auf Datei",
        "file_read_error": "❌ Datei-Lesefehler: {}",
        "cannot_get_code": "❌ Modulcode konnte nicht abgerufen werden",
        "searching_modules": "🔍 Suche Modul in Repositories...",
        "available_modules": "📦 Verfügbare Module\n\n☁️ {}\n\n{}",
        "module_not_found": "❌ Modul nicht in Repositories gefunden",
        "downloading_module": "📥 Installiere <code>{}</code>...",
        "download_failed": "❌ Modul konnte nicht heruntergeladen werden",
        "loading_from_file": "📥 Lade Modul aus Datei...",
        "invalid_encoding": "❌ Ungültige Dateikodierung",
        "save_module_prompt": "💾 Modul im Dateisystem speichern?",
        "save_yes": "✅ Ja, speichern",
        "save_no": "❌ Nein, nicht speichern",
        "save_always": "💾 Immer speichern",
        "save_never": "🚫 Nie speichern",
        "ffmpeg_required": "🎬 ffmpeg erforderlich\nInstallieren: apt install ffmpeg",
        "inline_not_initialized": "🔘 Inline nicht initialisiert\nBot läuft möglicherweise nicht",
        "hikka_version_required": "⚠️ Hikka v{} oder neuer erforderlich",
        "update_button": "🔄 Aktualisieren",
        "cancel_button": "❌ Abbrechen",
        "install_deps": "📦 Installiere Abhängigkeiten:\n{}",
        "termux_error": "⚠️ Installationsfehler in Termux\nVersuchen Sie manuelle Installation",
        "deps_error": "⚠️ Fehler bei der Abhängigkeitsinstallation",
        "load_error": "😖 {}",
        "module_load_error": "❌ Modul-Ladefehler",
        "requires_approval": "⏳ Modul {} erfordert Bestätigung\nKanal: {}\nGrund: {}",
        "self_unload": "👋 Modul entlud sich selbst\nGrund: {}",
        "self_suspend": "🥶 Modul ausgesetzt\nGrund: {}",
        "init_error": "❌ Modul-Initialisierungsfehler",
        "module_loaded_template": "🍇 Modul <code>{}</code> geladen {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "no_description": "Keine Beschreibung",
        "too_many_commands_template": "🍇 Modul <code>{}</code> geladen {}{}\n\n<blockquote>{}{}</blockquote>{}{}",
        "subscribed": "✅ Abonniert!",
        "not_subscribed": "❌ Nicht abonniert",
        "specify_module": "⚠️ Modulnamen angeben",
        "cannot_unload_library": "📚 Bibliothek kann nicht entladen werden",
        "cannot_unload_core": "❌ Kernmodul kann nicht entladen werden\n{}",
        "unloaded_modules": "✅ Entladene Module: {}",
        "nothing_unloaded": "❌ Nichts entladen",
        "clear_modules_confirm": "⚠️ Sind Sie sicher, dass Sie ALLE Module löschen möchten?\n\nNeustart nach dem Löschen erforderlich",
        "delete_all": "✅ Ja, alle löschen",
        "cancel": "❌ Nein, abbrechen",
        "all_modules_deleted": "🗑️ Alle Module gelöscht\n🔄 Neustart...",
        "specify_module_mlcmd": "⚠️ Modulnamen angeben",
        "module_not_found_mlcmd": "❌ Modul nicht gefunden",
        "module_info": "📦 Modul: <code>{}</code>\n📝 Beschreibung: {}\n🔧 Befehle: {}\n",
        "exact_not_found": "\n⚠️ Genaue Übereinstimmung nicht gefunden",
        "module_get_error": "❌ Fehler beim Abrufen des Moduls",
        "specify_repo_url": "⚠️ Repository-URL angeben\nBeispiel: .addrepo https://example.com/repo",
        "invalid_repo": "❌ Ungültiges Repository\n(keine full.txt oder leere Liste)",
        "repo_already_added": "📁 Repository bereits hinzugefügt\n{}",
        "repo_added": "✅ Repository hinzugefügt\n{}",
        "specify_repo_del": "⚠️ Repository-URL angeben",
        "repo_not_found": "❌ Repository nicht gefunden",
        "repo_deleted": "🗑️ Repository gelöscht\n{}",
        "save_all_modules": "💾 Werde alle Module speichern",
        "joined_channel": "🍇 Joined <a href=\"https://t.me/{}\">{}</a>",
        "file_source": "Datei",
        "direct_link": "direkter Link: {}",
        "repository": "Repository: {}",
        "restart_required": "🔄 Neustart nach Installation von {} erforderlich",
        "installing": "📥 Installiere <code>{}</code>...",
        "developer_label": "\n🫶 Entwickler: {}",
        "description_prefix": "ℹ️ {}",
        "info_prefix": "🍇 Modul <code>{}</code> geladen {}{}",
        "blockquote_start": "<blockquote>",
        "blockquote_end": "</blockquote>",
        "too_many_commands": "⚠️ Zu viele Befehle zum Anzeigen\n",
    }

    def __init__(self):
        self.fully_loaded = False
        self._links_cache = {}
        self._storage: RemoteStorage = None
        self._pending_overwrite = {}

        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "MODULES_REPO",
                DEFAULT_REPO,
                lambda: "Main repository with modules",
                validator=loader.validators.Link(),
            ),
            loader.ConfigValue(
                "ADDITIONAL_REPOS",
                [SECONDARY_REPO],
                lambda: "Additional repositories",
                validator=loader.validators.Series(validator=loader.validators.Link()),
            ),
            loader.ConfigValue(
                "share_link",
                doc=lambda: "Share module links",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "basic_auth",
                None,
                lambda: "Basic auth for repositories",
                validator=loader.validators.Hidden(
                    loader.validators.RegExp(r"^.*:.*$")
                ),
            ),
            loader.ConfigValue(
                "only_trusted",
                False,
                lambda: "Only allow modules from trusted sources (security risk if disabled)",
                validator=loader.validators.Boolean(),
            ),
        )

    async def _async_init(self):
        modules = list(
            filter(
                lambda x: not x.startswith(DEFAULT_REPO),
                utils.array_sum(
                    map(
                        lambda x: list(x.values()),
                        (await self.get_repo_list()).values(),
                    )
                ),
            )
        )
        # logger.debug(self.strings("loading_modules"), modules)
        asyncio.ensure_future(self._storage.preload(modules))

    async def client_ready(self):
        while not (settings := self.lookup("settings")):
            await asyncio.sleep(0.5)

        self._storage = RemoteStorage(self._client)

        self.allmodules.add_aliases(settings.get("aliases", {}))

        main.hikka.ready.set()

        asyncio.ensure_future(self._update_modules())
        asyncio.ensure_future(self._async_init())

    @loader.loop(interval=3, wait_before=True, autostart=True)
    async def _config_autosaver(self):
        for mod in self.allmodules.modules:
            if (
                not hasattr(mod, "config")
                or not mod.config
                or not isinstance(mod.config, loader.ModuleConfig)
            ):
                continue

            for option, config in mod.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(mod.config._config[option], "_save_marker")
                mod.pointer("__config__", {})[option] = config.value

        for lib in self.allmodules.libraries:
            if (
                not hasattr(lib, "config")
                or not lib.config
                or not isinstance(lib.config, loader.ModuleConfig)
            ):
                continue

            for option, config in lib.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(lib.config._config[option], "_save_marker")
                lib._lib_pointer("__config__", {})[option] = config.value

        self._db.save()

    def update_modules_in_db(self):
        if self.allmodules.secure_boot:
            return

        self.set(
            "loaded_modules",
            {
                **{
                    module.__class__.__name__: module.__origin__
                    for module in self.allmodules.modules
                    if module.__origin__.startswith("http")
                },
            },
        )

    def _get_img(self, code: str) -> typing.Optional[str]:
        match = re.search(r'#\s*img\s*"(.+?)"', code)
        return match.group(1).strip() if match else None

    def _is_trusted(self, developer: typing.Optional[str]) -> bool:
        if not developer:
            return False
        dev_clean = developer.strip().lstrip('@').lower()
        for trusted in TRUSTED_DEVS:
            if dev_clean == trusted.lower().lstrip('@'):
                return True
        return False

    async def _send_overwrite_warning(self, message: Message, target_command: str, is_trusted: bool = True):
        error_text = self.strings("overwrite_warning").format(
            utils.escape_html(self.get_prefix()),
            utils.escape_html(target_command)
        )
        
        reply_markup = None
        if is_trusted:
            reply_markup = [
                [
                    {"text": self.strings("confirm_overwrite"), "callback": self._inline_confirm_overwrite},
                    {"text": self.strings("close_btn"), "action": "close"},
                ]
            ]
        
        try:
            r = requests.get(OVERWRITE_IMAGE, timeout=10)
            if r.status_code == 200:
                img_path = tempfile.mktemp(suffix=".jpg")
                with open(img_path, "wb") as f:
                    f.write(r.content)
                await self._client.send_file(
                    utils.get_chat_id(message),
                    img_path,
                    caption=error_text,
                    reply_to=getattr(message, "reply_to_msg_id", None),
                    reply_markup=reply_markup,
                )
                os.remove(img_path)
                return True
        except Exception:
            pass
        
        await self.inline.form(
            error_text,
            message=message,
            reply_markup=reply_markup,
        )
        return True

    async def _inline_confirm_overwrite(self, call: InlineCall):
        await call.answer("✅ Подтверждено")
        
        if not hasattr(call, '_pending_overwrite_data'):
            await call.edit(self.strings("close_btn"))
            return
        
        data = call._pending_overwrite_data
        
        if data.get("target_command") == "Loader":
            await call.edit("❌ Модуль Loader не может быть перезаписан.")
            return
        
        await call.edit(self.strings("overwrite_in_progress"))
        
        target_command = data.get("target_command")
        with contextlib.suppress(Exception):
            await self.allmodules.unload_module(target_command)
        
        try:
            spec = ModuleSpec(
                f"hikka.modules.overwrite_{uuid.uuid4()}",
                loader.StringLoader(data["doc"], "<overwrite>"),
                origin=data["origin"],
            )
            instance = await self.allmodules.register_module(
                spec,
                f"hikka.modules.overwrite_{uuid.uuid4()}",
                data["origin"],
                save_fs=data["save_fs"],
            )
            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(instance, no_self_unload=True, from_dlmod=True)
            await call.edit(self.strings("overwrite_success"))
        except Exception as err:
            await call.edit(self.strings("overwrite_error").format(utils.escape_html(str(err))))

    async def _handle_core_overwrite(self, message: Message, e: CoreOverwriteError, doc: str, origin: str, save_fs: bool, is_trusted: bool = True):
        message._pending_overwrite_data = {
            "doc": doc,
            "origin": origin,
            "save_fs": save_fs,
            "target_command": e.target,
        }
        await self._send_overwrite_warning(message, e.target, is_trusted=is_trusted)

    @loader.command(alias="re")
    async def rename(self, message: Message):
        cmd_text = utils.get_args_raw(message)
        await message.delete()
        
        args = cmd_text.split()
        
        if len(args) < 1:
            await utils.answer(message, self.strings("usage_re"))
            return
        
        mode = args[0].lower()
        
        if mode == "raw":
            if len(args) < 2:
                await utils.answer(message, self.strings("need_raw_url"))
                return
            url = " ".join(args[1:])
            await self._perform_overwrite(message, url=url)
        elif mode == "file":
            await self._perform_overwrite(message, file_mode=True)
        else:
            await utils.answer(message, self.strings("invalid_mode"))

    async def _perform_overwrite(self, message: Message, url: str = None, file_mode: bool = False):
        await utils.answer(message, self.strings("overwrite_in_progress"))
        
        doc = None
        origin = None
        
        if url:
            try:
                r = requests.get(url, timeout=30)
                if r.status_code != 200:
                    await utils.answer(message, self.strings("download_error").format(r.status_code))
                    return
                doc = r.text
                origin = url
            except Exception as e:
                await utils.answer(message, self.strings("download_error").format(utils.escape_html(str(e))))
                return
        elif file_mode:
            msg = message if message.file else (await message.get_reply_message())
            if msg is None or msg.media is None:
                await utils.answer(message, self.strings("no_file_or_reply"))
                return
            
            try:
                doc_bytes = await msg.download_media(bytes)
                doc = doc_bytes.decode()
                origin = "<file>"
            except Exception as e:
                await utils.answer(message, self.strings("file_read_error").format(utils.escape_html(str(e))))
                return
        
        if not doc:
            await utils.answer(message, self.strings("cannot_get_code"))
            return
        
        try:
            node = ast.parse(doc)
            class_name = next(
                n.name
                for n in node.body
                if isinstance(n, ast.ClassDef)
                and any(
                    isinstance(base, ast.Attribute) and base.value.id == "Module"
                    or isinstance(base, ast.Name) and base.id == "Module"
                    for base in n.bases
                )
            )
        except Exception:
            class_name = None
        
        if class_name:
            with contextlib.suppress(Exception):
                await self.allmodules.unload_module(class_name)
        
        try:
            module_name = f"hikka.modules.overwrite_{uuid.uuid4()}"
            spec = ModuleSpec(
                module_name,
                loader.StringLoader(doc, f"<overwrite {origin}>"),
                origin=origin,
            )
            instance = await self.allmodules.register_module(
                spec,
                module_name,
                origin,
                save_fs=True,
            )
            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(instance, no_self_unload=True, from_dlmod=True)
            await utils.answer(message, self.strings("overwrite_success"))
        except Exception as err:
            await utils.answer(message, self.strings("overwrite_error").format(utils.escape_html(str(err))))

    @loader.command(alias="dlm")
    async def dlmod(self, message: Message, force_pm: bool = False):
        if args := utils.get_args(message):
            args = args[0]

            await utils.answer(
                message, self.strings("searching_modules")
            )

            if (
                await self.download_and_install(args, message, force_pm)
                == MODULE_LOADING_FORBIDDEN
            ):
                return

            if self.fully_loaded:
                self.update_modules_in_db()
        else:
            modules_list = []
            for repo, mods in (await self.get_repo_list()).items():
                mod_names = sorted(
                    [utils.escape_html(i.split("/")[-1].split(".")[0]) for i in mods.values()]
                )
                chunks = "\n".join([" | ".join(chunk) for chunk in utils.chunks(mod_names, 5)])
                modules_list.append(self.strings("available_modules").format(repo.strip('/'), chunks))
            
            await self.inline.list(message, modules_list)

    async def _get_modules_to_load(self):
        todo = self.get("loaded_modules", {})
        logger.debug(self.strings("loading_modules"), todo)
        return todo

    async def _get_repo(self, repo: str) -> str:
        repo = repo.strip("/")

        if self._links_cache.get(repo, {}).get("exp", 0) >= time.time():
            return self._links_cache[repo]["data"]

        res = await utils.run_sync(
            requests.get,
            f"{repo}/full.txt",
            auth=(
                tuple(self.config["basic_auth"].split(":", 1))
                if self.config["basic_auth"]
                else None
            ),
        )

        if not str(res.status_code).startswith("2"):
            logger.debug(
                "Can't load repo %s contents because of %s status code",
                repo,
                res.status_code,
            )
            return []

        self._links_cache[repo] = {
            "exp": time.time() + 5 * 60,
            "data": [link for link in res.text.strip().splitlines() if link],
        }

        return self._links_cache[repo]["data"]

    async def get_repo_list(
        self,
        only_primary: bool = False,
    ) -> dict:
        repos = [self.config["MODULES_REPO"]]
        if not only_primary:
            repos += self.config["ADDITIONAL_REPOS"]
        
        result = {}
        for repo_id, repo in enumerate(repos):
            if not repo.startswith("http"):
                continue
            modules = {}
            for i, link in enumerate(set(await self._get_repo(repo))):
                modules[f"Mod/{repo_id}/{i}"] = f'{repo.strip("/")}/{link}.py'
            result[repo] = modules
        return result

    async def get_links_list(self) -> typing.List[str]:
        links = await self.get_repo_list()
        main_repo = list(links.pop(self.config["MODULES_REPO"]).values())
        return main_repo + list(dict(ChainMap(*list(links.values()))).values())

    async def _find_link(self, module_name: str) -> typing.Union[str, bool]:
        return next(
            filter(
                lambda link: link.lower().endswith(f"/{module_name.lower()}.py"),
                await self.get_links_list(),
            ),
            False,
        )

    async def download_and_install(
        self,
        module_name: str,
        message: typing.Optional[Message] = None,
        force_pm: bool = False,
    ) -> int:
        try:
            blob_link = False
            module_name = module_name.strip()
            source = None
            if urlparse(module_name).netloc:
                url = module_name
                source = self.strings("direct_link").format(url)
                if re.match(
                    r"^(https:\/\/github\.com\/.*?\/.*?\/blob\/.*\.py)|"
                    r"(https:\/\/gitlab\.com\/.*?\/.*?\/-\/blob\/.*\.py)$",
                    url,
                ):
                    url = url.replace("/blob/", "/raw/")
                    blob_link = True
            else:
                url = await self._find_link(module_name)
                source = self.strings("repository").format(self.config['MODULES_REPO'])

                if not url:
                    if message is not None:
                        await utils.answer(message, self.strings("module_not_found"))

                    return MODULE_LOADING_FAILED

            if message:
                message = await utils.answer(
                    message,
                    self.strings("downloading_module").format(module_name),
                )

            try:
                r = await self._storage.fetch(url, auth=self.config["basic_auth"])
            except requests.exceptions.HTTPError:
                if message is not None:
                    await utils.answer(message, self.strings("download_failed"))

                return MODULE_LOADING_FAILED

            await self.load_module(
                r,
                message,
                module_name,
                url,
                blob_link=blob_link,
                source=source,
            )
            return MODULE_LOADING_SUCCESS
        except Exception:
            logger.exception("Failed to load %s", module_name)
            return MODULE_LOADING_FAILED

    async def _inline__load(
        self,
        call: InlineCall,
        doc: str,
        path_: str,
        mode: str,
    ):
        save = False
        if mode == "all_yes":
            self._db.set(main.__name__, "permanent_modules_fs", True)
            self._db.set(main.__name__, "disable_modules_fs", False)
            await call.answer(self.strings("save_all_modules"))
            save = True
        elif mode == "all_no":
            self._db.set(main.__name__, "disable_modules_fs", True)
            self._db.set(main.__name__, "permanent_modules_fs", False)
        elif mode == "once":
            save = True

        await self.load_module(doc, call, origin=path_ or "<string>", save_fs=save, source=self.strings("file_source"))

    @loader.command(alias="lm")
    async def loadmod(self, message: Message, force_pm: bool = False):
        args = utils.get_args_raw(message)
        if "-fs" in args:
            force_save = True
            args = args.replace("-fs", "").strip()
        else:
            force_save = False

        msg = message if message.file else (await message.get_reply_message())

        if msg is None or msg.media is None:
            await utils.answer(message, self.strings("no_file_or_reply"))
            return

        await utils.answer(
            message, self.strings("loading_from_file")
        )

        path_ = None
        doc = await msg.download_media(bytes)

        try:
            doc = doc.decode()
        except UnicodeDecodeError:
            await utils.answer(message, self.strings("invalid_encoding"))
            return

        if (
            not self._db.get(
                main.__name__,
                "disable_modules_fs",
                False,
            )
            and not self._db.get(main.__name__, "permanent_modules_fs", False)
            and not force_save
        ):
            if message.file:
                await message.edit("")
                message = await message.respond("🍇", reply_to=utils.get_topic(message))

            if await self.inline.form(
                self.strings("save_module_prompt"),
                message=message,
                reply_markup=[
                    [
                        {
                            "text": self.strings("save_yes"),
                            "callback": self._inline__load,
                            "args": (doc, path_, "once"),
                        },
                        {
                            "text": self.strings("save_no"),
                            "callback": self._inline__load,
                            "args": (doc, path_, "no"),
                        },
                    ],
                    [
                        {
                            "text": self.strings("save_always"),
                            "callback": self._inline__load,
                            "args": (doc, path_, "all_yes"),
                        }
                    ],
                    [
                        {
                            "text": self.strings("save_never"),
                            "callback": self._inline__load,
                            "args": (doc, path_, "all_no"),
                        }
                    ],
                ],
            ):
                return

        if path_ is not None:
            await self.load_module(
                doc,
                message,
                origin=path_,
                save_fs=(
                    force_save
                    or self._db.get(main.__name__, "permanent_modules_fs", False)
                    and not self._db.get(main.__name__, "disable_modules_fs", False)
                ),
                source=self.strings("file_source"),
            )
        else:
            await self.load_module(
                doc,
                message,
                save_fs=(
                    force_save
                    or self._db.get(main.__name__, "permanent_modules_fs", False)
                    and not self._db.get(main.__name__, "disable_modules_fs", False)
                ),
                source=self.strings("file_source"),
            )

    async def approve_internal(
        self,
        call: InlineCall,
        channel: "hints.EntityLike",
        event: asyncio.Event,
    ):
        await self._client(JoinChannelRequest(channel))
        event.status = True
        event.set()

        await call.edit(
            self.strings("joined_channel").format(
                channel.username,
                utils.escape_html(channel.title)
            ),
        )

    async def load_module(
        self,
        doc: str,
        message: Message,
        name: typing.Optional[str] = None,
        origin: str = "<string>",
        did_requirements: bool = False,
        save_fs: bool = False,
        blob_link: bool = False,
        source: str = None,
    ):
        developer = re.search(r"# ?meta developer: ?(.+)", doc)
        developer = developer.group(1) if developer else None

        meta_name = re.search(r"# ?meta name: ?(.+)", doc)
        meta_name = meta_name.group(1).strip() if meta_name else None

        is_trusted = self._is_trusted(developer)

        meta_img = self._get_img(doc)

        if any(
            line.replace(" ", "") == "#scope:ffmpeg" for line in doc.splitlines()
        ) and os.system("ffmpeg -version 1>/dev/null 2>/dev/null"):
            if isinstance(message, Message):
                await utils.answer(message, self.strings("ffmpeg_required"))
            return

        if (
            any(line.replace(" ", "") == "#scope:inline" for line in doc.splitlines())
            and not self.inline.init_complete
        ):
            if isinstance(message, Message):
                await utils.answer(message, self.strings("inline_not_initialized"))
            return

        if re.search(r"# ?scope: ?hikka_min", doc):
            ver = re.search(r"# ?scope: ?hikka_min ((?:\d+\.){2}\d+)", doc).group(1)
            ver_ = tuple(map(int, ver.split(".")))
            if main.__version__ < ver_:
                if isinstance(message, Message):
                    if getattr(message, "file", None):
                        m = utils.get_chat_id(message)
                        await message.edit("")
                    else:
                        m = message

                    await self.inline.form(
                        self.strings("hikka_version_required").format(ver),
                        m,
                        reply_markup=[
                            {
                                "text": self.strings("update_button"),
                                "callback": self.lookup("updater").inline_update,
                            },
                            {
                                "text": self.strings("cancel_button"),
                                "action": "close",
                            },
                        ],
                    )
                return

        if name is None:
            try:
                node = ast.parse(doc)
                uid = next(
                    n.name
                    for n in node.body
                    if isinstance(n, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Attribute)
                        and base.value.id == "Module"
                        or isinstance(base, ast.Name)
                        and base.id == "Module"
                        for base in n.bases
                    )
                )
            except Exception:
                logger.debug(
                    "Can't parse classname from code, using legacy uid instead",
                    exc_info=True,
                )
                uid = "__extmod_" + str(uuid.uuid4())
        else:
            if name.startswith(self.config["MODULES_REPO"]):
                name = name.split("/")[-1].split(".py")[0]

            uid = name.replace("%", "%%").replace(".", "%d")

        module_name = f"hikka.modules.{uid}"
        doc = geek.compat(doc)

        async def core_overwrite(e: CoreOverwriteError):
            nonlocal message, is_trusted
            if isinstance(message, Message):
                message._pending_overwrite_data = {
                    "doc": doc,
                    "origin": origin,
                    "save_fs": save_fs,
                    "target_command": e.target,
                }
                await self._send_overwrite_warning(message, e.target, is_trusted=is_trusted)
            return

        try:
            try:
                spec = ModuleSpec(
                    module_name,
                    loader.StringLoader(doc, f"<external {module_name}>"),
                    origin=f"<external {module_name}>",
                )
                instance = await self.allmodules.register_module(
                    spec,
                    module_name,
                    origin,
                    save_fs=save_fs,
                )
            except ImportError as e:
                logger.info(
                    "Module loading failed, attempting dependency installation (%s)",
                    e.name,
                )
                try:
                    requirements = list(
                        filter(
                            lambda x: not x.startswith(("-", "_", ".")),
                            map(
                                str.strip,
                                loader.VALID_PIP_PACKAGES.search(doc)[1].split(),
                            ),
                        )
                    )
                except TypeError:
                    logger.warning(
                        "No valid pip packages specified in code, attempting"
                        " installation from error"
                    )
                    requirements = [
                        {
                            "sklearn": "scikit-learn",
                            "pil": "Pillow",
                            "hikkatl": "Hikka-TL-New",
                        }.get(e.name.lower(), e.name)
                    ]

                if not requirements:
                    raise Exception("Nothing to install") from e

                logger.debug("Installing requirements: %s", requirements)

                if did_requirements:
                    if message is not None:
                        await utils.answer(
                            message,
                            self.strings("restart_required").format(e.name),
                        )
                    return

                if message is not None:
                    await utils.answer(
                        message,
                        self.strings("install_deps").format(
                            "\n".join(f"▫️ <code>{req}</code>" for req in requirements)
                        ),
                    )

                pip = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "-q",
                    "--disable-pip-version-check",
                    "--no-warn-script-location",
                    *["--user"] if loader.USER_INSTALL else [],
                    *requirements,
                )

                rc = await pip.wait()

                if rc != 0:
                    if message is not None:
                        if "com.termux" in os.environ.get("PREFIX", ""):
                            await utils.answer(
                                message,
                                self.strings("termux_error"),
                            )
                        else:
                            await utils.answer(
                                message,
                                self.strings("deps_error"),
                            )
                    return

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_requirements"] = True

                return await self.load_module(**kwargs)
            except CoreOverwriteError as e:
                await core_overwrite(e)
                return
            except loader.LoadError as e:
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    await utils.answer(
                        message,
                        self.strings("load_error").format(utils.escape_html(str(e))),
                    )
                return
        except Exception as e:
            logger.exception("Loading external module failed due to %s", e)
            if message is not None:
                await utils.answer(message, self.strings("module_load_error"))
            return

        if hasattr(instance, "__version__") and isinstance(instance.__version__, tuple):
            version = f" (v{'.'.join(map(str, instance.__version__))})"
        else:
            version = ""

        try:
            try:
                self.allmodules.send_config_one(instance)

                async def inner_proxy():
                    nonlocal instance, message
                    while True:
                        if hasattr(instance, "hikka_wait_channel_approve"):
                            if message:
                                (
                                    module,
                                    channel,
                                    reason,
                                ) = instance.hikka_wait_channel_approve
                                message = await utils.answer(
                                    message,
                                    self.strings("requires_approval").format(
                                        module,
                                        channel.title,
                                        reason
                                    ),
                                )
                                return
                        await asyncio.sleep(0.1)

                task = asyncio.ensure_future(inner_proxy())
                await self.allmodules.send_ready_one(
                    instance,
                    no_self_unload=True,
                    from_dlmod=bool(message),
                )
                task.cancel()
            except CoreOverwriteError as e:
                await core_overwrite(e)
                return
            except loader.LoadError as e:
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    await utils.answer(
                        message,
                        self.strings("load_error").format(utils.escape_html(str(e))),
                    )
                return
            except loader.SelfUnload as e:
                logger.debug("Unloading %s, because it raised `SelfUnload`", instance)
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    await utils.answer(
                        message,
                        self.strings("self_unload").format(utils.escape_html(str(e))),
                    )
                return
            except loader.SelfSuspend as e:
                logger.debug("Suspending %s, because it raised `SelfSuspend`", instance)
                if message:
                    await utils.answer(
                        message,
                        self.strings("self_suspend").format(utils.escape_html(str(e))),
                    )
                return
        except Exception as e:
            logger.exception("Module threw because of %s", e)
            if message is not None:
                await utils.answer(message, self.strings("init_error"))
            return

        instance.hikka_meta_pic = next(
            (
                line.replace(" ", "").split("#metapic:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#metapic:")
            ),
            None,
        )

        pack_url = next(
            (
                line.replace(" ", "").split("#packurl:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#packurl:")
            ),
            None,
        )

        if pack_url and (
            translations := await self.allmodules.translator.load_module_translations(
                pack_url
            )
        ):
            instance.strings.external_strings = translations

        for alias, cmd in self.lookup("settings").get("aliases", {}).items():
            if cmd in instance.commands:
                self.allmodules.add_alias(alias, cmd)

        try:
            modname = instance.strings("name")
        except (KeyError, AttributeError):
            modname = meta_name or getattr(instance, "name", instance.__class__.__name__)

        try:
            developer_entity = await (
                self._client.force_get_entity
                if (
                    developer in self._client.hikka_entity_cache
                    and getattr(
                        await self._client.get_entity(developer),
                        "left",
                        True,
                    )
                )
                else self._client.get_entity
            )(developer)
        except Exception:
            developer_entity = None

        if not isinstance(developer_entity, Channel):
            developer_entity = None

        if message is None:
            return

        trust_status = self.strings("trusted_source") if is_trusted else self.strings("untrusted_install_message")

        commands_list = []
        for _name, fun in sorted(instance.commands.items(), key=lambda x: x[0]):
            doc_str = utils.escape_html(inspect.getdoc(fun)) if fun.__doc__ else self.strings("no_description")
            commands_list.append(f"▫️ <code>{self.get_prefix()}{_name}</code> — {doc_str}")

        commands_text = "\n".join(commands_list)

        description = ""
        if instance.__doc__:
            description = f"ℹ️ {utils.escape_html(inspect.getdoc(instance))}\n\n"

        dev_str = ""
        if developer:
            dev_str = self.strings("developer_label").format(utils.escape_html(developer))

        final_message = self.strings("module_loaded_template").format(
            utils.escape_html(modname),
            utils.ascii_face(),
            version,
            self.strings("blockquote_start"),
            description + commands_text + "\n" + self.strings("blockquote_end"),
            trust_status,
            dev_str
        )

        if meta_img:
            try:
                r = requests.get(meta_img, timeout=10)
                if r.status_code == 200:
                    img_path = tempfile.mktemp(suffix=".jpg")
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                    await self._client.send_file(
                        utils.get_chat_id(message),
                        img_path,
                        caption=final_message,
                        reply_to=getattr(message, "reply_to_msg_id", None),
                    )
                    os.remove(img_path)
                    return
            except Exception:
                pass

        try:
            await utils.answer(message, final_message)
        except MediaCaptionTooLongError:
            short_message = self.strings("too_many_commands_template").format(
                utils.escape_html(modname),
                utils.ascii_face(),
                version,
                self.strings("blockquote_start"),
                description + self.strings("too_many_commands") + self.strings("blockquote_end"),
                trust_status,
                dev_str
            )
            await message.reply(short_message)

    async def _inline__subscribe(
        self,
        call: InlineCall,
        entity: int,
        msg: typing.Callable[[], str],
        subscribe: bool,
    ):
        if not subscribe:
            self.set("do_not_subscribe", self.get("do_not_subscribe", []) + [entity])
            await utils.answer(call, msg())
            await call.answer(self.strings("not_subscribed"))
            return

        await self._client(JoinChannelRequest(entity))
        await utils.answer(call, msg())
        await call.answer(self.strings("subscribed"))

    @loader.command(alias="ulm")
    async def unloadmod(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings("specify_module"))
            return

        instance = self.lookup(args)

        if issubclass(instance.__class__, loader.Library):
            await utils.answer(message, self.strings("cannot_unload_library"))
            return

        try:
            worked = await self.allmodules.unload_module(args)
        except CoreUnloadError as e:
            await utils.answer(
                message,
                self.strings("cannot_unload_core").format(e.module),
            )
            return

        if not self.allmodules.secure_boot:
            self.set(
                "loaded_modules",
                {
                    mod: link
                    for mod, link in self.get("loaded_modules", {}).items()
                    if mod not in worked
                },
            )

        if worked:
            msg = self.strings("unloaded_modules").format(
                ', '.join([(mod[:-3] if mod.endswith('Mod') else mod) for mod in worked])
            )
        else:
            msg = self.strings("nothing_unloaded")

        await utils.answer(message, msg)

    @loader.command()
    async def clearmodules(self, message: Message):
        await self.inline.form(
            self.strings("clear_modules_confirm"),
            message,
            reply_markup=[
                {
                    "text": self.strings("delete_all"),
                    "callback": self._inline__clearmodules,
                },
                {
                    "text": self.strings("cancel"),
                    "action": "close",
                },
            ],
        )

    async def _inline__clearmodules(self, call: InlineCall):
        self.set("loaded_modules", {})

        for file in os.scandir(loader.LOADED_MODULES_DIR):
            try:
                shutil.rmtree(file.path)
            except Exception:
                logger.debug("Failed to remove %s", file.path, exc_info=True)

        await utils.answer(call, self.strings("all_modules_deleted"))
        await self.lookup("Updater").restart_common(call)

    async def _update_modules(self):
        todo = await self._get_modules_to_load()

        self._secure_boot = False

        if self._db.get(loader.__name__, "secure_boot", False):
            self._db.set(loader.__name__, "secure_boot", False)
            self._secure_boot = True
        else:
            for mod in todo.values():
                await self.download_and_install(mod)

            self.update_modules_in_db()

            aliases = {
                alias: cmd
                for alias, cmd in self.lookup("settings").get("aliases", {}).items()
                if self.allmodules.add_alias(alias, cmd)
            }

            self.lookup("settings").set("aliases", aliases)

        self.fully_loaded = True

        with contextlib.suppress(AttributeError):
            await self.lookup("Updater").full_restart_complete(self._secure_boot)

    def flush_cache(self) -> int:
        count = sum(map(len, self._links_cache.values()))
        self._links_cache = {}
        return count

    def inspect_cache(self) -> int:
        return sum(map(len, self._links_cache.values()))

    async def reload_core(self) -> int:
        self.fully_loaded = False

        if self._secure_boot:
            self._db.set(loader.__name__, "secure_boot", True)

        if not self._db.get(main.__name__, "remove_core_protection", False):
            for module in self.allmodules.modules:
                if module.__origin__.startswith("<core"):
                    module.__origin__ = "<reload-core>"

        loaded = await self.allmodules.register_all(no_external=True)
        for instance in loaded:
            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(
                instance,
                no_self_unload=False,
                from_dlmod=False,
            )

        self.fully_loaded = True
        return len(loaded)

    @loader.command()
    async def mlcmd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings("specify_module_mlcmd"))
            return

        exact = True
        if not (
            class_name := next(
                (
                    module.strings("name")
                    for module in self.allmodules.modules
                    if args.lower()
                    in {
                        module.strings("name").lower(),
                        module.__class__.__name__.lower(),
                    }
                ),
                None,
            )
        ):
            if not (
                class_name := next(
                    reversed(
                        sorted(
                            [
                                module.strings["name"].lower()
                                for module in self.allmodules.modules
                            ]
                            + [
                                module.__class__.__name__.lower()
                                for module in self.allmodules.modules
                            ],
                            key=lambda x: difflib.SequenceMatcher(
                                None,
                                args.lower(),
                                x,
                            ).ratio(),
                        )
                    ),
                    None,
                )
            ):
                await utils.answer(message, self.strings("module_not_found_mlcmd"))
                return

            exact = False

        try:
            module = self.lookup(class_name)
            sys_module = inspect.getmodule(module)
            
            module_doc = inspect.getdoc(module) or self.strings("no_description")
            commands_count = len(module.commands)
            
            text = self.strings("module_info").format(
                utils.escape_html(class_name),
                utils.escape_html(module_doc),
                commands_count
            )
            if not exact:
                text += self.strings("exact_not_found")
                
        except Exception:
            await utils.answer(message, self.strings("module_get_error"))
            return

        file = io.BytesIO(sys_module.__loader__.data)
        file.name = f"{class_name}.py"
        file.seek(0)

        await utils.answer_file(
            message,
            file,
            caption=text,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command()
    async def addrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or (
            not utils.check_url(args) and not utils.check_url(f"https://{args}")
        ):
            await utils.answer(message, self.strings("specify_repo_url"))
            return

        if args.endswith("/"):
            args = args[:-1]

        if not args.startswith("https://") and not args.startswith("http://"):
            args = f"https://{args}"

        try:
            r = await utils.run_sync(
                requests.get,
                f"{args}/full.txt",
                auth=(
                    tuple(self.config["basic_auth"].split(":", 1))
                    if self.config["basic_auth"]
                    else None
                ),
            )
            r.raise_for_status()
            if not r.text.strip():
                raise ValueError
        except Exception:
            await utils.answer(message, self.strings("invalid_repo"))
            return

        if args in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings("repo_already_added").format(args))
            return

        self.config["ADDITIONAL_REPOS"] += [args]

        await utils.answer(message, self.strings("repo_added").format(args))

    @loader.command()
    async def delrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or not utils.check_url(args):
            await utils.answer(message, self.strings("specify_repo_del"))
            return

        if args.endswith("/"):
            args = args[:-1]

        if args not in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings("repo_not_found"))
            return

        self.config["ADDITIONAL_REPOS"].remove(args)

        await utils.answer(message, self.strings("repo_deleted").format(args))


if not hasattr(InlineCall, '_pending_overwrite_data'):
    InlineCall._pending_overwrite_data = None
