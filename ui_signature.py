"""Modal mouse handwriting pad. Draft strokes stay in memory until saved."""
import tkinter as tk
from tkinter import ttk, messagebox
from signatures import PAD_WIDTH, PAD_HEIGHT, PEN_WIDTH, handwritten_signature
from ui_theme import LINE, WHITE

class SignaturePad:
    def __init__(self,parent,on_save):
        self.on_save=on_save;self.strokes=[];self.active=None;self.point_count=0
        self.window=tk.Toplevel(parent);self.window.title('添加手写签名')
        self.window.transient(parent);self.window.resizable(False,False)
        frame=ttk.Frame(self.window,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='写下你的签名',style='Section.TLabel').pack(anchor='w')
        ttk.Label(frame,text='按住鼠标左键书写，松开后抬笔。保存你实际写下的笔迹。',style='Muted.TLabel').pack(anchor='w',pady=(6,16))
        self.canvas=tk.Canvas(frame,width=PAD_WIDTH,height=PAD_HEIGHT,bg=WHITE,
                              highlightthickness=1,highlightbackground=LINE,bd=0,cursor='pencil')
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>',self.start)
        self.canvas.bind('<B1-Motion>',self.move)
        self.canvas.bind('<ButtonRelease-1>',self.end)
        self.status=tk.StringVar(value='请在空白框内书写')
        ttk.Label(frame,textvariable=self.status,style='Muted.TLabel').pack(anchor='w',pady=(8,8))
        actions=ttk.Frame(frame);actions.pack(fill='x',pady=(4,12))
        self.undo_button=ttk.Button(actions,text='撤销上一笔',command=self.undo);self.undo_button.pack(side='left')
        self.clear_button=ttk.Button(actions,text='清空重写',command=self.clear);self.clear_button.pack(side='left',padx=8)
        self.save_button=ttk.Button(actions,text='保存字迹',style='Primary.TButton',command=self.save);self.save_button.pack(side='right')
        ttk.Button(actions,text='取消',command=self.close).pack(side='right',padx=8)
        ttk.Label(frame,text='字迹仅保存在本机，绑定当前账号。请由本人书写；本工具不认证身份或签署效力。',style='Muted.TLabel',wraplength=PAD_WIDTH).pack(anchor='w')
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.bind('<Escape>',lambda event:self.close())
        self.update_controls();self.window.update_idletasks()
        x=max(0,parent.winfo_rootx()+(parent.winfo_width()-self.window.winfo_reqwidth())//2)
        y=max(0,parent.winfo_rooty()+(parent.winfo_height()-self.window.winfo_reqheight())//2)
        self.window.geometry(f'+{x}+{y}');self.window.grab_set();self.canvas.focus_set()

    def point(self,event):
        x,y=event.x-1,event.y-1
        return (x,y) if 0<=x<=PAD_WIDTH and 0<=y<=PAD_HEIGHT else None

    def start(self,event):
        self.active=None;point=self.point(event)
        if point is None:return
        if len(self.strokes)>=2000 or self.point_count>=50000:
            self.status.set('笔迹过多，请清空后重新书写。');return
        self.active=[point];self.strokes.append(self.active);self.point_count+=1
        x,y=point;r=PEN_WIDTH/2
        self.canvas.create_oval(x+1-r,y+1-r,x+1+r,y+1+r,fill='#121212',outline='#121212',tags='ink')
        self.update_controls()

    def move(self,event):
        point=self.point(event)
        if point is None:self.active=None;return
        if self.active is None:self.start(event);return
        if point==self.active[-1]:return
        if self.point_count>=50000:self.active=None;return
        last=self.active[-1];self.active.append(point);self.point_count+=1
        self.canvas.create_line(last[0]+1,last[1]+1,point[0]+1,point[1]+1,
                                fill='#121212',width=PEN_WIDTH,capstyle=tk.ROUND,joinstyle=tk.ROUND,tags='ink')

    def end(self,event=None):
        if event is not None and self.active is not None:self.move(event)
        self.active=None;self.update_controls()

    def redraw(self):
        self.canvas.delete('ink')
        for stroke in self.strokes:
            if len(stroke)>1:
                self.canvas.create_line(*[v+1 for p in stroke for v in p],fill='#121212',width=PEN_WIDTH,
                                        capstyle=tk.ROUND,joinstyle=tk.ROUND,tags='ink')
            else:
                x,y=stroke[0];r=PEN_WIDTH/2
                self.canvas.create_oval(x+1-r,y+1-r,x+1+r,y+1+r,fill='#121212',outline='#121212',tags='ink')

    def undo(self):
        self.active=None
        if self.strokes:self.point_count-=len(self.strokes.pop())
        self.redraw();self.update_controls()

    def clear(self):
        self.strokes=[];self.active=None;self.point_count=0
        self.canvas.delete('ink');self.update_controls()

    def update_controls(self):
        state='normal' if self.strokes else 'disabled'
        for button in (self.undo_button,self.clear_button,self.save_button):button.configure(state=state)
        self.status.set(f'已写 {len(self.strokes)} 笔 · 保存后可在 PDF 中放置' if self.strokes else '请在空白框内书写')

    def save(self):
        self.end()
        try:
            handwritten_signature(self.strokes)  # Reject an empty pad or accidental click before persistence.
            self.on_save(self.strokes)
        except Exception as e:
            messagebox.showerror('签名未保存',str(e),parent=self.window);return
        self.close()

    def close(self):
        self.window.grab_release();self.window.destroy()
