"""Local signature assets from the user's mouse strokes or own ink image."""
import io, math
from PIL import Image, ImageDraw, ImageOps

PAD_WIDTH, PAD_HEIGHT = 680, 250
PEN_WIDTH = 3

def _png(image):
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()

def handwritten_signature(strokes):
    """Rasterize actual input geometry, with rounded ends and antialiased edges."""
    if not isinstance(strokes,(list,tuple)) or not 1<=len(strokes)<=2000:
        raise ValueError('请先在签名框内书写，再保存字迹。')
    points=[];clean=[]
    for stroke in strokes:
        if not isinstance(stroke,(list,tuple)) or not stroke:
            raise ValueError('手写笔迹无效，请清空后重新书写。')
        line=[]
        for point in stroke:
            if not isinstance(point,(list,tuple)) or len(point)!=2:
                raise ValueError('手写笔迹坐标无效。')
            x,y=point
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (x,y)) or not (0<=x<=PAD_WIDTH and 0<=y<=PAD_HEIGHT):
                raise ValueError('请在签名框内书写。')
            line.append((x,y));points.append((x,y))
            if len(points)>50000:raise ValueError('笔迹过多，请清空后重新书写。')
        clean.append(line)
    xs,ys=zip(*points)
    if max(max(xs)-min(xs),max(ys)-min(ys))<4:
        raise ValueError('未找到完整笔迹，请书写后再保存。')
    scale=3;radius=PEN_WIDTH*scale/2
    image=Image.new('RGBA',((PAD_WIDTH+PEN_WIDTH*2)*scale,(PAD_HEIGHT+PEN_WIDTH*2)*scale))
    draw=ImageDraw.Draw(image);ink=(18,18,18,255)
    for stroke in clean:
        line=[((x+PEN_WIDTH)*scale,(y+PEN_WIDTH)*scale) for x,y in stroke]
        if len(line)>1:draw.line(line,fill=ink,width=PEN_WIDTH*scale,joint='curve')
        for x,y in line:draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=ink)
    image=image.resize((PAD_WIDTH+PEN_WIDTH*2,PAD_HEIGHT+PEN_WIDTH*2),Image.Resampling.LANCZOS)
    bbox=image.getchannel('A').getbbox();ink=image.crop(bbox)
    result=Image.new('RGBA',(ink.width+24,ink.height+24));result.alpha_composite(ink,(12,12))
    return _png(result)

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
