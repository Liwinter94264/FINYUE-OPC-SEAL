"""Local PDF stamp approval service. No cloud or external transmission."""
from __future__ import annotations
import hashlib, hmac, io, json, math, os, re, secrets, sqlite3, time, uuid
from pathlib import Path
from contextlib import contextmanager
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from signatures import kai_signature, import_signature
from text_layer import text_png, text_dimensions
from legal_text import legal_manifest

COMPANY = "示例企业"
ADMIN_ID = "00001"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300000).hex()

def stamp_png(company=COMPANY):
    if not isinstance(company,str) or not 2<=len(company.strip())<=32:
        raise ValueError('印章名称应为2至32字。')
    company=company.strip()
    image = Image.new("RGBA", (640, 640))
    draw = ImageDraw.Draw(image)
    red = (218, 12, 24, 255)
    # Common domestic company seal layout: one round rim, Song-style arc text,
    # centered star. No invented registered seal number or certification.
    draw.ellipse((12, 12, 628, 628), outline=red, width=16)
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/simsun.ttc"
    font = ImageFont.truetype(str(font_path), 54)
    for i, ch in enumerate(company):
        angle = 210 - i * 240 / (len(company)-1)
        a = math.radians(angle)
        tile = Image.new("RGBA", (86, 86))
        ImageDraw.Draw(tile).text((43, 43), ch, font=font, fill=red, anchor="mm",stroke_width=1)
        tile = tile.rotate(angle-90, resample=Image.Resampling.BICUBIC, expand=True)
        x, y = 320 + 248*math.cos(a), 320 - 248*math.sin(a)
        image.alpha_composite(tile, (round(x-tile.width/2), round(y-tile.height/2)))
    points=[]
    for i in range(10):
        a=math.radians(-90+i*36);r=100 if i%2==0 else 38.2
        points.append((320+r*math.cos(a),320+r*math.sin(a)))
    draw.polygon(points, fill=red)
    buffer=io.BytesIO();image.save(buffer, format="PNG")
    return buffer.getvalue()

def validate_pdf(data):
    if len(data)>50*1024*1024:
        raise ValueError("PDF不得超过50MB。")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.is_encrypted:
            raise ValueError("请先提供未加密PDF。")
        if not 1<=len(doc)<=500:
            raise ValueError("PDF页数应为1至500页。")
        if doc.get_sigflags()>0:
            for page in doc:
                for widget in page.widgets() or []:
                    if widget.field_type==fitz.PDF_WIDGET_TYPE_SIGNATURE and widget.field_value:
                        raise ValueError("文件已有数字签名，请勿覆盖签名后的文件。")
        return len(doc)

class SealStore:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        for sub in ("originals","outputs","signatures","seals"):(self.root/sub).mkdir(exist_ok=True)
        self.profile_path=self.root/'profile.json'
        self.db_path=self.root/"approval.sqlite3"
        self.sessions={}
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,
              salt BLOB NOT NULL,pwhash TEXT NOT NULL,admin INTEGER NOT NULL DEFAULT 0,
              failures INTEGER NOT NULL DEFAULT 0,locked_until REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,applicant TEXT NOT NULL,
              filename TEXT NOT NULL,source_hash TEXT NOT NULL,params TEXT NOT NULL,
              status TEXT NOT NULL,created REAL NOT NULL,reviewer TEXT,reviewed REAL,
              reason TEXT NOT NULL DEFAULT '',output_hash TEXT);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at REAL NOT NULL,
              actor TEXT NOT NULL,action TEXT NOT NULL,request_id TEXT,details TEXT);
            CREATE TABLE IF NOT EXISTS remembered_sessions(token_hash TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,context TEXT NOT NULL,credential_hash TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS signatures(id TEXT PRIMARY KEY,owner TEXT NOT NULL,
              hash TEXT NOT NULL,kind TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS legal_consents(user_id TEXT NOT NULL,document TEXT NOT NULL,
              version TEXT NOT NULL,text_hash TEXT NOT NULL,accepted REAL NOT NULL,
              PRIMARY KEY(user_id,document,version,text_hash));
            """)
            if 'source_path' not in {r[1] for r in db.execute('PRAGMA table_info(requests)')}:
                db.execute("ALTER TABLE requests ADD COLUMN source_path TEXT")

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.db_path,timeout=20)
        db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def initialized(self):
        with self.db() as db:return db.execute("SELECT 1 FROM users WHERE admin=1").fetchone() is not None

    def setup_admin(self, password, name='本机用户', user_id=ADMIN_ID):
        if len(password)<8:raise ValueError("管理员密码至少8位。")
        if not isinstance(name,str) or not 1<=len(name.strip())<=32:raise ValueError('请填写本人显示姓名。')
        if not re.fullmatch(r'\d{5}',user_id):raise ValueError('账号编号应为5位数字。')
        salt=secrets.token_bytes(24)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users").fetchone():raise ValueError("已初始化，请登录。")
            db.execute("INSERT INTO users(id,name,salt,pwhash,admin) VALUES(?,?,?,?,1)",
                       (user_id,name.strip(),salt,password_hash(password,salt)))

    def register(self, user_id, name, password, confirmation, accepted=False):
        if not isinstance(user_id,str) or not re.fullmatch(r'[0-9]{5}',user_id):
            raise ValueError('账号编号应为5位数字。')
        if not isinstance(name,str) or not 1<=len(name.strip())<=32 or any(ord(c)<32 for c in name):
            raise ValueError('显示姓名应为1至32字，不得包含换行或控制字符。')
        if not isinstance(password,str) or not 8<=len(password)<=256:
            raise ValueError('密码应为8至256位。')
        if password!=confirmation:raise ValueError('两次密码不同。')
        if accepted is not True:raise ValueError('请先阅读并同意服务协议与免责声明。')
        salt=secrets.token_bytes(24);hashed=password_hash(password,salt)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            admin=not bool(db.execute('SELECT 1 FROM users').fetchone())
            if db.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone():
                raise ValueError('账号编号已存在，请登录或使用其他编号。')
            db.execute('INSERT INTO users(id,name,salt,pwhash,admin) VALUES(?,?,?,?,?)',
                       (user_id,name.strip(),salt,hashed,int(admin)))
            self._record_consent(db,user_id)
            self.audit(db,user_id,'register',None,'admin' if admin else 'applicant')
        return admin

    def _record_consent(self,db,user_id):
        manifest=legal_manifest();now=time.time()
        for key,value in manifest.items():
            db.execute('INSERT OR IGNORE INTO legal_consents VALUES(?,?,?,?,?)',
                       (user_id,key,value['version'],value['hash'],now))
        self.audit(db,user_id,'accept_legal',None,json.dumps(manifest,sort_keys=True))

    def has_current_consent(self,token):
        actor=self.actor(token)
        with self.db() as db:
            return all(db.execute('SELECT 1 FROM legal_consents WHERE user_id=? AND document=? AND version=? AND text_hash=?',
                       (actor['id'],key,value['version'],value['hash'])).fetchone()
                       for key,value in legal_manifest().items())

    def accept_legal(self,token,accepted=False):
        actor=self.actor(token)
        if accepted is not True:raise ValueError('请先阅读并同意服务协议与免责声明。')
        with self.db() as db:self._record_consent(db,actor['id'])

    def profile(self):
        if self.profile_path.exists():
            return json.loads(self.profile_path.read_text(encoding='utf-8'))
        # Local upgrade settings are deliberately excluded from source distributions.
        legacy=self.root.parent/'local-defaults.json'
        if legacy.exists():
            return dict(company=json.loads(legacy.read_text(encoding='utf-8')).get('company',''),seal_asset=None,export_dir='')
        return dict(company='',seal_asset=None,export_dir='')

    def configure_profile(self,token,company=None,image=None,export_dir=None):
        actor=self.actor(token,True);profile=self.profile()
        if company is not None or image is not None:
            data=stamp_png(company) if image is None else self.normalize_seal(image)
            asset=digest(data);(self.root/'seals'/f'{asset}.png').write_bytes(data)
            profile.update(company=company.strip() if company else '自有印章',seal_asset=asset)
        if export_dir is not None:
            folder=Path(export_dir).resolve() if export_dir else None
            if folder and (not folder.is_dir() or folder.is_relative_to(self.root.resolve())):
                raise ValueError('请选择内部data以外的现有导出文件夹。')
            profile['export_dir']=str(folder) if folder else ''
        temp=self.profile_path.with_suffix('.tmp')
        temp.write_text(json.dumps(profile,ensure_ascii=False),encoding='utf-8');os.replace(temp,self.profile_path)
        with self.db() as db:self.audit(db,actor['id'],'configure_profile',None)

    @staticmethod
    def normalize_seal(data):
        if len(data)>10*1024*1024:raise ValueError('印章图片不得超过10MB。')
        with Image.open(io.BytesIO(data)) as im:
            if im.width*im.height>16000000:raise ValueError('印章图片不得超过1600万像素。')
            im=im.convert('RGBA');im.thumbnail((1200,1200),Image.Resampling.LANCZOS)
            if max(im.size)/min(im.size)>1.2:raise ValueError('请选择接近正方形的印章图片。')
            # Preserve colored ink; remove only near-white pixels.
            im.putdata([(r,g,b,0 if min(r,g,b)>240 else a) for r,g,b,a in im.getdata()])
            bounds=im.getbbox()
            if not bounds:raise ValueError('印章图片没有可见内容。')
            side=max(im.size);square=Image.new('RGBA',(side,side));square.alpha_composite(im,((side-im.width)//2,(side-im.height)//2))
            out=io.BytesIO();square.save(out,format='PNG');return out.getvalue()

    def seal_data(self,asset=None):
        if asset is None:
            profile=self.profile();asset=profile.get('seal_asset')
            if not asset and profile.get('company'):return stamp_png(profile['company'])
        if not isinstance(asset,str) or not re.fullmatch('[a-f0-9]{64}',asset):raise ValueError('请先在设置中配置本人或本企业印章。')
        data=(self.root/'seals'/f'{asset}.png').read_bytes()
        if digest(data)!=asset:raise ValueError('印章素材校验失败，请重新配置。')
        return data

    def login(self, user_id, password):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
            if row and row['locked_until']>time.time():raise ValueError("登录暂时锁定，请15分钟后重试。")
            if not row or not hmac.compare_digest(password_hash(password,row['salt']),row['pwhash']):
                if row:
                    failures=row['failures']+1
                    db.execute("UPDATE users SET failures=?,locked_until=? WHERE id=?",
                               (failures,time.time()+900 if failures>=5 else 0,user_id))
                    db.commit()
                raise ValueError("账号编号或密码不正确。")
            db.execute("UPDATE users SET failures=0,locked_until=0 WHERE id=?",(user_id,))
        token=secrets.token_urlsafe(32);self.sessions[token]=dict(row)
        return token

    def logout(self, token):
        actor=self.sessions.pop(token,None)
        if actor:
            with self.db() as db:db.execute('DELETE FROM remembered_sessions WHERE user_id=?',(actor['id'],))

    def remember_session(self,token,context):
        actor=self.actor(token)
        if not isinstance(context,str) or not 1<=len(context)<=256:raise ValueError('Windows会话无效。')
        secret=secrets.token_urlsafe(32)
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(actor['id'],)).fetchone()
            credential=digest(row['salt']+row['pwhash'].encode())
            db.execute('DELETE FROM remembered_sessions WHERE context=? OR user_id=?',(context,actor['id']))
            db.execute('INSERT INTO remembered_sessions VALUES(?,?,?,?,?)',
                (digest(secret.encode()),actor['id'],context,credential,time.time()))
        return secret

    def restore_session(self,secret,context):
        if not isinstance(secret,str) or not 20<=len(secret)<=128:raise PermissionError('请重新登录。')
        with self.db() as db:
            saved=db.execute('SELECT * FROM remembered_sessions WHERE token_hash=?',(digest(secret.encode()),)).fetchone()
            if not saved or saved['context']!=context:raise PermissionError('请重新登录。')
            row=db.execute('SELECT * FROM users WHERE id=?',(saved['user_id'],)).fetchone()
            if not row or row['locked_until']>time.time() or not hmac.compare_digest(saved['credential_hash'],digest(row['salt']+row['pwhash'].encode())):
                raise PermissionError('请重新登录。')
            self.audit(db,row['id'],'restore_session',None)
        token=secrets.token_urlsafe(32);self.sessions[token]=dict(row)
        return token

    def revoke_remembered(self,secret):
        with self.db() as db:db.execute('DELETE FROM remembered_sessions WHERE token_hash=?',(digest(secret.encode()),))

    def create_signature(self,token,name=None,image=None):
        actor=self.actor(token)
        if (name is None)==(image is None):raise ValueError('请选择姓名生成或图片导入。')
        data=kai_signature(name) if name is not None else import_signature(image)
        asset_id=uuid.uuid4().hex;path=self.root/'signatures'/f'{asset_id}.png'
        path.write_bytes(data)
        try:
            with self.db() as db:
                db.execute('INSERT INTO signatures VALUES(?,?,?,?,?)',(asset_id,actor['id'],digest(data),'kai' if name is not None else 'image',time.time()))
                self.audit(db,actor['id'],'create_signature',None,asset_id)
        except Exception:path.unlink(missing_ok=True);raise
        return asset_id

    def _signature_data(self,asset_id,owner):
        if not isinstance(asset_id,str) or not re.fullmatch('[a-f0-9]{32}',asset_id):raise ValueError('签名素材无效。')
        with self.db() as db:row=db.execute('SELECT * FROM signatures WHERE id=?',(asset_id,)).fetchone()
        if not row or row['owner']!=owner:raise PermissionError('只能使用申请人本人的签名素材。')
        data=(self.root/'signatures'/f'{asset_id}.png').read_bytes()
        if digest(data)!=row['hash']:raise ValueError('签名素材已改变，请重新导入。')
        return data

    def signature(self,token,asset_id,request_id=None):
        actor=self.actor(token);owner=actor['id']
        if request_id:
            row=self.request(token,request_id)
            if (json.loads(row['params']).get('signature') or {}).get('asset_id')!=asset_id:raise PermissionError('该签名不属于本申请。')
            owner=row['applicant']
        return self._signature_data(asset_id,owner)

    def last_signature(self,token):
        actor=self.actor(token)
        with self.db() as db:row=db.execute('SELECT id FROM signatures WHERE owner=? ORDER BY created DESC LIMIT 1',(actor['id'],)).fetchone()
        return row['id'] if row else None

    def actor(self, token, admin=False):
        row=self.sessions.get(token)
        if not row:raise PermissionError("请重新登录。")
        if admin and not row['admin']:raise PermissionError("只有管理员可以审核。")
        return row

    def add_user(self, token, user_id, name, password):
        actor=self.actor(token,True)
        if not re.fullmatch(r"\d{5}",user_id) or user_id==actor['id']:raise ValueError("请使用其他5位数字工号。")
        if not name.strip() or len(password)<8:raise ValueError("请填写姓名，密码至少8位。")
        salt=secrets.token_bytes(24)
        with self.db() as db:
            db.execute("INSERT INTO users(id,name,salt,pwhash) VALUES(?,?,?,?)",(user_id,name.strip(),salt,password_hash(password,salt)))
            self.audit(db,actor['id'],"create_user",None,user_id)

    @staticmethod
    def audit(db,actor,action,request_id,details=""):
        db.execute("INSERT INTO audit(at,actor,action,request_id,details) VALUES(?,?,?,?,?)",(time.time(),actor,action,request_id,details))

    def submit(self, token, source, params, expected_hash=None):
        actor=self.actor(token)
        source=Path(source).resolve()
        if source.suffix.lower()!='.pdf':raise ValueError("第一版支持PDF，请先将Word导出为PDF。")
        data=source.read_bytes();validate_pdf(data)
        if expected_hash and digest(data)!=expected_hash:
            raise ValueError("预览后原文件已改变，请重新选择文件核对。")
        self.check_position(data,params)
        params=dict(params)
        if params.get('seal_enabled',True):
            profile=self.profile()
            if profile.get('seal_asset'):params['seal_asset']=profile['seal_asset']
            elif profile.get('company'):
                png=self.seal_data();asset=digest(png);(self.root/'seals'/f'{asset}.png').write_bytes(png);params['seal_asset']=asset
            else:raise ValueError('请先配置自有印章，或取消添加印章。')
            self.seal_data(params['seal_asset'])
        if params.get('signature'):self._signature_data(params['signature']['asset_id'],actor['id'])
        request_id=uuid.uuid4().hex
        original=self.root/'originals'/f'{request_id}.pdf'
        original.write_bytes(data)
        try:
            with self.db() as db:
                db.execute("INSERT INTO requests(id,applicant,filename,source_hash,params,status,created,source_path) VALUES(?,?,?,?,?,'pending',?,?)",
                   (request_id,actor['id'],source.name,digest(data),json.dumps(params),time.time(),str(source)))
                self.audit(db,actor['id'],"submit",request_id,digest(data))
        except Exception:
            original.unlink(missing_ok=True);raise
        if actor['admin']:
            self.approve(token,request_id,auto=True)
        return request_id

    @staticmethod
    def check_position(data,params):
        with fitz.open(stream=data,filetype='pdf') as doc:
            if isinstance(params['page'],bool) or not isinstance(params['page'],int):
                raise ValueError("盖章页码应为整数。")
            p=params['page'];x=float(params['x']);y=float(params['y']);size=float(params['size'])
            if p<0 or p>=len(doc) or not all(math.isfinite(v) for v in (x,y,size)):raise ValueError("盖章页码或位置无效。")
            rect=doc[p].rect
            if params.get('seal_enabled',True) and (size<40 or size>180 or x<0 or y<0 or x+size>rect.width+0.01 or y+size>rect.height+0.01):
                raise ValueError("印章应完整放在页面内，直径约14至63毫米。")
            sig=params.get('signature')
            labels=params.get('labels',[])
            if not isinstance(labels,list) or len(labels)>10:raise ValueError('最多添加10个文本框。')
            if not params.get('seal_enabled',True) and not sig and not labels:raise ValueError('请选择公章、签名或文字。')
            if sig:
                if isinstance(sig['page'],bool) or not isinstance(sig['page'],int) or not 0<=sig['page']<len(doc):raise ValueError('签名页码无效。')
                sx,sy,sw,sh=(float(sig[k]) for k in ('x','y','width','height'))
                sr=doc[sig['page']].rect
                if not all(math.isfinite(v) for v in (sx,sy,sw,sh)) or not 10<=sw<=350 or not 4<=sh<=160 or sx<0 or sy<0 or sx+sw>sr.width+.01 or sy+sh>sr.height+.01:
                    raise ValueError('签名应完整放在页面内，宽度约4至123毫米，高度约2至56毫米。')
            for label in labels:
                lp=label['page']
                if isinstance(lp,bool) or not isinstance(lp,int) or not 0<=lp<len(doc):raise ValueError('文字页码无效。')
                lw,lh=text_dimensions(label['text'],label['font_size']);lx,ly=float(label['x']),float(label['y'])
                if not all(math.isfinite(v) for v in (lx,ly,lw,lh)) or lx<0 or ly<0 or lx+lw>doc[lp].rect.width+.01 or ly+lh>doc[lp].rect.height+.01:
                    raise ValueError('文本框应完整放在页面内，请调整位置或字号。')

    def list_requests(self,token):
        actor=self.actor(token)
        with self.db() as db:
            if actor['admin']:return [dict(r) for r in db.execute("SELECT * FROM requests ORDER BY created DESC")]
            return [dict(r) for r in db.execute("SELECT * FROM requests WHERE applicant=? ORDER BY created DESC",(actor['id'],))]

    def request(self,token,request_id):
        actor=self.actor(token)
        with self.db() as db:row=db.execute("SELECT * FROM requests WHERE id=?",(request_id,)).fetchone()
        if not row or (not actor['admin'] and row['applicant']!=actor['id']):raise PermissionError("无法访问此申请。")
        return dict(row)

    def original(self,token,request_id):
        row=self.request(token,request_id)
        data=(self.root/'originals'/f'{request_id}.pdf').read_bytes()
        if digest(data)!=row['source_hash']:raise ValueError("申请文件已改变，请重新申请。")
        return data

    def approve(self,token,request_id,auto=False):
        actor=self.actor(token,True)
        temp=self.root/'outputs'/f'{request_id}.tmp'
        final=self.root/'outputs'/f'{request_id}.pdf'
        created_output=False
        try:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
                if not row or row['status']!='pending':raise ValueError("申请不存在或已经处理。")
                if auto and row['applicant']!=actor['id']:raise PermissionError("仅管理员本人申请可自动通过。")
                data=(self.root/'originals'/f'{request_id}.pdf').read_bytes()
                if digest(data)!=row['source_hash']:raise ValueError("申请文件已改变，请重新申请。")
                params=json.loads(row['params']);self.check_position(data,params)
                sig=params.get('signature')
                sig_data=self._signature_data(sig['asset_id'],row['applicant']) if sig else None
                with fitz.open(stream=data,filetype='pdf') as doc:
                    if params.get('seal_enabled',True):
                        page=doc[int(params['page'])]
                        if page.rotation:page.remove_rotation()
                        x,y,size=float(params['x']),float(params['y']),float(params['size'])
                        page.insert_image(fitz.Rect(x,y,x+size,y+size),stream=self.seal_data(params.get('seal_asset')),overlay=True)
                    if sig:
                        page=doc[sig['page']]
                        if page.rotation:page.remove_rotation()
                        x,y,w,h=(float(sig[k]) for k in ('x','y','width','height'))
                        page.insert_image(fitz.Rect(x,y,x+w,y+h),stream=sig_data,overlay=True)
                    for label in params.get('labels',[]):
                        page=doc[label['page']]
                        if page.rotation:page.remove_rotation()
                        x,y=float(label['x']),float(label['y']);w,h=text_dimensions(label['text'],label['font_size'])
                        page.insert_image(fitz.Rect(x,y,x+w,y+h),stream=text_png(label['text']),overlay=True)
                    doc.save(temp,garbage=4,deflate=True)
                out_hash=digest(temp.read_bytes())
                if final.exists():raise ValueError("盖章输出已存在，拒绝覆盖。")
                os.replace(temp,final)
                created_output=True
                db.execute("UPDATE requests SET status='approved',reviewer=?,reviewed=?,output_hash=? WHERE id=?",(actor['id'],time.time(),out_hash,request_id))
                self.audit(db,actor['id'],"auto_approve_stamp" if auto else "approve_stamp",request_id,out_hash)
        except Exception:
            temp.unlink(missing_ok=True)
            # Only remove our new file if the approval transaction did not commit.
            with self.db() as db:row=db.execute('SELECT status FROM requests WHERE id=?',(request_id,)).fetchone()
            if created_output and row and row['status']=='pending':final.unlink(missing_ok=True)
            raise
        return final

    def reposition(self,token,request_id,params):
        actor=self.actor(token,True)
        data=self.original(token,request_id);self.check_position(data,params)
        before=self.request(token,request_id)
        old_sig=json.loads(before['params']).get('signature');new_sig=params.get('signature')
        params=dict(params)
        if json.loads(before['params']).get('seal_asset'):params['seal_asset']=json.loads(before['params'])['seal_asset']
        if bool(old_sig)!=bool(new_sig) or (new_sig and old_sig['asset_id']!=new_sig['asset_id']):raise ValueError('审核时只能调整原签名的位置，不能替换申请人的签名。')
        if new_sig:self._signature_data(new_sig['asset_id'],before['applicant'])
        old_labels=json.loads(before['params']).get('labels',[]);new_labels=params.get('labels',[])
        if [v['text'] for v in old_labels]!=[v['text'] for v in new_labels]:raise ValueError('审核时不能改写申请人的文字，请退回后重新提交。')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM requests WHERE id=?',(request_id,)).fetchone()
            if not row or row['status']!='pending':raise ValueError("只能调整待审核申请。")
            db.execute('UPDATE requests SET params=? WHERE id=?',(json.dumps(params),request_id))
            self.audit(db,actor['id'],'reposition',request_id,json.dumps(params))

    def reject(self,token,request_id,reason):
        actor=self.actor(token,True)
        if not reason.strip():raise ValueError("请填写退回理由。")
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM requests WHERE id=?',(request_id,)).fetchone()
            if not row or row['status']!='pending':raise ValueError("申请不存在或已经处理。")
            db.execute("UPDATE requests SET status='rejected',reviewer=?,reviewed=?,reason=? WHERE id=?",(actor['id'],time.time(),reason.strip(),request_id))
            self.audit(db,actor['id'],"reject",request_id,reason.strip())

    def output(self,token,request_id):
        row=self.request(token,request_id)
        if row['status']!='approved':raise ValueError("只有已通过且未作废的申请可以导出。")
        p=self.root/'outputs'/f'{request_id}.pdf'
        if digest(p.read_bytes())!=row['output_hash']:raise ValueError("输出文件校验失败。")
        return p

    def export(self,token,request_id,target):
        row=self.request(token,request_id)
        target=Path(target).resolve()
        if target.suffix.lower()!='.pdf':raise ValueError("请导出为PDF文件。")
        if target.is_relative_to(self.root.resolve()) or (row['source_path'] and target==Path(row['source_path']).resolve()):
            raise ValueError("不能覆盖原文件或内部数据，请选择其他导出位置。")
        created=False
        try:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                current=db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
                if not current or current['status']!='approved':raise ValueError('申请未通过或已作废，不能导出。')
                data=(self.root/'outputs'/f'{request_id}.pdf').read_bytes()
                if digest(data)!=current['output_hash']:raise ValueError('输出文件校验失败。')
                # Exclusive creation avoids overwriting originals, existing copies or hard links.
                with target.open('xb') as stream:
                    created=True;stream.write(data);stream.flush();os.fsync(stream.fileno())
                if digest(target.read_bytes())!=current['output_hash']:raise ValueError('导出副本校验失败。')
                self.audit(db,self.actor(token)['id'],'export',request_id,current['output_hash'])
        except FileExistsError:
            raise ValueError('此位置已有文件，请换一个文件名，原文件不会覆盖。') from None
        except Exception:
            if created:target.unlink(missing_ok=True)
            raise
        return target

    def export_copy(self,token,request_id):
        row=self.request(token,request_id)
        configured=self.profile().get('export_dir')
        folder=Path(configured) if configured else (Path(row['source_path']).parent if row['source_path'] else self.root.parent/'导出副本')
        if not folder.is_dir():folder=self.root.parent/'导出副本'
        folder.mkdir(parents=True,exist_ok=True)
        name=Path(row['filename']).stem+'_已处理副本_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3)+'.pdf'
        return self.export(token,request_id,folder/name)

    def withdraw(self,token,request_id,reason):
        actor=self.actor(token)
        if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:raise ValueError('请填写1至500字的撤回或作废理由。')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
            if not row or (not actor['admin'] and row['applicant']!=actor['id']):raise PermissionError('无法处理此申请。')
            if row['status']=='pending':status='withdrawn';action='withdraw_request'
            elif row['status']=='approved':
                if not actor['admin']:raise PermissionError('已通过申请需要管理员作废。')
                status='revoked';action='revoke_approval'
            else:raise ValueError('申请已处理，不能重复撤回或作废。')
            db.execute('UPDATE requests SET status=?,reason=? WHERE id=?',(status,reason.strip(),request_id))
            self.audit(db,actor['id'],action,request_id,reason.strip())
        return status
