"""
CodeHelper Discord Bot — Railway Edition
Fast AI responses using Groq

Deploy on Railway:
  Set env vars: DISCORD_TOKEN, GROQ_API_KEY
"""

import os
import discord
from discord.ext import commands
from groq import Groq

# ── Config ───────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GROQ_API_KEY  = os.environ["GROQ_API_KEY"]
BOT_PREFIX    = "!"
MAX_MSG_LEN   = 1900

MODEL = "llama-3.3-70b-versatile"

LANG_ALIASES = {
    "c++": "cpp", "cpp": "cpp",
    "python": "python", "py": "python",
    "lua": "lua", "luna": "lua",
}

SYSTEM_PROMPT = """You are CodeHelper, an expert programming assistant for C++, Python, and Lua.

Your job:
1. GENERATE complete, working, well-commented code when asked.
2. FIX errors — identify the bug, explain why it's wrong, show the corrected code.
3. EXPLAIN code clearly — line by line if needed.
4. CONVERT code between C++, Python, and Lua accurately.
5. COMPARE how the same thing works across all three languages.

Rules:
- Always wrap code in triple backticks with the language tag: ```cpp  ```python  ```lua
- For fixes: show the BROKEN code first (marked ❌), then the FIXED code (marked ✅), then explain.
- For generation: include comments explaining what each important part does.
- Be concise but complete. Never leave code half-finished.
- Only help with C++, Python, and Lua. Politely decline other languages.
"""

# ── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot    = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)
client = Groq(api_key=GROQ_API_KEY)

histories: dict[int, list[dict]] = {}

def get_history(cid: int) -> list[dict]:
    return histories.setdefault(cid, [])

def push_history(cid: int, role: str, content: str):
    h = get_history(cid)
    h.append({"role": role, "content": content})
    if len(h) > 20:
        histories[cid] = h[-20:]

def split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    
    parts = []
    buf = ""
    in_block = False
    
    for line in text.splitlines(keepends=True):
        if line.strip().startswith("```"):
            in_block = not in_block

        # If a single line is somehow over limit, force split it
        if len(line) > limit:
            if buf:
                parts.append(buf)
                buf = ""
            for i in range(0, len(line), limit):
                parts.append(line[i:i+limit])
            continue

        if len(buf) + len(line) > limit:
            # Close open code block before splitting
            if in_block:
                buf += "```"
            parts.append(buf)
            # Reopen code block in new chunk
            buf = "```\n" + line if in_block else line
        else:
            buf += line

    if buf:
        parts.append(buf)

    return parts or [text]

async def groq_chat(cid: int, prompt: str) -> str:
    push_history(cid, "user", prompt)
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + get_history(cid)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
        )
        answer = resp.choices[0].message.content
        push_history(cid, "assistant", answer)
        return answer
    except Exception as e:
        return f"⚠️ Groq error: {e}"

async def send_chunks(ctx, text: str):
    for chunk in split_message(text):
        await ctx.reply(chunk)

# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help | C++ ⚙️ Python 🐍 Lua 🌙"
        )
    )
    print(f"✅ CodeHelper (Groq/{MODEL}) online as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        content = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if content:
            async with message.channel.typing():
                reply = await groq_chat(message.channel.id, content)
            for chunk in split_message(reply):
                await message.reply(chunk)
            return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("⚠️ Missing argument. Try `!help` to see usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.reply(f"⚠️ {error}")

# ── Commands ──────────────────────────────────────────────────────────────────

@bot.command(name="make", aliases=["create", "build", "generate"])
async def make(ctx, lang: str, *, description: str):
    target = LANG_ALIASES.get(lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{lang}`. Use: cpp, python, lua")
    prompt = f"Write complete, working {target} code for: {description}\nInclude helpful comments. Make sure it actually runs."
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="fix", aliases=["debug", "error"])
async def fix(ctx, *, code_and_error: str):
    prompt = f"Fix this code. Show the broken version (❌), then the fixed version (✅), then explain what was wrong:\n\n{code_and_error}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="ask")
async def ask(ctx, *, question: str):
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, question)
    await send_chunks(ctx, reply)

@bot.command(name="explain")
async def explain(ctx, *, code: str):
    prompt = f"Explain this code clearly, line by line if needed:\n\n{code}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="convert", aliases=["translate"])
async def convert(ctx, to_lang: str, *, code: str):
    target = LANG_ALIASES.get(to_lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{to_lang}`. Use: cpp, python, lua")
    prompt = f"Convert this code to {target}. Keep the same logic and add comments where syntax differs:\n\n{code}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="snippet", aliases=["example"])
async def snippet(ctx, lang: str, *, topic: str):
    target = LANG_ALIASES.get(lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{lang}`. Use: cpp, python, lua")
    prompt = f"Show a short, practical {target} snippet demonstrating: {topic}. Include a brief explanation."
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="compare")
async def compare(ctx, *, topic: str):
    prompt = f"Compare '{topic}' across C++, Python, and Lua. Show a code example for each and highlight key differences."
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="optimize", aliases=["improve"])
async def optimize(ctx, *, code: str):
    prompt = f"Review this code and suggest optimizations. Show the improved version and explain what changed:\n\n{code}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)

@bot.command(name="clear", aliases=["reset"])
async def clear(ctx):
    histories.pop(ctx.channel.id, None)
    await ctx.reply("🧹 History cleared! Fresh start.")

@bot.command(name="model")
async def model_info(ctx):
    await ctx.reply(f"🤖 Currently using **Groq / {MODEL}**")

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🤖 CodeHelper — Command Reference",
        description=f"Powered by **Groq** (`{MODEL}`) — fast AI for C++, Python & Lua!",
        color=0xF55036,
    )
    embed.add_field(name="🔨 Generate Code", value="`!make <lang> <description>`\n`!snippet <lang> <topic>`", inline=False)
    embed.add_field(name="🐛 Fix & Debug", value="`!fix <code + error>`\n`!optimize <code>`", inline=False)
    embed.add_field(name="📖 Learn", value="`!ask <question>`\n`!explain <code>`\n`!compare <topic>`\n`!convert <lang> <code>`", inline=False)
    embed.add_field(name="💡 Other", value="`!model` • `!clear` • **@mention** me to chat freely", inline=False)
    embed.add_field(name="🌐 Languages", value="`cpp` / `c++`  •  `python` / `py`  •  `lua` / `luna`", inline=False)
    embed.set_footer(text="Hosted on Railway • Groq Edition")
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
