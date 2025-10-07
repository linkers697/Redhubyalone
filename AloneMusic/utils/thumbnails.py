import os
import re
import random
import aiohttp
import aiofiles
import traceback
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

def truncate(text):
    words = text.split(" ")
    text1, text2 = "", ""
    for w in words:
        if len(text1) + len(w) < 30:
            text1 += " " + w
        elif len(text2) + len(w) < 30:
            text2 += " " + w
    return [text1.strip(), text2.strip()]

def draw_text_with_outline(draw, pos, text, font, fill, outline_color=(0, 0, 0)):
    if not hasattr(draw, "text"):
        return
    x0, y0 = pos
    outline_range = 2
    for dx in range(-outline_range, outline_range + 1):
        for dy in range(-outline_range, outline_range + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x0 + dx, y0 + dy), text, font=font, fill=outline_color)
    draw.text((x0, y0), text, font=font, fill=fill)

# Fancy rounded progress bar
def draw_rounded_bar(draw, xy, radius, fill_bg, fill_fg, progress=0.7):
    x0, y0, x1, y1 = xy
    # Background
    draw.rounded_rectangle(xy, radius=radius, fill=fill_bg)
    # Foreground
    progress_x = x0 + int((x1 - x0) * progress)
    draw.rounded_rectangle([x0, y0, progress_x, y1], radius=radius, fill=fill_fg)
    # Knob
    knob_radius = (y1 - y0) // 2
    draw.ellipse([progress_x - knob_radius, y0, progress_x + knob_radius, y1], fill=fill_fg)

async def get_thumb(videoid: str):
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        data = await results.next()
        if not data or "result" not in data or not data["result"]:
            print("No video results found")
            return None

        result = data["result"][0]
        title = re.sub("\W+", " ", result.get("title", "Unsupported Title")).title()
        duration = result.get("duration", "Unknown Mins")
        thumbnail_url = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        views = result.get("viewCount", {}).get("short", "Unknown Views")
        channel = result.get("channel", {}).get("name", "Unknown Channel")

        if not thumbnail_url:
            print("No thumbnail URL found")
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status == 200:
                    os.makedirs("cache", exist_ok=True)
                    async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                        await f.write(await resp.read())
                else:
                    print(f"Failed to download thumbnail: {resp.status}")
                    return None

        def safe_open(path):
            try:
                return Image.open(path).convert("RGBA")
            except Exception as e:
                print(f"Error opening image {path}: {e}")
                return None

        icons = safe_open("AloneMusic/assets/icons.png")
        speaker_icon = safe_open("AloneMusic/assets/speaker.png")
        youtube = safe_open(f"cache/thumb{videoid}.png")
        if not all([icons, speaker_icon, youtube]):
            return None

        youtube_resized = changeImageSize(1280, 720, youtube)

        # Background: blur + overlay
        bg = youtube_resized.filter(ImageFilter.GaussianBlur(25))
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.4)
        overlay = Image.new("RGBA", bg.size, (15, 15, 25, 200))
        background = Image.alpha_composite(bg, overlay)
        draw = ImageDraw.Draw(background)

        # Background watermark
        try:
            font_bg = ImageFont.truetype("AloneMusic/assets/font3.ttf", 120)
        except:
            font_bg = ImageFont.load_default()
        draw.text((320, 250), "AsianBots", font=font_bg, fill=(255, 255, 255, 50))

        # Logo crop + glow
        Xc, Yc = youtube.width / 2, youtube.height / 2
        x1, y1, x2, y2 = Xc - 250, Yc - 250, Xc + 250, Yc + 250
        rand_color = (random.randint(100, 255), random.randint(50, 200), random.randint(100, 255))
        logo = youtube.crop((x1, y1, x2, y2))
        logo.thumbnail((350, 350), Image.Resampling.LANCZOS)
        glow = ImageOps.expand(logo, border=20, fill=rand_color)
        glow = glow.filter(ImageFilter.GaussianBlur(15))
        background.paste(glow, (80, 120), glow)
        background.paste(logo, (100, 140), logo)

        # Fonts
        try:
            font_chan = ImageFont.truetype("AloneMusic/assets/font2.ttf", 30)
        except:
            font_chan = ImageFont.load_default()
        try:
            font_small = ImageFont.truetype("AloneMusic/assets/font.ttf", 28)
        except:
            font_small = ImageFont.load_default()
        try:
            font_title = ImageFont.truetype("AloneMusic/assets/font3.ttf", 50)
        except:
            font_title = ImageFont.load_default()

        stitle = truncate(title)
        draw_text_with_outline(draw, (565, 160), stitle[0], font_title, (255, 255, 255))
        if stitle[1]:
            draw_text_with_outline(draw, (565, 220), stitle[1], font_title, (240, 240, 240))

        draw.text((565, 300), f"{channel} | {views[:23]}", font=font_chan, fill=(200, 200, 200))

        # Rounded progress bar
        draw_rounded_bar(draw, (565, 370, 1130, 390), radius=10, fill_bg=(50, 50, 50), fill_fg=rand_color, progress=0.7)

        draw.text((565, 400), "00:00", font=font_chan, fill=(255, 255, 255))
        draw.text((1080, 400), duration[:23], font=font_chan, fill=(255, 255, 255))

        # Music icons
        if icons:
            icons_resized = icons.resize((560, 58), Image.Resampling.LANCZOS)
            background.paste(icons_resized, (565, 460), icons_resized)

        # Small thumbnail
        if youtube:
            small_thumb = youtube.resize((120, 70), Image.Resampling.LANCZOS)
            background.paste(small_thumb, (1080, 30), small_thumb)

        # Speaker icon
        if speaker_icon:
            speaker_icon = speaker_icon.resize((80, 80), Image.Resampling.LANCZOS)
            glow_speaker = ImageOps.expand(speaker_icon, border=10, fill=rand_color).filter(ImageFilter.GaussianBlur(8))
            background.paste(glow_speaker, (1150, 550), glow_speaker)

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        tpath = f"cache/{videoid}.png"
        background.save(tpath)
        return tpath

    except Exception:
        traceback.print_exc()
        return None
