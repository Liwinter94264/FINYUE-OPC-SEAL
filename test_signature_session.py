"""Signature and restart-session tests use synthetic files/accounts only."""
import io, json, tempfile, unittest
from pathlib import Path
from PIL import Image, ImageDraw
import pymupdf as fitz
from seal_core import SealStore, ADMIN_ID
from local_session import SessionCache, windows_context
from signatures import import_signature, handwritten_signature
from text_layer import date_labels, today_parts, text_dimensions

class SignatureSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=SealStore(self.root/'data');self.store.setup_admin('Synthetic-Admin-Only')
        self.admin=self.store.login(ADMIN_ID,'Synthetic-Admin-Only')
        self.store.configure_profile(self.admin,company='合成测试专用章')
        self.store.add_user(self.admin,'00002','合成测试','Synthetic-User-Only')
        self.user=self.store.login('00002','Synthetic-User-Only')
        self.pdf=self.root/'synthetic.pdf'
        with fitz.open() as d:
            d.new_page();d.new_page();d.save(self.pdf)
        self.params=dict(page=0,x=420,y=650,size=110)

    def tearDown(self):self.temp.cleanup()

    @staticmethod
    def ink():
        im=Image.new('RGB',(300,130),'white');draw=ImageDraw.Draw(im)
        draw.line([(40,90),(80,25),(110,90),(170,35),(230,95)],fill='black',width=6)
        buf=io.BytesIO();im.save(buf,format='PNG');return buf.getvalue()

    def sig(self,token):return self.store.create_signature(token,image=self.ink())
    def params_with_sig(self,asset):
        return dict(self.params,signature=dict(asset_id=asset,page=1,x=70,y=620,width=150,height=50))

    def test_image_removes_white_and_retains_ink_and_invalid_rejected(self):
        data=import_signature(self.ink())
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.mode,'RGBA');self.assertEqual(im.getpixel((0,0))[3],0)
            self.assertGreater(im.getchannel('A').getextrema()[1],200)
        white=io.BytesIO();Image.new('RGB',(50,50),'white').save(white,format='PNG')
        for data in (b'bad image',white.getvalue(),b'x'*(10*1024*1024+1)):
            with self.assertRaises(ValueError):import_signature(data)

    def test_handwriting_retains_pen_lifts_and_rejects_blank_or_invalid_input(self):
        strokes=[[(20,30),(100,30)],[(300,30),(400,30)]]
        with Image.open(io.BytesIO(handwritten_signature(strokes))) as im:
            self.assertGreater(im.width,im.height);self.assertEqual(im.mode,'RGBA')
            self.assertEqual(im.getpixel((0,0))[3],0)
            self.assertEqual(im.getchannel('A').crop((140,0,260,im.height)).getbbox(),None)
            self.assertGreater(im.getchannel('A').getextrema()[1],240)
        for strokes in ([],[[]],[[(3,3)]],[[(0,0),(float('nan'),4)]],
                        [[(-1,2),(3,4)]],[[(True,2),(5,6)]],[[(0,0),(681,2)]]):
            with self.subTest(strokes=strokes),self.assertRaises(ValueError):handwritten_signature(strokes)

    def test_drawn_asset_persists_and_legacy_kai_asset_remains_usable(self):
        asset=self.store.create_signature(self.admin,strokes=[[(20,80),(80,20),(100,90)]])
        original=self.store.signature(self.admin,asset)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT kind FROM signatures WHERE id=?',(asset,)).fetchone()[0],'drawn')
            # Existing images of name lettering remain compatible, without re-rendering.
            db.execute('UPDATE signatures SET kind=? WHERE id=?',('kai',asset))
        reopened=SealStore(self.store.root);token=reopened.login(ADMIN_ID,'Synthetic-Admin-Only')
        self.assertEqual(reopened.signature(token,asset),original)
        rid=reopened.submit(token,self.pdf,dict(self.params_with_sig(asset),seal_enabled=False))
        self.assertTrue(reopened.output(token,rid).exists())

    def test_signature_and_seal_different_pages_approval_and_snapshot(self):
        asset=self.sig(self.user);params=self.params_with_sig(asset);original=self.pdf.read_bytes()
        rid=self.store.submit(self.user,self.pdf,params)
        self.assertEqual(self.store.request(self.user,rid)['status'],'pending')
        self.store.reposition(self.admin,rid,dict(params,signature=dict(params['signature'],x=180)))
        self.store.approve(self.admin,rid)
        with fitz.open(self.store.output(self.user,rid)) as d:
            self.assertEqual(len(d[0].get_images()),1);self.assertEqual(len(d[1].get_images()),1)
            placed=d[1].get_image_rects(d[1].get_images()[0][0])[0]
            self.assertGreaterEqual(placed.x0,180);self.assertLessEqual(placed.x1,330)
            self.assertAlmostEqual((placed.x0+placed.x1)/2,255,delta=.1)
            self.assertAlmostEqual((placed.y0+placed.y1)/2,645,delta=.1)
        self.assertEqual(original,self.pdf.read_bytes())

    def test_signature_only_and_asset_owner_cannot_be_replaced(self):
        user_asset=self.sig(self.user);admin_asset=self.sig(self.admin)
        params=dict(self.params_with_sig(user_asset),seal_enabled=False)
        with self.assertRaises(PermissionError):self.store.submit(self.admin,self.pdf,params)
        rid=self.store.submit(self.user,self.pdf,params)
        self.assertTrue(self.store.signature(self.admin,user_asset,rid))
        with self.assertRaises(PermissionError):self.store.signature(self.admin,user_asset)
        with self.assertRaises(ValueError):
            self.store.reposition(self.admin,rid,dict(params,signature=dict(params['signature'],asset_id=admin_asset)))
        self.store.approve(self.admin,rid)
        with fitz.open(self.store.output(self.user,rid)) as d:
            self.assertEqual(len(d[0].get_images()),0);self.assertEqual(len(d[1].get_images()),1)

    def test_signature_tampering_and_invalid_positions_rejected(self):
        asset=self.sig(self.user);params=self.params_with_sig(asset)
        for key,value in [('page',True),('page',2),('x',float('nan')),('width',0),('height',200),('y',820)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.store.submit(self.user,self.pdf,dict(params,signature=dict(params['signature'],**{key:value})))
        rid=self.store.submit(self.user,self.pdf,params)
        path=self.store.root/'signatures'/f'{asset}.png';path.write_bytes(path.read_bytes()+b'tampered')
        with self.assertRaises(ValueError):self.store.approve(self.admin,rid)
        self.assertEqual(self.store.request(self.user,rid)['status'],'pending')

    def test_resume_across_app_objects_and_new_windows_session_rejected(self):
        secret=self.store.remember_session(self.admin,'synthetic-boot-logon-A')
        other=SealStore(self.store.root);token=other.restore_session(secret,'synthetic-boot-logon-A')
        self.assertEqual(other.actor(token)['id'],ADMIN_ID)
        with self.assertRaises(PermissionError):other.restore_session(secret,'synthetic-boot-logon-B')
        other.logout(token)
        with self.assertRaises(PermissionError):self.store.restore_session(secret,'synthetic-boot-logon-A')

    def test_role_reload_password_change_lock_and_bad_secret(self):
        secret=self.store.remember_session(self.user,'synthetic-A')
        with self.store.db() as db:db.execute('UPDATE users SET admin=0 WHERE id=?',('00002',))
        resumed=self.store.restore_session(secret,'synthetic-A')
        with self.assertRaises(PermissionError):self.store.add_user(resumed,'00003','合成','Synthetic-Only')
        with self.store.db() as db:db.execute('UPDATE users SET pwhash=? WHERE id=?',('changed','00002'))
        with self.assertRaises(PermissionError):self.store.restore_session(secret,'synthetic-A')
        with self.assertRaises(PermissionError):self.store.restore_session('not-a-valid-secret','synthetic-A')

    def test_resume_honors_lock_and_disabled_signature_is_rejected(self):
        import time
        secret=self.store.remember_session(self.user,'synthetic-A')
        with self.store.db() as db:db.execute('UPDATE users SET locked_until=? WHERE id=?',(time.time()+100,'00002'))
        with self.assertRaises(PermissionError):self.store.restore_session(secret,'synthetic-A')
        with self.assertRaises(ValueError):self.store.submit(self.admin,self.pdf,dict(self.params,seal_enabled=False))

    def test_signature_on_rotated_page_and_old_style_requests_remain_readable(self):
        with fitz.open(self.pdf) as d:d[1].set_rotation(90);rotated=self.root/'rotated.pdf';d.save(rotated)
        asset=self.sig(self.admin);params=self.params_with_sig(asset)
        params['signature'].update(x=650,y=420,width=150,height=50)
        rid=self.store.submit(self.admin,rotated,params)
        with fitz.open(self.store.output(self.admin,rid)) as d:
            self.assertEqual(d[1].rotation,0)
            rect=d[1].get_image_rects(d[1].get_images()[0][0])[0]
            self.assertAlmostEqual((rect.x0+rect.x1)/2,725,delta=.1)
        old=self.store.submit(self.admin,self.pdf,self.params)
        reopened=SealStore(self.store.root);token=reopened.login(ADMIN_ID,'Synthetic-Admin-Only')
        self.assertTrue(reopened.output(token,old).exists())

    def test_real_windows_dpapi_reopen_context_change_corruption_and_clear(self):
        if not windows_context():self.skipTest('Windows session APIs unavailable')
        path=self.root/'session.dpapi';cache=SessionCache(path)
        self.assertTrue(cache.remember(self.store,self.admin))
        self.assertNotIn(b'Synthetic-Admin-Only',path.read_bytes())
        self.assertNotIn(b'context',path.read_bytes())
        other=SealStore(self.store.root);token=cache.restore(other)
        self.assertEqual(other.actor(token)['id'],ADMIN_ID)
        fake=SessionCache(path,context=lambda:'different-Windows-logon')
        self.assertIsNone(fake.restore(other));self.assertFalse(path.exists())
        cache.remember(self.store,self.admin);path.write_bytes(b'corrupted')
        self.assertIsNone(cache.restore(other));self.assertFalse(path.exists())
        cache.remember(self.store,self.admin);cache.clear();self.assertIsNone(cache.restore(other))

    def test_date_slots_and_text_only_export_preserve_original(self):
        import os
        date_pdf=self.root/'synthetic-date.pdf'
        with fitz.open() as d:
            page=d.new_page();page.insert_font(fontname='LocalSong',fontfile=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simsun.ttc'))
            page.insert_text((280,730),'年        月        日',fontname='LocalSong',fontsize=16)
            labels=date_labels(page,0);d.save(date_pdf)
        self.assertEqual([v['text'] for v in labels],list(today_parts()))
        original=date_pdf.read_bytes()
        rid=self.store.submit(self.admin,date_pdf,dict(self.params,seal_enabled=False,labels=labels))
        with fitz.open(self.store.output(self.admin,rid)) as d:self.assertEqual(len(d[0].get_images()),3)
        self.assertEqual(date_pdf.read_bytes(),original)
        with fitz.open(self.pdf) as d:
            with self.assertRaises(ValueError):date_labels(d[0],0)

    def test_text_limits_geometry_and_reviewer_cannot_rewrite(self):
        label=dict(text='合成日期文字',page=0,x=70,y=620,font_size=12)
        params=dict(self.params,labels=[label])
        rid=self.store.submit(self.user,self.pdf,params)
        with self.assertRaises(ValueError):self.store.reposition(self.admin,rid,dict(params,labels=[dict(label,text='changed')]))
        self.store.reposition(self.admin,rid,dict(params,labels=[dict(label,x=150)]));self.store.approve(self.admin,rid)
        for change in ({'font_size':float('nan')},{'x':float('inf')},{'page':True},{'text':'x'*201},{'text':''},{'y':850}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.store.submit(self.admin,self.pdf,dict(params,labels=[dict(label,**change)]))
        with self.assertRaises(ValueError):self.store.submit(self.admin,self.pdf,dict(params,labels=[label]*11))

if __name__=='__main__':unittest.main()
