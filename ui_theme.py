"""Desktop styling with approved brand artwork and a generated decoration."""
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

PAPER='#f5f6f4'
WHITE='#ffffff'
INK='#263c33'
MUTED='#718078'
LINE='#e3e8e2'
GREEN='#315d48'
SAGE='#edf3ed'
BLUE=SAGE
LILAC=SAGE
GOLD=SAGE
FONT=('Microsoft YaHei UI',9)

def asset_root():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'

def artwork(master,name,size,circle=False):
    path=asset_root()/name
    if not path.exists():
        # Public source bundles omit proprietary brand artwork.
        im=Image.new('RGBA',size);draw=ImageDraw.Draw(im)
        draw.ellipse((1,1,size[0]-2,size[1]-2),fill=SAGE)
        draw.text((size[0]/2,size[1]/2),'PDF' if 'mascot' in name else 'OPC',fill=GREEN,anchor='mm')
        return ImageTk.PhotoImage(im,master=master)
    with Image.open(path) as im:
        im=im.convert('RGBA');im.thumbnail(size,Image.Resampling.LANCZOS)
        if circle:
            mask=Image.new('L',im.size,0);ImageDraw.Draw(mask).ellipse((0,0,im.width-1,im.height-1),fill=255)
            im.putalpha(mask)
        return ImageTk.PhotoImage(im,master=master)

def apply_theme(root):
    root.configure(bg=PAPER)
    root.option_add('*Font',FONT)
    root.option_add('*Background',WHITE)
    root.option_add('*Foreground',INK)
    root.option_add('*Entry.Background',WHITE)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=FONT,background=WHITE,foreground=INK)
    style.configure('TFrame',background=WHITE)
    style.configure('Paper.TFrame',background=PAPER)
    style.configure('TLabel',background=WHITE,foreground=INK)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Paper.TLabel',background=PAPER,foreground=MUTED)
    style.configure('Title.TLabel',font=('Microsoft YaHei UI',15,'bold'))
    style.configure('Section.TLabel',font=('Microsoft YaHei UI',10,'bold'))
    style.configure('TCheckbutton',background=WHITE,padding=(0,3),focuscolor=WHITE)
    style.map('TCheckbutton',background=[('active',WHITE)],foreground=[('disabled','#a9aea6')])
    style.configure('TRadiobutton',background=WHITE,padding=(0,3),focuscolor=WHITE)
    style.map('TRadiobutton',background=[('active',WHITE)],foreground=[('disabled','#a9aea6')])
    style.configure('TEntry',fieldbackground=WHITE,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,padding=8)
    style.configure('TSpinbox',fieldbackground=WHITE,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,padding=6,arrowsize=12)
    style.configure('Treeview',background=WHITE,fieldbackground=WHITE,foreground=INK,
                    rowheight=42,borderwidth=0,relief='flat',font=FONT)
    style.map('Treeview',background=[('selected',SAGE)],foreground=[('selected',GREEN)])
    style.configure('Treeview.Heading',font=('Microsoft YaHei UI',8,'bold'),background=WHITE,
                    foreground=MUTED,borderwidth=0,relief='flat',padding=(8,10))
    style.map('Treeview.Heading',background=[('active',WHITE)])
    style.configure('Vertical.TScrollbar',background=LINE,troughcolor=WHITE,borderwidth=0,
                    arrowcolor=MUTED,arrowsize=10)
    for orientation in ('Vertical','Horizontal'):
        style.layout(orientation+'.TScrollbar',[(orientation+'.Scrollbar.trough',{
            'sticky':'nswe','children':[(orientation+'.Scrollbar.thumb',{'sticky':'nswe','expand':1})]})])
        style.configure(orientation+'.TScrollbar',background=LINE,troughcolor=WHITE,
                        bordercolor=WHITE,lightcolor=LINE,darkcolor=LINE,borderwidth=0,width=8)
        style.map(orientation+'.TScrollbar',background=[('active','#c7d2c7')])
    style.configure('TCombobox',fieldbackground=WHITE,background=WHITE,bordercolor=LINE,
                    lightcolor=WHITE,darkcolor=WHITE,arrowcolor=MUTED,padding=5)
    style.map('TCombobox',fieldbackground=[('readonly',WHITE)],foreground=[('readonly',INK)])
    style.configure('TNotebook',background=WHITE,borderwidth=0,tabmargins=(0,0,0,12))
    style.layout('TNotebook',[('Notebook.client',{'sticky':'nswe'})])
    style.configure('TNotebook',bordercolor=WHITE,lightcolor=WHITE,darkcolor=WHITE)
    style.configure('TNotebook.Tab',padding=(8,6),background=PAPER,foreground=MUTED,borderwidth=0,
                    bordercolor=WHITE,lightcolor=WHITE,darkcolor=WHITE)
    style.map('TNotebook.Tab',background=[('selected',SAGE),('active',BLUE)],foreground=[('selected',GREEN)])
    # Opaque corner pixels blend with the white parent; no square color underneath.
    root._control_images=[]
    for name,fill,hover,fg,edge in (
        ('TButton',WHITE,PAPER,INK,LINE),
        ('Primary.TButton',GREEN,'#264b39',WHITE,GREEN),
        ('Gold.TButton',SAGE,'#e0eadf',GREEN,SAGE),
        ('Blue.TButton',SAGE,'#e0eadf',GREEN,SAGE),
        ('Quiet.TButton',PAPER,'#e9ede8',MUTED,PAPER),
        ('Danger.TButton',PAPER,'#f0e8e4','#95624e',LINE),
        ('AuthTab.TButton',WHITE,PAPER,MUTED,WHITE),
        ('SelectedAuthTab.TButton',SAGE,'#e0eadf',GREEN,SAGE),
    ):
        photos=[]
        for color,outline in ((fill,edge),(hover,hover),(hover,hover),('#f0f2ee','#f0f2ee'),(fill,edge)):
            im=Image.new('RGB',(192,120),WHITE)
            ImageDraw.Draw(im).rounded_rectangle((1,1,190,118),radius=24,fill=color,outline=outline,width=3)
            photos.append(ImageTk.PhotoImage(im.resize((64,40),Image.Resampling.LANCZOS),master=root))
        root._control_images.extend(photos)
        element=name.replace('.','_')+'Surface24'
        style.element_create(element,'image',photos[0],('disabled',photos[3]),('pressed',photos[2]),
                             ('active',photos[1]),('focus',photos[4]),border=(12,12),sticky='nsew')
        style.layout(name,[(element,{'sticky':'nsew','children':[('Button.padding',{
            'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
        style.configure(name,foreground=fg,background=WHITE,padding=(14,8),anchor='center',font=FONT)
        style.map(name,foreground=[('disabled','#a3afa5')])
    check_images=[]
    for selected,disabled in ((False,False),(True,False),(False,True),(True,True)):
        im=Image.new('RGB',(60,60),WHITE);draw=ImageDraw.Draw(im)
        fill=('#e4e9e2' if disabled else GREEN) if selected else WHITE
        draw.rounded_rectangle((5,5,49,49),radius=10,fill=fill,outline=LINE if disabled or not selected else GREEN,width=3)
        if selected:draw.line([(15,27),(24,36),(40,18)],fill=MUTED if disabled else WHITE,width=6,joint='curve')
        check_images.append(ImageTk.PhotoImage(im.resize((20,20),Image.Resampling.LANCZOS),master=root))
    root._control_images.extend(check_images)
    style.element_create('OPC.Check.indicator','image',check_images[0],('disabled','selected',check_images[3]),
                         ('disabled',check_images[2]),('selected',check_images[1]),width=24,sticky='w')
    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nsew','children':[
        ('OPC.Check.indicator',{'side':'left','sticky':'w'}),('Checkbutton.label',{'side':'left','sticky':'w'})]})])
    style.layout('Link.TButton',[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})])
    style.configure('Link.TButton',foreground=GREEN,background=WHITE,padding=(0,6),font=FONT)
    style.map('Link.TButton',foreground=[('active','#34756b')])
    return style

class Card(tk.Frame):
    """A rounded card with normal Tk widgets and geometry management inside."""
    def __init__(self,parent,fill=WHITE,padding=16,**kwargs):
        super().__init__(parent,bg=PAPER,**kwargs)
        self.back=tk.Canvas(self,bg=PAPER,highlightthickness=0,bd=0)
        self.back.place(x=0,y=0,relwidth=1,relheight=1)
        self.content=tk.Frame(self,bg=fill)
        self.content.pack(fill='both',expand=True,padx=padding,pady=padding)
        self.fill=fill
        self.bind('<Configure>',self._paint)

    def _paint(self,event):
        w,h=event.width-2,event.height-2;r=min(22,w/3,h/3)
        self.back.delete('all')
        self.back.create_polygon(1+r,1,w-r,1,w,1,w,1+r,w,h-r,w,h,w-r,h,1+r,h,1,h,
                                 1,h-r,1,1+r,1,1,fill=self.fill,outline=LINE,smooth=True)
