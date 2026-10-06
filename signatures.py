"""Local signature assets: Kai-style name lettering or the user's own ink image."""
import io, os, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

def _png(image):
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()

def kai_signature(name):
    name=name.strip()
    if not re.fullmatch(r'[\u3400-\u9fffA-Za-z0-9· ]{1,20}',name):
        raise ValueError('签名请填写1至20个汉字、字母或数字。')
    font_path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simkai.ttf'
    if not font_path.exists():raise ValueError('本机未安装Windows楷体，请导入本人签名图片。')
    font=ImageFont.truetype(str(font_path),180)
    box=font.getbbox(name);width=box[2]-box[0];height=box[3]-box[1]
    image=Image.new('RGBA',(width+36,height+36))
    ImageDraw.Draw(image).text((18-box[0],18-box[1]),name,font=font,fill=(18,18,18,255))
    return _png(image)

def import_signature(data):
    if len(data)>10*1024*1024:raise ValueError('签名图片不得超过10MB。')
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ('PNG','JPEG','WEBP','BMP'):raise ValueError('请选择PNG、JPG、WebP或BMP图片。')
            if source.width*source.height>16_000_000:raise ValueError('签名图片不得超过1600万像素。')
            source.load();image=ImageOps.exif_transpose(source).convert('RGBA')
    except (OSError,Image.DecompressionBombError) as e:raise ValueError('无法读取签名图片。') from e
    # Convert actual ink to black; remove near-white paper, retaining stroke geometry.
    rgb=Image.new('RGB',image.size,'white');rgb.paste(image,mask=image.getchannel('A'))
    gray=ImageOps.grayscale(rgb)
    alpha=gray.point(lambda v:0 if v>=235 else round((235-v)*255/235))
    bbox=alpha.getbbox()
    if bbox is None or bbox[2]-bbox[0]<2 or bbox[3]-bbox[1]<2:raise ValueError('图片中未找到清晰签名字迹。')
    ink=Image.new('RGBA',image.size,(18,18,18,0));ink.putalpha(alpha)
    ink=ink.crop(bbox)
    ink.thumbnail((2400,1200),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(ink.width+24,ink.height+24));result.alpha_composite(ink,(12,12))
    return _png(result)
