# Licensed under GNU Affero General Public License v3.0
# BS4 scraping by Sumit Jaiswal <https://github.com/ransomsumit>
# Pyrogram implementation and minor fix(s) by Jyothis <https://github.com/EverythingSuckz>

import os
import re
import math
import aiohttp
import logging
import asyncio
import aiofiles
import traceback
import pyshorteners
import urllib.parse
from io import BytesIO
from random import randint
from threading import Thread
from bs4 import BeautifulSoup as soup
from pyrogram import Client, filters, idle
from PIL import Image, ImageFont, ImageDraw
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle, InputTextMessageContent

chilp_it = pyshorteners.Shortener()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

loop = asyncio.get_event_loop()

token = os.environ.get("bot_api")
api_id = os.environ.get("api_id")
api_hash = os.environ.get("api_hash")

query_cache = dict()

MangaKyo = Client(
    ':memory:',
    api_id=api_id,
    api_hash=api_hash,
    bot_token=token
)

holy = "https://w27.holymanga.net/"

the_bot = None

async def async_get(url, *args, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, *args, **kwargs) as resp:
            return await resp.read()


@MangaKyo.on_message(filters.private & filters.command(['start', 'help']), group=1)
async def send_start(_, m: Message):
    if len(m.text.split()) < 2:
        await m.reply(f'Howdy {m.from_user.mention(style="md")},\nWelcome to {the_bot.username}. There is only one command /manga.\n\nEx. `/manga one piece`')


@MangaKyo.on_message(filters.command(['manga', f'manga@MangaKyoBot']))
async def manga_search(_, m: Message):
    if len(m.text.split()) < 1:
        await m.reply('Use /manga <your query>', parse_mode='md')
        return
    query = m.text.split(' ', 1)[1]
    requery = re.sub(" ", "+", query.strip())
    req = await async_get(holy + "?s=" + str(requery), headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    sou = soup(req, "html.parser").find("div", class_ = "comics-grid").find_all("h3", class_ = "name")
    if(sou == []):
        await m.reply("Nothing Found!! Make sure to type the name correct or in different keyword. Ask admins if persistent @Ransom_s")
    else:
        buttons = []
        for i in range(len(sou)):
            text = sou[i].find("a").getText()
            if len(text)>40:
                text = text[:20] + "...." + text[-20:]
            url_full = sou[i].find("a").attrs["href"]
            url = re.sub(holy, '', url_full)
            if len(url)>40:
                url = f"{chilp_it.chilpit.short(url_full)}%#{m.from_user.id}"
            else:
                url = f"{url}@#{m.from_user.id}"
            buttons.append([InlineKeyboardButton(text, callback_data=url)])
        await m.reply(f"Results for {query}", reply_markup=InlineKeyboardMarkup(buttons))


@MangaKyo.on_message(filters.command('read'))
async def manga_reader(_, m: Message):
    url = re.sub("/read ", "", m.text)
    await m.delete()
    if m.chat.type == "group" or m.chat.type == "supergroup":
        await m.reply("Sorry, manga reading is not allowed in groups 😭")
        return
    req = await async_get(url, headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    title = soup(req, "html.parser").find("a", class_ = "bg-tt").getText()
    url_quotes = urllib.parse.quote_plus(url)
    buttons = [[InlineKeyboardButton("Read Here", url=f"https://animebot-play.herokuapp.com/mng/{url_quotes}")]]
    await m.reply(title, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='html', quote=True)


async def get_chapters(url):
    req = await async_get(url, headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    sou = soup(req, "html.parser").find("div", class_ = "bg-white well")
    about = sou.find("div", class_ = "new-chap").getText().strip()
    num = int(re.findall(r'\d+', about)[0])
    return num

async def get_details(url):
    req = await async_get(url, headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    sou = soup(req, "html.parser").find("div", class_ = "bg-white well")
    img = sou.find("div", class_="thumb text-center").find("img").attrs['src']
    info = sou.find("div", class_ = "info")
    about = "<b>" + info.find("h1", class_="name bigger").getText() + "</b>\n"
    about += "<b>Rating: </b>" + info.find("div", class_ = "counter").getText() + "\n\n"
    about += "<b>" + info.find("div", class_ = "author").getText().strip().replace("\n","") + "</b>\n\n"
    about += "<b>" + info.find("div", class_ = "genre").getText().strip().replace("\n","") + "</b>\n\n"
    about += "<b>" + info.find("div", class_ = "new-chap").getText().strip() + "</b>\n"
    total_chap = await get_chapters(url)
    about += "<pre>Approx " + str(math.ceil(total_chap/50)) + " pages of 50 results made</pre>\n\n"
    try:
        about += "<code>" + sou.find("div", class_ = "comic-description").find("p").getText() + "</code>"
    except Exception as e:
        about += "<code>" + sou.find("div", class_ = "comic-description").getText() + "</code>"
    return about, img

async def genereate_cover(poster_url):
    try:
        url_white = "https://i.imgur.com/R1yA2Ik.jpeg"

        # get raw content
        bg_raw = await async_get(url_white)
        poster_raw = await async_get(poster_url)

        # open
        background = Image.open(BytesIO(bg_raw))
        poster = Image.open(BytesIO(poster_raw))
        
        # get dimensions
        back_width, back_height = background.size
        poster_width, poster_height = poster.size

        # resizing
        poster_resize_height_percent = back_height / poster_height
        resize_width = int((poster_width * poster_resize_height_percent) // 1)
        poster = poster.resize((resize_width, back_height))

        # paste
        background.paste(poster)

        # draw
        font = ImageFont.truetype(r'dacassa.ttf', 35)
        draw = ImageDraw.Draw(background)
        rgb = (randint(0, 255), randint(0, 255), randint(0, 255))
        draw.text((resize_width + (back_width - resize_width) // 3.5, int(back_width * 0.30)), "MangaKyo", rgb, font = font, align="center")

        # saving
        output = BytesIO()
        output.name = 'poster.png'
        background.save(output, format="PNG")
        return output
    except:
        logging.error(traceback.format_exc())
        return

@MangaKyo.on_callback_query(filters.regex(pattern=r'^(https?:\/\/[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b|[-a-zA-Z0-9\-)([-a-zA-Z0-9():_\+.~?&\/\/=]+)([%#@]+)(\d+)$'))
async def callback_handler(b: Client, c: CallbackQuery):
    cslug = c.matches[0].group(1)
    identifier = c.matches[0].group(2)[:1]
    user_id = int(c.matches[0].group(3))
    if(c.from_user.id != user_id):
        await c.answer("Not Your Query!", show_alert = True)
        return
    await c.message.delete()
    status = await c.message.reply('<i>Please wait</i>')
    if identifier == '@':
        url = holy + cslug
    elif identifier == '%':
        url = chilp_it.chilpit.expand(cslug)
    slug = re.sub(holy, "" ,url)
    slug = re.sub("/", "", slug)
    try:
        about, image_url = await get_details(url)
    except Exception:
        await c.answer("Error Occurred", show_alert=True)
        logging.error(traceback.format_exc())
    if c.message.chat.type == "group" or c.message.chat.type == "supergroup":
        buttons = [[InlineKeyboardButton("Read", url=f"https://t.me/{the_bot.username}?start={slug}")]]
    else:
        buttons = [[InlineKeyboardButton("Read", switch_inline_query_current_chat=slug)]]
    if image_url:
        poster = await genereate_cover(image_url)
        await c.message.reply_photo(poster, caption=about, parse_mode="html", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await c.message.reply(about, parse_mode="html", reply_markup=InlineKeyboardMarkup(buttons))
    await status.delete()

@MangaKyo.on_message(filters.private & filters.command('start'), group=2)
async def send_pages(_, m: Message):
    if len(m.text.split()) > 1:
        slug = re.sub("/start ", "", m.text)
        if m.chat.type == "group" or m.chat.type == "supergroup":
            await m.reply("Sorry, manga reading is not allowed in groups 😭")
            return
        await m.reply('Press here to view chapters', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Press here', switch_inline_query_current_chat=slug)]]))


async def foo(url, lis, i):
    u = url + "/page-" + str(i) + "/"
    req = await async_get(u, headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    sou = soup(req, "html.parser").find_all("h2", class_ = "chap")
    temp = {}
    for j in sou:
        temp[j.find("a").getText()]= j.find("a").attrs['href']
    lis[i] =  temp

def async_for_thread(*args):
    thread_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(thread_loop)
    thread_loop.run_until_complete(foo(*args))
    thread_loop.close()

async def count_chapters(url):
    req = await async_get(url, headers = {"User-Agent" : "Mozilla/5.0", 'x-requested-with': 'XMLHttpRequest'})
    try:
        num = soup(req, "html.parser").find("div", class_ = "pagination").find_all("a", class_ = "next page-numbers")[1].attrs['href']
        num = int(num[num.find('page-')+5:])
    except Exception as e:
        num = 1
    threads = [None] * num
    lis = {}
    for i in range(1,num+1):
        threads[i-1] = Thread(target=async_for_thread, args=(url, lis, i))
        threads[i-1].start()
    for i in range(len(threads)):
        threads[i].join()
    temp = {}
    for i in range(1,len(lis)+1):
        temp = {**temp, **lis[i]}
    return temp

async def genarate_results(name, offset=0):
    url = holy + name
    from_cache = query_cache.get(url)
    if not from_cache:
        all_chapters = await count_chapters(url)
        logging.info(f'Fetching new results for {name}')
        query_cache[url] = all_chapters
    all_chapters = query_cache.get(url)
    reversed_dict = dict(reversed(list(all_chapters.items())))
    chapters_name = list(reversed_dict.keys())
    total = len(chapters_name)
    r = []
    if total>50:
        for i in range(offset, offset+50):
            try:
                r.append(InlineQueryResultArticle(title=chapters_name[i][:20] + "..." + chapters_name[i][-20:], input_message_content=InputTextMessageContent('/read ' + reversed_dict[chapters_name[i]])))
            except IndexError:
                continue
    else:
        for i in range(offset, total):
            try:
                r.append(InlineQueryResultArticle(title=chapters_name[i][:20] + "..." + chapters_name[i][-20:], input_message_content=InputTextMessageContent('/read ' + reversed_dict[chapters_name[i]])))
            except TypeError:
                continue
    return r, total

@MangaKyo.on_inline_query(filters.regex(pattern=r'^((?:\w+-?)+\w+)$'))
async def query_text(_, q: InlineQuery):
    res, total = await genarate_results(q.query, offset=int(q.offset) if q.offset != '' else 0)
    await q.answer(
        results=res,
        switch_pm_text=f"Found {total} Chapters",
        switch_pm_parameter="start",
        cache_time=1,
        next_offset='50' if q.offset == '' else str(int(q.offset) + 50)
    )
    # try:
    #     manga_chap(inline_query.id, in_query.lower(), int(page))
    # except Exception as e:
    #     r = types.InlineQueryResultArticle('1', "Make Sure to follow correct syntax, name + pageNo. with a space", types.InputTextMessageContent('Make Sure to follow correct syntax, name + pageNo. with a space \nError: ' + str(e)))
    #     r2 = types.InlineQueryResultArticle('2', 'Example : one-piece 11', types.InputTextMessageContent('Something went wrong ' + str(e)))
    #     bot.answer_inline_query(inline_query.id, [r,r2])



async def start_bot():
    global the_bot
    try:
        req = await async_get("https://drive.google.com/u/0/uc?id=1WPnro8tmf_bCmpSabblIYfauV8JZlnPq&export=download")
        async with aiofiles.open('dacassa.ttf', 'wb') as f:
            await f.write(req)
            await f.close()
    except:
        logging.error(traceback)
    await MangaKyo.start()
    the_bot = await MangaKyo.get_me()
    print(f'Pyrogram stated on @{the_bot.username} successfully!')
    await idle()

if __name__ == '__main__':
    loop.run_until_complete(start_bot())