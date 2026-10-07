"""Windows desktop UI for the local company stamp workflow."""
import copy, io, json, os, sys, tempfile, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pymupdf as fitz
from PIL import Image, ImageTk
from seal_core import SealStore, COMPANY, ADMIN_ID, stamp_png, digest
from local_session import SessionCache
from login_policy import LoginPolicy
from ui_auth import build_auth, legal_reader
from text_layer import today_text, date_labels, text_png, text_dimensions
from ui_theme import apply_theme, artwork, Card, INK, MUTED, PAPER, WHITE, LINE, GREEN
from ui_layout import build_workspace
from release_info import PRODUCT, VERSION

def data_directory():
    base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    return base/'data'

class App:
    def __init__(self,root,store,session_cache=None):
        self.root=root;self.store=store;self.token=None;self.pdf=None;self.source=None;self.selected=None
        self.page=0;self.position=None;self.scale=1;self.photo=None
        self.session_cache=session_cache or SessionCache(store.root/'session.dpapi')
        root.title(PRODUCT+' '+VERSION)
        width=min(1380,root.winfo_screenwidth()-80);height=min(920,root.winfo_screenheight()-100)
        root.geometry(f'{width}x{height}');root.minsize(1020,680)
        apply_theme(root)
        self.window_icon=artwork(root,'site-icon.webp',(64,64));root.iconphoto(True,self.window_icon)
        self._resize_job=None;self.preview_offset=12
        self.login_policy=LoginPolicy(store.root,self.session_cache)
        self.token=self.login_policy.restore(store)
        if self.token:self.show_main()
        else:self.show_login()

    def clear(self):
        if self._resize_job:self.root.after_cancel(self._resize_job);self._resize_job=None
        if self.pdf:self.pdf.close();self.pdf=None
        for child in self.root.winfo_children():child.destroy()

    def show_login(self):
        build_auth(self)

    def legal(self):
        legal_reader(self)

    def show_main(self):
        if not self.store.has_current_consent(self.token):
            build_auth(self,'consent');return
        self.clear();self.source=None;self.selected=None;self.position=None
        self.undo_stack=[];self.edit_checkpoint=None;self.restoring_edit=False
        actor=self.store.actor(self.token)
        self.seal_enabled=tk.BooleanVar(value=bool(self.store.profile().get('seal_asset') or self.store.profile().get('company')));self.sig_enabled=tk.BooleanVar(value=False)
        self.zoom=tk.StringVar(value='适合宽度')
        self.placement=tk.StringVar(value='seal');self.sig_width=tk.StringVar(value='35')
        self.sig_position=None;self.sig_page=None;self.signature_asset=self.store.last_signature(self.token)
        self.signature_png=None
        if self.signature_asset:
            try:self.signature_png=self.store.signature(self.token,self.signature_asset)
            except (ValueError,OSError):self.signature_asset=None
        build_workspace(self,actor)
        self.refresh();self.buttons();self.reset_history()
        self.root.bind('<Control-z>',self.keyboard_undo)

    def update_mode(self):
        if hasattr(self,'mode_text'):
            self.mode_text.set({'seal':'公章定位','signature':'签名定位','text':'文字定位'}[self.placement.get()])

    def tool_tab_changed(self,event):
        index=self.notebook.index(self.notebook.select())
        self.placement.set(('seal','signature','text')[index]);self.update_mode()

    def preview_resize(self,event):
        if self._resize_job:self.root.after_cancel(self._resize_job)
        self._resize_job=self.root.after(100,self.resize_preview)

    def resize_preview(self):
        self._resize_job=None
        if not hasattr(self,'canvas') or not self.canvas.winfo_exists():return
        if self.pdf:self.safe(self.draw)
        else:self.empty_preview()

    def empty_preview(self):
        self.canvas.delete('all')
        w=max(300,self.canvas.winfo_width());h=max(340,self.canvas.winfo_height())
        cx=w/2;cy=max(100,h/2-70)
        self.canvas.create_image(cx,cy,image=self.workspace_decoration)
        self.canvas.create_text(cx,cy+104,text='先选一份 PDF',fill=INK,font=('Microsoft YaHei UI',17,'bold'),anchor='n')
        self.canvas.create_text(cx,cy+144,text='盖章、签名和日期，在同一个工作台完成。',fill=MUTED,font=('Microsoft YaHei UI',9),width=max(240,w-50),anchor='n')
        self.canvas.create_text(cx,cy+178,text='点击左侧「选择 PDF」开始',fill=GREEN,font=('Microsoft YaHei UI',9),anchor='n')
        self.canvas.configure(scrollregion=(0,0,w,h))

    def safe(self,fn):
        try:return fn()
        except Exception as e:messagebox.showerror('操作未完成',str(e),parent=self.root)

    def logout(self):
        self.session_cache.clear();self.store.logout(self.token);self.token=None;self.show_login()

    def settings(self):
        panel=tk.Toplevel(self.root);panel.title('自有印章与导出设置');panel.transient(self.root)
        panel.geometry('480x360');panel.resizable(False,False)
        frame=ttk.Frame(panel,padding=24);frame.pack(fill='both',expand=True)
        profile=self.store.profile();company=tk.StringVar(value=profile.get('company',''))
        folder=tk.StringVar(value=profile.get('export_dir',''));selected=[None]
        ttk.Label(frame,text='自有印章',style='Section.TLabel').pack(anchor='w')
        ttk.Label(frame,text='填写本人 / 企业名称生成图形章，或导入自有印章图片。',wraplength=420,style='Muted.TLabel').pack(anchor='w',pady=8)
        ttk.Entry(frame,textvariable=company).pack(fill='x',pady=5)
        def image():
            path=filedialog.askopenfilename(title='选择本人或本企业印章',filetypes=[('图片','*.png *.jpg *.jpeg *.webp *.bmp')],parent=panel)
            if path:selected[0]=Path(path);image_button.configure(text='已选择自有印章图片')
        image_button=ttk.Button(frame,text='导入自有印章图片',command=image);image_button.pack(fill='x',pady=5)
        ttk.Label(frame,text='默认导出目录',style='Section.TLabel').pack(anchor='w',pady=(14,5))
        ttk.Entry(frame,textvariable=folder).pack(fill='x')
        def directory():
            path=filedialog.askdirectory(title='选择默认导出文件夹',parent=panel)
            if path:folder.set(path)
        ttk.Button(frame,text='选择文件夹…',command=directory).pack(anchor='w',pady=8)
        def save():
            def run():
                kwargs=dict(export_dir=folder.get().strip())
                if selected[0]:
                    if selected[0].stat().st_size>10*1024*1024:raise ValueError('印章图片不得超过10MB。')
                    kwargs.update(image=selected[0].read_bytes(),company=company.get().strip() or None)
                elif company.get().strip() and company.get().strip()!=profile.get('company'):kwargs['company']=company.get().strip()
                self.store.configure_profile(self.token,**kwargs)
                self.update_seal_preview();self.seal_enabled.set(bool(self.store.profile().get('seal_asset') or self.store.profile().get('company')))
                self.redraw_markers();panel.destroy()
            self.safe(run)
        ttk.Button(frame,text='保存设置',style='Primary.TButton',command=save).pack(fill='x',pady=6)

    def update_seal_preview(self):
        profile=self.store.profile();self.seal_name.set(profile.get('company') or '先配置本人或本企业印章')
        try:
            im=Image.open(io.BytesIO(self.store.seal_data()));im.thumbnail((88,88),Image.Resampling.LANCZOS)
            self.stamp_photo=ImageTk.PhotoImage(im,master=self.root);self.stamp_label.configure(image=self.stamp_photo,text='')
        except ValueError:self.stamp_label.configure(image='',text='＋ 自有印章',fg=MUTED)

    def make_signature(self):
        def run():
            if self.selected:raise ValueError('请先选择新PDF。审核时不能替换申请人的签名。')
            name=simpledialog.askstring('楷书签名','填写本人姓名，生成端正楷书字样；使用前请核对预览。',initialvalue=self.store.actor(self.token)['name'],parent=self.root)
            if name is None:return
            self.set_signature(self.store.create_signature(self.token,name=name))
        self.safe(run)

    def import_signature(self):
        def run():
            if self.selected:raise ValueError('请先选择新PDF。审核时不能替换申请人的签名。')
            path=filedialog.askopenfilename(title='导入本人签名图片（白底深色字迹）',filetypes=[('签名图片','*.png *.jpg *.jpeg *.webp *.bmp')],parent=self.root)
            if not path:return
            source=Path(path)
            if source.stat().st_size>10*1024*1024:raise ValueError('签名图片不得超过10MB。')
            self.set_signature(self.store.create_signature(self.token,image=source.read_bytes()))
        self.safe(run)

    def set_signature(self,asset_id):
        self.signature_asset=asset_id;self.signature_png=self.store.signature(self.token,asset_id)
        self.sig_enabled.set(True);self.placement.set('signature');self.sig_position=None;self.sig_page=None
        self.draw();self.track_edits()
        preview=tk.Toplevel(self.root);preview.title('签名预览');preview.transient(self.root)
        im=Image.open(io.BytesIO(self.signature_png));im.thumbnail((460,180),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(im);label=ttk.Label(preview,image=photo,padding=18);label.image=photo;label.pack()
        ttk.Label(preview,text='请核对字样后，在PDF中点选签名位置。',padding=10).pack()
        ttk.Button(preview,text='确认预览',command=preview.destroy).pack(pady=10)

    def redraw_markers(self):self.safe(self.draw)

    def signature_dimensions(self):
        if not self.signature_png:raise ValueError('请先生成或导入本人签名。')
        width=float(self.sig_width.get())*72/25.4
        with Image.open(io.BytesIO(self.signature_png)) as im:height=width*im.height/im.width
        if not 10<=width<=350 or not 4<=height<=160:raise ValueError('请调整签名宽度，使签名完整且大小合适。')
        return width,height

    def resize_signature(self):
        if self.sig_enabled.get():
            self.sig_position=None;self.sig_page=None;self.safe(self.draw)

    def update_text_info(self):
        if self.labels:
            self.active_label=min(self.active_label,len(self.labels)-1)
            label=self.labels[self.active_label];self.text_font.set(str(label['font_size']))
            self.text_info.set(f"{self.active_label+1}/{len(self.labels)}：{label['text'][:12]}")
        else:self.text_info.set('未添加文字')

    def add_text(self):
        def run():
            if not self.pdf or self.selected:raise ValueError('请先选择新PDF，再添加文字。')
            if len(self.labels)>=10:raise ValueError('最多添加10个文本框。')
            text=simpledialog.askstring('添加文字','填写日期或其他文字，添加后可在页面中点选位置。',initialvalue=today_text(),parent=self.root)
            if text is None:return
            size=float(self.text_font.get());w,h=text_dimensions(text,size);rect=self.pdf[self.page].rect
            self.labels.append(dict(text=text,font_size=size,page=self.page,x=24,y=max(0,rect.height-h-35),width=w,height=h))
            self.active_label=len(self.labels)-1;self.placement.set('text');self.update_text_info();self.marker()
        self.safe(run)

    def fill_date(self):
        def run():
            if not self.pdf or self.selected:raise ValueError('请先选择新PDF，再填写日期。')
            found=date_labels(self.pdf[self.page],self.page)
            keep=[v for v in self.labels if not(v.get('kind')=='date' and v['page']==self.page)]
            if len(keep)+len(found)>10:raise ValueError('最多添加10个文本框，请先删除其他文字。')
            self.labels=keep+found;self.active_label=len(keep);self.placement.set('text');self.update_text_info();self.marker()
        self.safe(run)

    def pick_text(self,offset):
        if self.labels:
            self.active_label=(self.active_label+offset)%len(self.labels);self.placement.set('text');self.update_text_info()
            page=self.labels[self.active_label]['page']
            if page!=self.page:self.page=page;self.position=None;self.safe(self.draw)

    def edit_text(self):
        def run():
            if self.selected:raise ValueError('不能改写已提交申请的文字，请选择新PDF。')
            if not self.labels:raise ValueError('请先添加文字。')
            label=self.labels[self.active_label]
            text=simpledialog.askstring('编辑文字','修改当前文本框内容：',initialvalue=label['text'],parent=self.root)
            if text is None:return
            w,h=text_dimensions(text,label['font_size']);label.update(text=text,width=w,height=h)
            self.update_text_info();self.marker()
        self.safe(run)

    def remove_text(self):
        if self.selected:return
        if self.labels:self.labels.pop(self.active_label);self.update_text_info();self.marker()

    def resize_text(self):
        def run():
            if not self.labels:return
            label=self.labels[self.active_label];size=float(self.text_font.get());w,h=text_dimensions(label['text'],size)
            label.update(font_size=size,width=w,height=h);self.marker()
        self.safe(run)

    def add_user(self):
        def run():
            user=simpledialog.askstring('新增申请人','填写未使用的5位数字账号编号',parent=self.root)
            if not user:return
            name=simpledialog.askstring('新增申请人','姓名',parent=self.root)
            if not name:return
            password=simpledialog.askstring('新增申请人','设置密码（至少8位）',show='*',parent=self.root)
            if password is None:return
            self.store.add_user(self.token,user,name,password);messagebox.showinfo('完成','申请人已创建。',parent=self.root)
        self.safe(run)

    def refresh(self):
        self.rows={r['id']:r for r in self.store.list_requests(self.token)}
        self.tree.delete(*self.tree.get_children())
        names={'pending':'待审核','approved':'已盖章','rejected':'已退回','withdrawn':'已撤回','revoked':'已作废'}
        for row in self.rows.values():self.tree.insert('', 'end',iid=row['id'],text=row['filename'],values=(names[row['status']],row['applicant']))
        self.count_text.set(f'{len(self.rows)} 份')
        colors={'pending':MUTED,'approved':GREEN,'rejected':MUTED,'withdrawn':MUTED,'revoked':MUTED}
        for key,color in colors.items():self.tree.tag_configure(key,foreground=color)
        for row in self.rows.values():self.tree.item(row['id'],tags=(row['status'],))

    def buttons(self):
        row=self.rows.get(self.selected);admin=self.store.actor(self.token)['admin']
        self.submit_button.configure(state='normal' if self.source and not self.selected else 'disabled')
        for b in (self.approve_button,self.reject_button):b.configure(state='normal' if admin and row and row['status']=='pending' else 'disabled')
        if admin and row and row['status']=='pending':
            self.submit_button.grid_remove();self.approve_button.grid();self.reject_button.grid()
        else:
            self.submit_button.grid();self.approve_button.grid_remove();self.reject_button.grid_remove()
        for b in (self.export_button,self.save_as_button):b.configure(state='normal' if row and row['status']=='approved' else 'disabled')
        can_withdraw=row and (row['status']=='pending' or (admin and row['status']=='approved'))
        self.withdraw_button.configure(state='normal' if can_withdraw else 'disabled')
        self.undo_button.configure(state='normal' if self.undo_stack and self.editable() else 'disabled')
        for b in (self.kai_button,self.import_button,self.seal_check,self.sig_check,self.date_button,self.text_button,self.edit_text_button,self.remove_text_button):b.configure(state='disabled' if row else 'normal')
        can_position=bool(self.pdf and self.editable())
        for widget in (self.bottom_right_button,self.seal_size_input,self.signature_size_input,self.text_size_input):
            widget.configure(state='normal' if can_position else 'disabled')
        if row and not self.seal_enabled.get():self.bottom_right_button.configure(state='disabled')
        if not self.pdf:hint='先选择 PDF，再设置盖章位置。'
        elif row and row['status']=='approved':hint='已通过：位置已固定。重新盖章请先选择 PDF。'
        elif row and row['status']=='pending':hint='待审核：可调整位置，确认后审核。' if admin else '待审核：管理员审核期间不能改动。'
        elif row:hint='记录只读：请修改原件后重新选择 PDF。'
        else:hint='编辑中：选择工具，再点击 PDF 放置。'
        self.editor_hint.set(hint)


    def load(self,data,params=None):
        if self.pdf:self.pdf.close()
        self.pdf=fitz.open(stream=data,filetype='pdf')
        if self.pdf.is_encrypted:raise ValueError('请选择未加密PDF。')
        self.page=int(params['page']) if params else len(self.pdf)-1
        self.position=(float(params['x']),float(params['y'])) if params else None
        if params:self.size.set(str(round(float(params['size'])*25.4/72,1)))
        self.seal_enabled.set(params.get('seal_enabled',True) if params else bool(self.store.profile().get('seal_asset') or self.store.profile().get('company')))
        sig=params.get('signature') if params else None
        self.sig_enabled.set(bool(sig))
        self.signature_asset=sig['asset_id'] if sig else self.store.last_signature(self.token)
        self.signature_png=None
        if self.signature_asset:
            try:self.signature_png=self.store.signature(self.token,self.signature_asset,self.selected if sig else None)
            except (ValueError,OSError):
                if sig:raise
                self.signature_asset=None
        self.sig_position=(sig['x'],sig['y']) if sig else None;self.sig_page=sig['page'] if sig else None
        if sig:self.sig_width.set(str(sig['width']*25.4/72))
        self.labels=[dict(v) for v in params.get('labels',[])] if params else []
        self.active_label=0;self.update_text_info()
        self.draw();self.reset_history()

    def editable(self):
        row=self.rows.get(self.selected)
        return not row or (row['status']=='pending' and self.store.actor(self.token)['admin'])

    def draft_state(self):
        return copy.deepcopy(dict(page=self.page,position=self.position,size=self.size.get(),
            seal=self.seal_enabled.get(),signature=self.sig_enabled.get(),asset=self.signature_asset,
            sig_position=self.sig_position,sig_page=self.sig_page,sig_width=self.sig_width.get(),
            labels=self.labels,active_label=self.active_label,font=self.text_font.get()))

    def reset_history(self):
        self.undo_stack=[];self.edit_checkpoint=self.draft_state();self.buttons()

    def track_edits(self):
        if self.restoring_edit or not self.editable():return
        current=self.draft_state()
        if self.edit_checkpoint is not None and current!=self.edit_checkpoint:
            self.undo_stack.append(self.edit_checkpoint)
            self.undo_stack=self.undo_stack[-50:]
        self.edit_checkpoint=current;self.buttons()

    def keyboard_undo(self,event):
        if isinstance(event.widget,(tk.Entry,tk.Text,ttk.Entry,ttk.Spinbox)):return
        self.undo();return 'break'

    def undo(self):
        def run():
            if not self.undo_stack or not self.editable():return
            state=self.undo_stack[-1]
            png=self.store.signature(self.token,state['asset'],self.selected) if state['asset'] else None
            self.undo_stack.pop();self.restoring_edit=True
            try:
                self.page=state['page'];self.position=state['position'];self.size.set(state['size'])
                self.seal_enabled.set(state['seal']);self.sig_enabled.set(state['signature'])
                self.signature_asset=state['asset'];self.signature_png=png
                self.sig_position=state['sig_position'];self.sig_page=state['sig_page'];self.sig_width.set(state['sig_width'])
                self.labels=copy.deepcopy(state['labels']);self.active_label=state['active_label'];self.text_font.set(state['font'])
                self.update_text_info();self.draw()
            finally:self.restoring_edit=False
            self.edit_checkpoint=self.draft_state();self.buttons()
        self.safe(run)

    def choose(self):
        path=filedialog.askopenfilename(title='选择待盖章PDF',filetypes=[('PDF','*.pdf')],parent=self.root)
        if not path:return
        def run():
            self.selected=None;self.source=Path(path)
            data=self.source.read_bytes();self.source_hash=digest(data)
            self.load(data);self.detail.set(f'新申请：{self.source.name}');self.buttons()
            self.document_title.set(self.source.name);self.document_state.set('编辑中')
            self.export_info.set('点击右侧工具，在 PDF 中定位；确认后生成副本。')
        self.safe(run)

    def select_request(self,event):
        selection=self.tree.selection()
        if not selection:return
        def run():
            self.selected=selection[0];self.source=None
            row=self.rows[self.selected]
            data=self.store.output(self.token,self.selected).read_bytes() if row['status']=='approved' else self.store.original(self.token,self.selected)
            self.load(data,json.loads(row['params']))
            when=time.strftime('%Y-%m-%d %H:%M',time.localtime(row['created']))
            self.detail.set(f"申请人：{row['applicant']}\n申请编号：{row['id'][:12]}\n申请时间：{when}\n文件：{row['filename']}\n{row['reason']}")
            self.buttons()
            self.document_title.set(row['filename'])
            self.document_state.set({'pending':'待审核','approved':'已通过','rejected':'已退回','withdrawn':'已撤回','revoked':'已作废'}[row['status']])
        self.safe(run)

    def diameter(self):
        size=float(self.size.get())*72/25.4
        if not 40<=size<=180:raise ValueError('章直径请填写15至63毫米。')
        return size

    def draw(self):
        if not self.pdf:return
        page=self.pdf[self.page];available=max(300,self.canvas.winfo_width())
        fit_scale=(available-40)/page.rect.width
        chosen=self.zoom.get()
        self.scale=min(1.4,fit_scale) if chosen=='适合宽度' else float(chosen.rstrip('%'))/100
        pix=page.get_pixmap(matrix=fitz.Matrix(self.scale,self.scale),alpha=False)
        self.photo=ImageTk.PhotoImage(Image.frombytes('RGB',(pix.width,pix.height),pix.samples))
        self.preview_offset=max(16,(available-pix.width)/2)
        self.canvas.delete('all')
        self.canvas.create_rectangle(self.preview_offset+5,21,self.preview_offset+pix.width+5,pix.height+21,fill=LINE,outline='')
        self.canvas.create_image(self.preview_offset,16,image=self.photo,anchor='nw')
        self.canvas.configure(scrollregion=(0,0,max(available,pix.width+32),pix.height+36))
        self.file_title_label.configure(wraplength=max(240,available-20))
        self.page_text.set(f'第 {self.page+1} / {len(self.pdf)} 页')
        if self.position is None:self.position=(max(0,page.rect.width-self.diameter()-24),max(0,page.rect.height-self.diameter()-24))
        if self.sig_enabled.get() and self.sig_position is None:
            w,h=self.signature_dimensions();self.sig_position=(24,max(0,page.rect.height-h-28));self.sig_page=self.page
        self.marker()

    def marker(self):
        self.track_edits()
        self.canvas.delete('seal')
        if self.position is None:return
        if self.selected and self.rows[self.selected]['status']!='pending':return
        if self.seal_enabled.get():
            x,y=self.position;s=self.diameter();pixels=max(1,round(s*self.scale))
            asset=json.loads(self.rows[self.selected]['params']).get('seal_asset') if self.selected else None
            preview=Image.open(io.BytesIO(self.store.seal_data(asset))).resize((pixels,pixels),Image.Resampling.LANCZOS)
            self.seal_photo=ImageTk.PhotoImage(preview)
            self.canvas.create_image(self.preview_offset+x*self.scale,16+y*self.scale,image=self.seal_photo,anchor='nw',tags='seal')
        if self.sig_enabled.get() and self.sig_position is not None and self.sig_page==self.page:
            x,y=self.sig_position;w,h=self.signature_dimensions()
            preview=Image.open(io.BytesIO(self.signature_png)).resize((max(1,round(w*self.scale)),max(1,round(h*self.scale))),Image.Resampling.LANCZOS)
            self.signature_photo=ImageTk.PhotoImage(preview)
            self.canvas.create_image(self.preview_offset+x*self.scale,16+y*self.scale,image=self.signature_photo,anchor='nw',tags='seal')
        self.label_photos=[]
        for label in self.labels:
            if label['page']!=self.page:continue
            w,h=text_dimensions(label['text'],label['font_size'])
            preview=Image.open(io.BytesIO(text_png(label['text']))).resize((max(1,round(w*self.scale)),max(1,round(h*self.scale))),Image.Resampling.LANCZOS)
            photo=ImageTk.PhotoImage(preview);self.label_photos.append(photo)
            self.canvas.create_image(self.preview_offset+label['x']*self.scale,16+label['y']*self.scale,image=photo,anchor='nw',tags='seal')

    def place(self,event):
        if not self.pdf or not self.editable():return
        def run():
            if self.placement.get()=='text':
                if not self.labels:raise ValueError('请先添加日期或文字。')
                label=self.labels[self.active_label];w,h=text_dimensions(label['text'],label['font_size']);rect=self.pdf[self.page].rect
                if w>rect.width or h>rect.height:raise ValueError('文本框大于页面，请减小字号。')
                x=(self.canvas.canvasx(event.x)-self.preview_offset)/self.scale-w/2;y=(self.canvas.canvasy(event.y)-16)/self.scale-h/2
                label.update(page=self.page,x=min(max(0,x),rect.width-w),y=min(max(0,y),rect.height-h));self.marker();return
            if self.placement.get()=='signature':
                if not self.sig_enabled.get():raise ValueError('请先勾选添加签名。')
                w,h=self.signature_dimensions();page=self.pdf[self.page]
                if w>page.rect.width or h>page.rect.height:raise ValueError('签名大于页面，请减小宽度。')
                x=(self.canvas.canvasx(event.x)-self.preview_offset)/self.scale-w/2;y=(self.canvas.canvasy(event.y)-16)/self.scale-h/2
                self.sig_position=(min(max(0,x),page.rect.width-w),min(max(0,y),page.rect.height-h));self.sig_page=self.page;self.marker();return
            s=self.diameter();page=self.pdf[self.page]
            x=(self.canvas.canvasx(event.x)-self.preview_offset)/self.scale-s/2
            y=(self.canvas.canvasy(event.y)-16)/self.scale-s/2
            self.position=(min(max(0,x),page.rect.width-s),min(max(0,y),page.rect.height-s));self.marker()
        self.safe(run)

    def bottom_right(self):
        def run():
            if not self.pdf:raise ValueError('请先选择一份 PDF。')
            if not self.editable():raise ValueError('该申请的位置已固定，重新盖章请先选择 PDF。')
            if self.selected and not self.seal_enabled.get():raise ValueError('该申请未包含印章，审核时不能新增印章。')
            asset=json.loads(self.rows[self.selected]['params']).get('seal_asset') if self.selected else None
            self.store.seal_data(asset)
            self.seal_enabled.set(True);self.placement.set('seal');self.update_mode()
            page=self.pdf[self.page];size=self.diameter()
            self.position=(max(0,page.rect.width-size-24),max(0,page.rect.height-size-24))
            self.draw();self.canvas.yview_moveto(1);self.canvas.xview_moveto(1)
            self.export_info.set(f'印章已定位到第 {self.page+1} 页右下角，请核对预览。')
        self.safe(run)

    def resize_stamp(self):
        if self.pdf:self.position=None;self.safe(self.draw)

    def turn(self,offset):
        if self.pdf and 0<=self.page+offset<len(self.pdf):self.page+=offset;self.position=None;self.safe(self.draw)

    def params(self):
        if not self.pdf or self.position is None:raise ValueError('请先选择文件及盖章位置。')
        params=dict(page=self.page,x=self.position[0],y=self.position[1],size=self.diameter(),seal_enabled=self.seal_enabled.get())
        if self.sig_enabled.get():
            w,h=self.signature_dimensions()
            if self.sig_position is None:raise ValueError('请点击放置签名。')
            params['signature']=dict(asset_id=self.signature_asset,page=self.sig_page,x=self.sig_position[0],y=self.sig_position[1],width=w,height=h)
        params['labels']=[dict(v) for v in self.labels]
        return params

    def submit(self):
        def run():
            if not self.source or self.selected:return
            actor=self.store.actor(self.token)
            msg=('请确认：您有权处理本文件并使用其中的印章、签名；已核对各页内容、日期与位置。\n\n'
                 '这是图片叠加，不提供可靠电子签名认证或可信时间戳；请核实接收方的签署要求。\n\n'
                 + ('管理员本人提交会自动通过，没有第二人复核。确认生成副本？' if actor['admin'] else '确认提交给管理员审核？'))
            if not messagebox.askyesno('提交申请',msg,parent=self.root):return
            request_id=self.store.submit(self.token,self.source,self.params(),expected_hash=self.source_hash)
            self.refresh();self.tree.selection_set(request_id);self.tree.focus(request_id);self.select_request(None)
            messagebox.showinfo('完成','已通过并生成盖章副本。' if actor['admin'] else '申请已提交，等待管理员审核。',parent=self.root)
        self.safe(run)

    def approve(self):
        def run():
            if not self.selected:return
            if not messagebox.askyesno('审核确认','确认已核查申请人的真实授权、文件各页内容、印章、签名、日期及位置，并符合接收方要求，予以通过？',parent=self.root):return
            self.store.reposition(self.token,self.selected,self.params());self.store.approve(self.token,self.selected)
            rid=self.selected;self.refresh();self.tree.selection_set(rid);self.select_request(None)
            messagebox.showinfo('完成','已审核通过，可导出盖章PDF。',parent=self.root)
        self.safe(run)

    def reject(self):
        def run():
            if not self.selected:return
            reason=simpledialog.askstring('退回申请','退回理由',parent=self.root)
            if reason is None:return
            self.store.reject(self.token,self.selected,reason);self.refresh();self.buttons()
        self.safe(run)

    def export(self):
        def run():
            if not self.selected:raise ValueError('请先在左侧选择已通过的申请。')
            target=self.store.export_copy(self.token,self.selected)
            self.export_info.set(f'已导出：{target}')
            messagebox.showinfo('导出成功',f'副本已保存，文件校验通过：\n{target}',parent=self.root)
        self.safe(run)

    def export_as(self):
        def run():
            if not self.selected:raise ValueError('请先在左侧选择已通过的申请。')
            self.store.output(self.token,self.selected)
            name=Path(self.rows[self.selected]['filename']).stem+'_已盖章.pdf'
            row=self.rows[self.selected]
            initialdir=self.store.profile().get('export_dir') or (str(Path(row['source_path']).parent) if row['source_path'] else str(self.store.root.parent))
            target=filedialog.asksaveasfilename(title='导出副本（请使用新文件名）',initialdir=initialdir,initialfile=name,defaultextension='.pdf',filetypes=[('PDF','*.pdf')],parent=self.root)
            if target:
                saved=self.store.export(self.token,self.selected,target)
                self.export_info.set(f'已导出：{saved}')
                messagebox.showinfo('导出成功',f'副本已保存，文件校验通过：\n{saved}',parent=self.root)
            else:self.export_info.set('已取消另存为，没有导出文件。')
        self.safe(run)

    def withdraw(self):
        def run():
            if not self.selected:raise ValueError('请先选择申请。')
            row=self.store.request(self.token,self.selected)
            action='作废' if row['status']=='approved' else '撤回'
            reason=simpledialog.askstring(action+'申请','填写理由：',parent=self.root)
            if reason is None:return
            notice='作废后本工具禁止再次导出，原件和审核记录保留。已导出的副本仍需由你通知接收方停用。' if action=='作废' else '撤回后管理员不能继续审核，记录保留。'
            if not messagebox.askyesno(action+'确认',notice,parent=self.root):return
            rid=self.selected;self.store.withdraw(self.token,rid,reason)
            self.refresh();self.tree.selection_set(rid);self.select_request(None)
            self.export_info.set('申请已'+action+'。')
        self.safe(run)

def smoke_test(target):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix='seal-smoke-') as root:
        store=SealStore(Path(root)/'data');store.setup_admin('Synthetic-Test-Only-2026')
        token=store.login(ADMIN_ID,'Synthetic-Test-Only-2026')
        store.configure_profile(token,company='合成测试专用章')
        store.accept_legal(token,True)
        (Path(root)/'local-defaults.json').write_text(json.dumps({'windows_session_login':True}),encoding='utf-8')
        doc=fitz.open();page=doc.new_page();page.insert_text((50,60),'SYNTHETIC TEST DOCUMENT - NO BUSINESS EFFECT')
        source=Path(root)/'synthetic.pdf';doc.save(source);doc.close()
        rid=store.submit(token,source,dict(page=0,x=420,y=680,size=110))
        output=store.output(token,rid)
        with fitz.open(output) as out:assert len(out[0].get_images())==1
        gui=tk.Tk();gui.withdraw()
        app=App(gui,store);app.token=token;app.show_main()
        app.selected=rid;app.load(output.read_bytes(),dict(page=0,x=420,y=680,size=110));app.buttons()
        asset=store.create_signature(token,name='合成测试')
        sig=dict(asset_id=asset,page=0,x=80,y=680,width=140,height=45)
        label=dict(text='2026年10月6日',font_size=12,page=0,x=80,y=740)
        rid2=store.submit(token,source,dict(page=0,x=420,y=680,size=110,signature=sig,labels=[label]))
        app.refresh();app.selected=rid2;app.load(store.output(token,rid2).read_bytes(),json.loads(store.request(token,rid2)['params']));app.buttons()
        assert app.sig_enabled.get() and app.signature_asset==asset and app.labels[0]['text']==label['text']
        with patch.object(messagebox,'showinfo') as info,patch.object(messagebox,'showerror') as error:
            app.export();assert info.called and not error.called
        copies=list(Path(root).glob('*_已处理副本_*.pdf'))
        assert len(copies)==1 and digest(copies[0].read_bytes())==store.request(token,rid2)['output_hash']
        app.selected=None;app.source=source;app.load(source.read_bytes())
        before=app.position;app.position=(40,50);app.marker();app.undo();assert app.position==before
        app.labels=[label];app.marker();app.undo();assert not app.labels
        store.withdraw(token,rid2,'合成测试作废')
        try:store.export_copy(token,rid2)
        except ValueError:pass
        else:raise AssertionError('Revoked request exported')
        remembered=app.session_cache.remember(store,token)
        if not remembered:raise AssertionError('Windows session APIs unavailable')
        gui.update();app.clear();gui.destroy()
        gui2=tk.Tk();gui2.withdraw();app2=App(gui2,SealStore(Path(root)/'data'))
        assert app2.token is None
        assert app2.auth_button.cget('text')=='登录工作台'
        assert app2.user.get()=='00001'
        app2.password.set('Synthetic-Test-Only-2026');app2.auth_submit()
        assert app2.token and app2.store.actor(app2.token)['id']==ADMIN_ID
        from release_info import license_documents
        notices=license_documents()
        assert 'GNU AFFERO GENERAL PUBLIC LICENSE' in notices['license'][1]
        assert 'Pillow-LICENSE' in notices['third-party'][1]
        app2.logout();assert app2.token is None
        gui2.update();app2.clear();gui2.destroy()
        Path(target).write_text(json.dumps({'status':'passed','pdfStamp':True,'tkRuntime':True,'guiWidgets':True,'stampedPreview':True,'signatureOverlay':True,'textOverlay':True,'oldSessionIgnored':True,'passwordLoginOnReopen':True,'offlineLicenses':True,'logoutRevokes':True,'actualUIExport':True,'editUndo':True,'revokedExportBlocked':True,'syntheticOnly':True}),encoding='utf-8')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        try:smoke_test(sys.argv[2])
        except Exception as e:
            Path(sys.argv[2]).write_text(json.dumps({'status':'failed','error':str(e),'syntheticOnly':True}),encoding='utf-8')
            sys.exit(1)
    else:
        root=tk.Tk()
        try:App(root,SealStore(data_directory()));root.mainloop()
        except Exception as e:messagebox.showerror('启动未完成',str(e));root.destroy()
