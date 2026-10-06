"""Editable date/text overlays, rendered with the local Windows Song font."""
import io, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def today_parts():
    day=datetime.now(timezone(timedelta(hours=8)))
    return str(day.year),str(day.month),str(day.day)

def today_text():
    y,m,d=today_parts();return f'{y}年{m}月{d}日'

def text_png(text):
    if not isinstance(text,str) or not text.strip() or len(text)>200 or len(text.splitlines())>5:
        raise ValueError('文字应为1至200字、最多5行。')
    if any((ord(c)<32 and c!='\n') or ord(c)>0xffff for c in text):raise ValueError('请使用普通汉字、数字或标点。')
    font=ImageFont.truetype(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simsun.ttc'),80)
    draw=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    box=draw.multiline_textbbox((0,0),text,font=font,spacing=18)
    image=Image.new('RGBA',(box[2]-box[0]+12,box[3]-box[1]+12))
    ImageDraw.Draw(image).multiline_text((6-box[0],6-box[1]),text,font=font,spacing=18,fill=(0,0,0,255))
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()

def text_dimensions(text,font_size):
    size=float(font_size)
    if not 8<=size<=36:raise ValueError('文字字号应为8至36。')
    with Image.open(io.BytesIO(text_png(text))) as im:return im.width*size/80,im.height*size/80

def date_labels(page,page_number):
    if page.rotation:raise ValueError('旋转页请用添加日期文字手动定位。')
    years,months,days=(page.search_for(s) for s in ('年','月','日'))
    triples=[]
    for y in years:
        for m in months:
            for d in days:
                if y.x0<m.x0<d.x0 and abs(y.y0-m.y0)<4 and abs(m.y0-d.y0)<4:
                    triples.append((y,m,d))
    if not triples:raise ValueError('当前页未找到同一行的年、月、日，请添加日期文字后点击定位。')
    boxes=max(triples,key=lambda triple:(triple[0].y0,triple[2].x0))
    result=[]
    for text,box in zip(today_parts(),boxes):
        size=max(8,min(24,box.height/1.4));w,h=text_dimensions(text,size)
        result.append(dict(kind='date',text=text,font_size=size,page=page_number,x=box.x0-w-2,y=box.y0+(box.height-h)/2,width=w,height=h))
    return result
