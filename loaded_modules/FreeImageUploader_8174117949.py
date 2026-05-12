#         ▄▀█ █▀█ █▀▀ ▀█▀ ▄▀█
#.        █▀█ █▄█ █▀  ░█░ █▀█
#              © Copyright 2026
#           https://t.me/FrontendVSCode
#
# 🔒      Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

#img "https://iili.io/BDRQs7s.jpg"
# meta pic: https://iili.io/BDRQs7s.jpg
# meta banner: https://iili.io/BDRQs7s.jpg
# meta developer: @NEBULASoftware
# scope: inline
# scope: softa_only
# scope: softa_min 1.2.10

__version__ = (1, 3, 0)

import aiohttp
import base64
from telethon.tl.types import Message
from telethon.tl.custom import Message as CustomMessage
from .. import loader, utils


@loader.tds
class FreeImageUploader(loader.Module):
    """Upload images to Freeimage (iili.io) with preview"""
    
    strings = {
        "name": "FreeImage Hosting",
        "noargs": "🚫 <b>Reply to a photo!</b>",
        "err": "🚫 <b>Upload error:</b> <code>{error}</code>",
        "uploading": "⏳ <b>Uploading image to Freeimage...</b>",
        "uploaded": "✅ <b>Image uploaded successfully!</b>\n\n🔗 <code>{url}</code>\n\n🌐 <a href='{url}'>Open link</a>",
        "not_image": "🚫 <b>Only images are supported</b> (jpg, png, gif)",
        "_cmd_doc_img": "Upload photo to Freeimage — short link with .jpg",
    }
    
    strings_ru = {
        "name": "FreeImage Хостинг",
        "noargs": "🚫 <b>Сделай реплай на фото!</b>",
        "err": "🚫 <b>Ошибка загрузки:</b> <code>{error}</code>",
        "uploading": "⏳ <b>Загружаю изображение на Freeimage...</b>",
        "uploaded": "✅ <b>Изображение успешно загружено!</b>\n\n🔗 <code>{url}</code>\n\n🌐 <a href='{url}'>Открыть ссылку</a>",
        "not_image": "🚫 <b>Поддерживаются только изображения</b> (jpg, png, gif)",
        "_cmd_doc_img": "Загрузить фото на Freeimage — короткая ссылка с .jpg",
    }
    
    strings_ua = {
        "name": "FreeImage Хостинг",
        "noargs": "🚫 <b>Зроби реплай на фото!</b>",
        "err": "🚫 <b>Помилка завантаження:</b> <code>{error}</code>",
        "uploading": "⏳ <b>Завантажую зображення на Freeimage...</b>",
        "uploaded": "✅ <b>Зображення успішно завантажено!</b>\n\n🔗 <code>{url}</code>\n\n🌐 <a href='{url}'>Відкрити посилання</a>",
        "not_image": "🚫 <b>Підтримуються тільки зображення</b> (jpg, png, gif)",
        "_cmd_doc_img": "Завантажити фото на Freeimage — коротке посилання з .jpg",
    }
    
    strings_de = {
        "name": "FreeImage Hosting",
        "noargs": "🚫 <b>Antworte auf ein Foto!</b>",
        "err": "🚫 <b>Upload-Fehler:</b> <code>{error}</code>",
        "uploading": "⏳ <b>Lade Bild zu Freeimage hoch...</b>",
        "uploaded": "✅ <b>Bild erfolgreich hochgeladen!</b>\n\n🔗 <code>{url}</code>\n\n🌐 <a href='{url}'>Link öffnen</a>",
        "not_image": "🚫 <b>Nur Bilder werden unterstützt</b> (jpg, png, gif)",
        "_cmd_doc_img": "Foto zu Freeimage hochladen — kurzer Link mit .jpg",
    }
    
    async def get_image_bytes(self, message: Message):
        """Get image bytes and extension from reply"""
        reply = await message.get_reply_message()
        
        if not reply or not reply.media:
            await utils.answer(message, self.strings("noargs"))
            return None, None
        
        if not reply.file or not reply.file.mime_type or not reply.file.mime_type.startswith('image/'):
            await utils.answer(message, self.strings("not_image"))
            return None, None
        
        img_bytes = await self._client.download_media(reply, bytes)
        if not img_bytes:
            await utils.answer(message, self.strings("err").format(error="Failed to download"))
            return None, None
        
        mime = reply.file.mime_type
        ext = "jpg"
        if "png" in mime:
            ext = "png"
        elif "gif" in mime:
            ext = "gif"
        
        return img_bytes, ext
    
    @loader.command()
    async def imgcmd(self, message: Message):
        """Upload photo to Freeimage (iili.io)"""
        
        reply = await message.get_reply_message()
        
        if not reply or not reply.media:
            await utils.answer(message, self.strings("noargs"))
            return
        
        status = await message.reply(self.strings("uploading"))
        
        img_bytes, ext = await self.get_image_bytes(message)
        if not img_bytes:
            await status.delete()
            return
        
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        async with aiohttp.ClientSession() as session:
            try:
                data = {
                    "key": "6d207e02198a847aa98d0a2a901485a5",
                    "action": "upload",
                    "source": img_base64,
                    "format": "json"
                }
                
                async with session.post("https://freeimage.host/api/1/upload", data=data) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    
                    result = await resp.json()
                    if not result.get("success"):
                        raise Exception(result.get("error", {}).get("message", "Unknown error"))
                    
                    url = result["image"]["url"]
                    
                    if not url.endswith(('.jpg', '.png', '.gif')):
                        url = f"{url}.jpg"
                    
                    await status.delete()
                    
                    original_photo = await self._client.download_media(reply, bytes)
                    
                    await self._client.send_file(
                        message.chat_id,
                        original_photo,
                        caption=self.strings("uploaded").format(url=url),
                        reply_to=reply.id,
                        link_preview=True
                    )
                    
                    await message.delete()
                    
            except Exception as e:
                await status.edit(self.strings("err").format(error=str(e)))