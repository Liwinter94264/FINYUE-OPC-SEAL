"""Two-column local authentication and offline legal reader."""
import tkinter as tk
from tkinter import ttk, messagebox
from legal_text import DOCUMENTS, LEGAL_VERSION, REGISTRATION_RULES
from release_info import PRODUCT, VERSION, license_documents
from seal_core import ADMIN_ID
from ui_theme import Card, artwork, PAPER, WHITE, INK, MUTED, GREEN, SAGE, LINE

def legal_reader(app, key='service'):
    window=tk.Toplevel(app.root);window.title('使用规则 · '+LEGAL_VERSION)
    window.geometry('760x630');window.minsize(540,400);window.transient(app.root)
    frame=ttk.Frame(window,padding=22);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='使用前，把规则看清楚',style='Title.TLabel').pack(anchor='w',pady=(0,12))
    notebook=ttk.Notebook(frame);notebook.pack(fill='both',expand=True)
    selected=None
    for name,(title,body) in {**DOCUMENTS, **license_documents()}.items():
        page=ttk.Frame(notebook);notebook.add(page,text=title)
        text=tk.Text(page,wrap='word',bg=WHITE,fg=INK,relief='flat',padx=18,pady=16,
                     font=('Microsoft YaHei UI',10),spacing1=3,spacing3=7)
        scrollbar=ttk.Scrollbar(page,command=text.yview);scrollbar.pack(side='right',fill='y')
        text.configure(yscrollcommand=scrollbar.set);text.pack(fill='both',expand=True)
        text.insert('1.0',body);text.configure(state='disabled')
        if name==key:selected=page
    if selected:notebook.select(selected)
    ttk.Button(frame,text='返回',style='Primary.TButton',command=window.destroy).pack(anchor='e',pady=(14,0))

def legal_links(app,parent):
    row=ttk.Frame(parent);row.pack(fill='x',pady=(3,6))
    ttk.Button(row,text='服务协议 ↗',style='Link.TButton',command=lambda:legal_reader(app,'service')).pack(side='left')
    ttk.Button(row,text='免责声明 ↗',style='Link.TButton',command=lambda:legal_reader(app,'disclaimer')).pack(side='left',padx=12)

def build_auth(app,mode=None):
    app.clear();app.root.unbind('<Control-z>')
    first=not app.store.initialized()
    mode=mode or ('register' if first else 'login')
    register=mode=='register';consent=mode=='consent'
    app.auth_mode=mode
    # One bounded card gives every page the same header, columns and outer margin.
    outer=ttk.Frame(app.root,style='Paper.TFrame');outer.pack(fill='both',expand=True,padx=24,pady=24)
    shell=Card(outer,padding=28);shell.place(relx=.5,rely=.5,anchor='center')
    app.auth_shell=shell
    content=shell.content
    header=ttk.Frame(content);header.pack(fill='x',pady=(0,20))
    app.login_mascot=artwork(app.root,'mascot.webp',(44,44),circle=True)
    ttk.Label(header,image=app.login_mascot).pack(side='left',padx=(0,12))
    brand=ttk.Frame(header);brand.pack(side='left')
    ttk.Label(brand,text=PRODUCT,font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
    ttk.Label(brand,text='本机 PDF 工作台  /  '+VERSION,style='Muted.TLabel').pack(anchor='w',pady=(3,0))
    ttk.Label(header,text='文件在本机处理',style='Muted.TLabel').pack(side='right')
    tk.Frame(content,bg=LINE,height=1).pack(fill='x',pady=(0,20))
    body=ttk.Frame(content);body.pack(fill='both',expand=True)
    body.columnconfigure(0,weight=1,uniform='auth');body.columnconfigure(2,weight=1,uniform='auth')
    body.rowconfigure(0,weight=1)
    visual=ttk.Frame(body);visual.grid(row=0,column=0,sticky='nsew')
    tk.Frame(body,bg=LINE,width=1).grid(row=0,column=1,sticky='ns',padx=24)
    ttk.Label(visual,text='把文件处理好，\n再放心交出去。',font=('Microsoft YaHei UI',17,'bold'),justify='left').pack(anchor='w',pady=(0,6))
    ttk.Label(visual,text='盖章 · 签名 · 日期 · 审核',style='Muted.TLabel').pack(anchor='w')
    app.auth_decoration=artwork(app.root,'auth-decoration-v1.png',(300,176))
    ttk.Label(visual,image=app.auth_decoration).pack(pady=(14,14),anchor='w')
    ttk.Label(visual,text='本机账号与审核规则',style='Section.TLabel').pack(anchor='w',pady=(0,10))
    rules=ttk.Frame(visual);rules.pack(fill='x')
    rules.columnconfigure(1,weight=1)
    app.auth_rule_numbers=[];app.auth_rule_texts=[]
    for index,rule in enumerate(REGISTRATION_RULES[:3]):
        number=ttk.Label(rules,text=f'{index+1:02}',foreground=GREEN,font=('Arial',10,'bold'))
        number.grid(row=index,column=0,sticky='nw',padx=(0,12),pady=(0,10))
        text=ttk.Label(rules,text=rule,wraplength=300,justify='left',style='Muted.TLabel')
        text.grid(row=index,column=1,sticky='nw',pady=(0,10))
        app.auth_rule_numbers.append(number);app.auth_rule_texts.append(text)
    def wrap_rules(event):
        available=max(160,event.width-34)
        for label in app.auth_rule_texts:label.configure(wraplength=available)
    rules.bind('<Configure>',wrap_rules)
    form=ttk.Frame(body);form.grid(row=0,column=2,sticky='new')
    app.auth_form=form
    if not consent:
        tabs=ttk.Frame(form);tabs.pack(fill='x',pady=(0,16))
        tabs.columnconfigure(0,weight=1,uniform='tabs');tabs.columnconfigure(1,weight=1,uniform='tabs')
        for column,(label,tab) in enumerate((('登录','login'),('注册','register'))):
            ttk.Button(tabs,text=label,style='SelectedAuthTab.TButton' if mode==tab else 'AuthTab.TButton',
                       command=lambda tab=tab:build_auth(app,tab)).grid(row=0,column=column,sticky='ew',padx=(0,4) if column==0 else (4,0))
    title='确认使用规则' if consent else '创建本机账号' if register else '欢迎回来'
    ttk.Label(form,text=title,style='Title.TLabel').pack(anchor='w',pady=(0,8))
    subtitle=('旧账号与权限保留。请阅读以下文件后继续。' if consent else
              '首个注册者为管理员，之后为申请人。' if register else '用本机账号登录，继续处理文件。')
    ttk.Label(form,text=subtitle,style='Muted.TLabel',wraplength=340).pack(anchor='w',pady=(0,18))
    app.user=tk.StringVar(value=ADMIN_ID if first or not register else '')
    app.password=tk.StringVar();app.confirm=tk.StringVar();app.display_name=tk.StringVar()
    app.legal_accepted=tk.BooleanVar(value=False)
    if not consent:
        if register:
            fields=ttk.Frame(form);fields.pack(fill='x');fields.columnconfigure(0,weight=1,uniform='fields');fields.columnconfigure(1,weight=1,uniform='fields')
            for column,label,variable in ((0,'显示姓名',app.display_name),(1,'编号（5位数字）',app.user)):
                cell=ttk.Frame(fields);cell.grid(row=0,column=column,sticky='ew',padx=(0,6) if column==0 else (6,0))
                ttk.Label(cell,text=label).pack(anchor='w');ttk.Entry(cell,textvariable=variable,width=12).pack(fill='x',pady=(6,12))
        else:
            ttk.Label(form,text='账号编号（5位数字）').pack(anchor='w')
            ttk.Entry(form,textvariable=app.user).pack(fill='x',pady=(6,12))
        ttk.Label(form,text='密码（至少8位）').pack(anchor='w')
        password=ttk.Entry(form,textvariable=app.password,show='*');password.pack(fill='x',pady=(6,12))
        if register:
            ttk.Label(form,text='再次输入密码').pack(anchor='w')
            ttk.Entry(form,textvariable=app.confirm,show='*').pack(fill='x',pady=(6,12))
    else:
        documents=ttk.Frame(form);documents.pack(fill='x',pady=(0,16))
        for key,title,detail in (('service','本机使用服务协议','注册、审核、文件保管与责任'),
                                 ('disclaimer','功能限制与免责声明','图形章、图片签名的功能与效力边界')):
            row=ttk.Frame(documents);row.pack(fill='x',pady=(0,10))
            text=ttk.Frame(row);text.pack(side='left',fill='x',expand=True)
            ttk.Label(text,text=title,style='Section.TLabel').pack(anchor='w')
            ttk.Label(text,text=detail,style='Muted.TLabel').pack(anchor='w',pady=(5,0))
            ttk.Button(row,text='查看 ↗',style='Link.TButton',command=lambda key=key:legal_reader(app,key)).pack(side='right',padx=(12,0))
            tk.Frame(documents,bg=LINE,height=1).pack(fill='x',pady=(0,10))
    if register or consent:
        ttk.Checkbutton(form,text='我已阅读并同意服务协议与免责声明',variable=app.legal_accepted).pack(anchor='w',pady=(0,4))
    if not consent:legal_links(app,form)
    app.auth_error=tk.StringVar()
    error=ttk.Label(form,textvariable=app.auth_error,foreground='#a34835',wraplength=340)
    # Empty errors take no vertical space. A real error is placed above the action.
    def enter():
        try:
            if consent:
                app.store.accept_legal(app.token,app.legal_accepted.get())
            else:
                if register:
                    app.store.register(app.user.get().strip(),app.display_name.get(),app.password.get(),
                                       app.confirm.get(),app.legal_accepted.get())
                app.token=app.store.login(app.user.get().strip(),app.password.get())
                app.password.set('');app.confirm.set('')
                if app.login_policy.windows_session:
                    try:
                        if not app.login_policy.remember(app.store,app.token):
                            messagebox.showinfo('登录成功','Windows会话无法保存，关闭后仍需密码登录。',parent=app.root)
                    except OSError:
                        messagebox.showinfo('登录成功','Windows会话无法保存，关闭后仍需密码登录。',parent=app.root)
            app.show_main()
        except Exception as error:app.auth_error.set(str(error))
    app.auth_submit=enter
    actions=ttk.Frame(form);actions.pack(fill='x',pady=(10,0))
    app.auth_actions=actions
    def show_error(*unused):
        if app.auth_error.get():error.pack(fill='x',pady=(0,6),before=actions)
        else:error.pack_forget()
    app.auth_error.trace_add('write',show_error)
    app.auth_button=ttk.Button(actions,text='同意并继续' if consent else '注册并进入' if register else '登录工作台',
                              style='Primary.TButton',command=enter)
    app.auth_button.pack(fill='x')
    if consent:
        ttk.Button(actions,text='暂不同意，退出登录',style='Quiet.TButton',command=app.logout).pack(fill='x',pady=(10,0))
    ttk.Label(form,text=app.login_policy.description,style='Muted.TLabel',wraplength=340).pack(anchor='w',pady=(16,0))
    if register:
        ttk.Label(form,text='仅可使用有权处理的文件、印章和签名。',style='Muted.TLabel',wraplength=340).pack(anchor='w',pady=(6,0))
    def fit_shell(event):
        width=min(980,event.width)
        shell.place_configure(width=width)
        shell.update_idletasks()
        needed=max(visual.winfo_reqheight(),form.winfo_reqheight())+header.winfo_reqheight()+98
        shell.place_configure(height=min(max(570,needed),event.height))
    outer.bind('<Configure>',fit_shell)
    if not consent:password.bind('<Return>',lambda event:enter());password.focus_set()
