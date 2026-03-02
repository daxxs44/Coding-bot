"""
CodeHelper Discord Bot — Groq Edition
Fast AI responses using Groq (LLaMA / DeepSeek models)

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

# Groq model options (uncomment the one you want):
# "llama-3.3-70b-versatile"   ← best quality (recommended)
# "llama-3.1-8b-instant"      ← fastest / cheapest
# "deepseek-r1-distill-llama-70b" ← great for coding
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
    parts, buf, in_block = [], "", False
    for line in text.splitlines(keepends=True):
        if line.strip().startswith("```"):
            in_block = not in_block
        if len(buf) + len(line) > limit and not in_block:
            parts.append(buf)
            buf = line
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
    """Generate complete working code.
    !make python a calculator with +/-/*/divide
    !make cpp a linked list with push/pop
    !make lua a simple inventory system
    """
    target = LANG_ALIASES.get(lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{lang}`. Use: cpp, python, lua")
    prompt = f"Write complete, working {target} code for: {description}\nInclude helpful comments. Make sure it actually runs."
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="fix", aliases=["debug", "error"])
async def fix(ctx, *, code_and_error: str):
    """Fix broken code. Paste your code + error message.
    !fix ```python
    def add(a, b)
        return a + b
    ```
    SyntaxError: invalid syntax
    """
    prompt = (
        f"Fix this code. Show the broken version (❌), then the fixed version (✅), "
        f"then explain what was wrong:\n\n{code_and_error}"
    )
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="ask")
async def ask(ctx, *, question: str):
    """Ask any C++, Python, or Lua question."""
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, question)
    await send_chunks(ctx, reply)


@bot.command(name="explain")
async def explain(ctx, *, code: str):
    """Explain what a piece of code does."""
    prompt = f"Explain this code clearly, line by line if needed:\n\n{code}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="convert", aliases=["translate"])
async def convert(ctx, to_lang: str, *, code: str):
    """Convert code to another language.
    !convert python ```cpp
    cout << "Hello" << endl;
    ```
    """
    target = LANG_ALIASES.get(to_lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{to_lang}`. Use: cpp, python, lua")
    prompt = f"Convert this code to {target}. Keep the same logic and add comments where syntax differs:\n\n{code}"
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="snippet", aliases=["example"])
async def snippet(ctx, lang: str, *, topic: str):
    """Get a quick code snippet on a topic.
    !snippet lua coroutines
    !snippet cpp lambda functions
    """
    target = LANG_ALIASES.get(lang.lower())
    if not target:
        return await ctx.reply(f"❌ Unknown language `{lang}`. Use: cpp, python, lua")
    prompt = f"Show a short, practical {target} snippet demonstrating: {topic}. Include a brief explanation."
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="compare")
async def compare(ctx, *, topic: str):
    """Compare a topic across C++, Python, and Lua.
    !compare error handling
    !compare OOP classes
    """
    prompt = (
        f"Compare '{topic}' across C++, Python, and Lua. "
        f"Show a code example for each and highlight key differences."
    )
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="optimize", aliases=["improve"])
async def optimize(ctx, *, code: str):
    """Get suggestions to improve your code."""
    prompt = (
        f"Review this code and suggest optimizations. "
        f"Show the improved version and explain what changed and why:\n\n{code}"
    )
    async with ctx.typing():
        reply = await groq_chat(ctx.channel.id, prompt)
    await send_chunks(ctx, reply)


@bot.command(name="clear", aliases=["reset"])
async def clear(ctx):
    """Clear conversation history for this channel."""
    histories.pop(ctx.channel.id, None)
    await ctx.reply("🧹 History cleared! Fresh start.")


@bot.command(name="model")
async def model_info(ctx):
    """Show the current AI model being used."""
    await ctx.reply(f"🤖 Currently using **Groq / {MODEL}**\nChange the `MODEL` variable in the bot to switch models.")


@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🤖 CodeHelper — Command Reference",
        description=f"Powered by **Groq** (`{MODEL}`) — fast AI for C++, Python & Lua!",
        color=0xF55036,  # Groq orange
    )
    embed.add_field(
        name="🔨 Generate Code",
        value=(
            "`!make <lang> <description>`\n"
            "→ `!make python a todo list app`\n"
            "→ `!make cpp a binary search tree`\n\n"
            "`!snippet <lang> <topic>`\n"
            "→ `!snippet lua metatables`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🐛 Fix & Debug",
        value=(
            "`!fix <your code + error>`\n"
            "→ Paste broken code + error, I'll fix it\n\n"
            "`!optimize <code>`\n"
            "→ Get suggestions to make your code better"
        ),
        inline=False,
    )
    embed.add_field(
        name="📖 Learn",
        value=(
            "`!ask <question>` — Any question\n"
            "`!explain <code>` — Understand what code does\n"
            "`!compare <topic>` — C++ vs Python vs Lua\n"
            "`!convert <lang> <code>` — Translate to another language"
        ),
        inline=False,
    )
    embed.add_field(
        name="💡 Other",
        value=(
            "`!model` — See which AI model is active\n"
            "`!clear` — Reset chat history\n"
            "**@mention** me to chat freely\n"
            "I remember the last **10 exchanges** per channel"
        ),
        inline=False,
    )
    embed.add_field(
        name="🌐 Languages",
        value="`cpp` / `c++`  •  `python` / `py`  •  `lua` / `luna`",
        inline=False,
    )
    embed.set_footer(text="Hosted on Railway • Groq Edition")
    await ctx.send(embed=embed)


# ── Run ───────────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
