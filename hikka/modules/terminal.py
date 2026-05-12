#.        ▄▀█ █▀█ █▀▀ ▀█▀ ▄▀█
#.        █▀█ █▄█ █▀  ░█░ █▀█
#              © Copyright 2026
#           https://t.me/FrontendVSCode
#
# 🔒      Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

#img "https://i.pinimg.com/736x/32/42/83/32428384c94b93cd597d0ff5429d4f97.jpg"
# meta pic: https://i.pinimg.com/736x/32/42/83/32428384c94b93cd597d0ff5429d4f97.jpg
# meta banner: https://i.pinimg.com/736x/32/42/83/32428384c94b93cd597d0ff5429d4f97.jpg
# meta developer: @NEBULASoftware
# scope: inline
# scope: softa_only
# scope: softa_min 1.2.10


from .. import loader, utils
import asyncio
import contextlib
import logging
import re
import time
import typing

import hikkatl
from .. import loader, utils

logger = logging.getLogger(__name__)

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

ANSI_COLORS = {
    "30": "black",
    "31": "red",
    "32": "green",
    "33": "orange",
    "34": "blue",
    "35": "purple",
    "36": "teal",
    "37": "gray",
}


def ansi_to_html(text: str) -> str:
    text = ANSI_RE.sub("", text)

    for code, color in ANSI_COLORS.items():
        text = text.replace(
            f"\x1b[{code}m",
            f'<span style="color:{color}">',
        )

    return text.replace("\x1b[0m", "</span>")


def hash_msg(message):
    return f"{utils.get_chat_id(message)}/{message.id}"

async def read_stream(func, stream, delay: float):
    buf = b""
    last_task = None

    while True:
        data = await stream.read(1)

        if not data:
            if last_task:
                last_task.cancel()
                with contextlib.suppress(Exception):
                    await func(buf.decode(errors="ignore"))
            break

        buf += data

        if last_task:
            last_task.cancel()

        last_task = asyncio.create_task(_delayed(func, buf, delay))


async def _delayed(func, data, delay):
    await asyncio.sleep(delay)
    with contextlib.suppress(Exception):
        await func(data.decode(errors="ignore"))

class MessageEditor:
    def __init__(self, message, command):
        self.message = message
        self.command = command.replace("cd ~ && ", "", 1)

        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.start = time.time()

    async def update_stdout(self, data):
        self.stdout = data
        await self.redraw()

    async def update_stderr(self, data):
        self.stderr = data
        await self.redraw()

    async def redraw(self):
        elapsed = int(time.time() - self.start)

        text = (
            f"🧩 Command [ <code>{utils.escape_html(self.command)}</code> ]\n\n"
        )

        if self.stdout:
            text += (
                "📥 Output:\n"
                f"<pre>{ansi_to_html(utils.escape_html(self.stdout[-3000:]))}</pre>\n"
            )

        if self.stderr:
            text += (
                "⚠ Error:\n"
                f"<pre>{ansi_to_html(utils.escape_html(self.stderr[-1500:]))}</pre>\n"
            )

        if self.rc is not None:
            text += (
                f"\n📦 Time: <code>{elapsed}s</code>\n"
                f"📌 Exit code: <code>{self.rc}</code>"
            )

        with contextlib.suppress(Exception):
            await utils.answer(self.message, text)

    async def done(self, rc):
        self.rc = rc
        await self.redraw()

@loader.tds
class TerminalMod(loader.Module):
    """Terminal (EN/RU + ANSI + history + bash fix)"""

    strings = {
        "name": "Terminal",

       
        "usage": "Usage: <code>.t python --version</code>",
        "history": "📜 History",
        "empty": "empty",

       
        "usage_ru": "Использование: <code>.t python --version</code>",
        "history_ru": "📜 История",
    }

    strings_ru = {
        "usage": "Использование: <code>.t python --version</code>",
        "history": "📜 История",
        "empty": "пусто",
    }

    def __init__(self):
        self.history = []
    @loader.command()
    async def testloadcmd(self, message):
        """Test team - replies hello"""
        await utils.answer(message, "🧩 <blockquote>Hello! I'm a test module!</blockquote>")

    @loader.command()
    async def testcheckcmd(self, message):
        """Checking the module operation"""
        await utils.answer(message, "🧩 <blockquote>Everything works! 🏓</blockquote>")

    @loader.command(alias="t")
    async def terminalcmd(self, message):
        args = utils.get_args_raw(message)

        
        if args.strip() in {"-h", "history"}:
            hist = "\n".join(self.history[-15:]) or self.strings("empty")
            return await utils.answer(
                message,
                f"{self.strings('history')}\n<code>{hist}</code>",
            )

        if not args:
            return await utils.answer(
                message,
                self.strings("usage"),
            )

        self.history.append(args)

        await self.run(message, args)

    async def run(self, message, cmd):
        full_cmd = f"bash -lc 'cd ~ && {cmd}'"

        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        editor = MessageEditor(message, cmd)

        await editor.redraw()

        await asyncio.gather(
            read_stream(editor.update_stdout, proc.stdout, 0.3),
            read_stream(editor.update_stderr, proc.stderr, 0.3),
        )

        await editor.done(await proc.wait())