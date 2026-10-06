"""Product setup, immutable seal snapshots and legacy identity compatibility."""
import io,json,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import pymupdf as fitz
from seal_core import SealStore,ADMIN_ID,digest

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=SealStore(self.root/'data');self.store.setup_admin('Synthetic-Only',name='匿名示例',user_id='54321')
        self.admin=self.store.login('54321','Synthetic-Only')
        self.source=self.root/'example.pdf'
        with fitz.open() as doc:doc.new_page();doc.save(self.source)
        self.params=dict(page=0,x=50,y=60,size=110)
    def tearDown(self):self.temp.cleanup()
    def test_fresh_profile_requires_own_seal_and_custom_identity_reopens(self):
        self.assertEqual(self.store.profile()['company'],'')
        with self.assertRaises(ValueError):self.store.submit(self.admin,self.source,self.params)
        reopened=SealStore(self.store.root);self.assertTrue(reopened.initialized())
        self.assertEqual(reopened.actor(reopened.login('54321','Synthetic-Only'))['name'],'匿名示例')
        with self.assertRaises(ValueError):reopened.setup_admin('Synthetic-Again')
    def test_pending_seal_is_pinned_across_profile_changes_and_reposition(self):
        self.store.configure_profile(self.admin,company='匿名示例章甲')
        self.store.add_user(self.admin,'54322','测试用户','Synthetic-Only')
        user=self.store.login('54322','Synthetic-Only')
        rid=self.store.submit(user,self.source,self.params)
        original_asset=json.loads(self.store.request(self.admin,rid)['params'])['seal_asset']
        self.store.configure_profile(self.admin,company='匿名示例章乙')
        self.store.reposition(self.admin,rid,dict(self.params,seal_asset=self.store.profile()['seal_asset']))
        self.assertEqual(json.loads(self.store.request(self.admin,rid)['params'])['seal_asset'],original_asset)
        output=self.store.approve(self.admin,rid)
        with fitz.open(output) as doc,fitz.open(self.source) as expected:
            expected[0].insert_image(fitz.Rect(50,60,160,170),stream=self.store.seal_data(original_asset))
            with fitz.open(stream=expected.tobytes(garbage=4,deflate=True),filetype='pdf') as saved:
                self.assertEqual(doc[0].get_pixmap().samples,saved[0].get_pixmap().samples)
    def test_import_preserves_red_and_detects_tampering(self):
        im=Image.new('RGB',(200,200),'white');ImageDraw.Draw(im).ellipse((20,20,180,180),outline='red',width=5)
        buf=io.BytesIO();im.save(buf,format='PNG')
        self.store.configure_profile(self.admin,image=buf.getvalue())
        asset=self.store.profile()['seal_asset'];data=self.store.seal_data()
        with Image.open(io.BytesIO(data)) as result:
            self.assertEqual(result.getpixel((0,0))[3],0)
            self.assertTrue(any(r>200 and g<30 and b<30 and a for r,g,b,a in result.getdata()))
        (self.store.root/'seals'/f'{asset}.png').write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.store.submit(self.admin,self.source,self.params)
    def test_export_directory_and_settings_permissions(self):
        folder=self.root/'exports';folder.mkdir()
        self.store.configure_profile(self.admin,company='匿名测试章',export_dir=str(folder))
        rid=self.store.submit(self.admin,self.source,self.params);out=self.store.export_copy(self.admin,rid)
        self.assertEqual(out.parent,folder.resolve());self.assertEqual(digest(out.read_bytes()),self.store.request(self.admin,rid)['output_hash'])
        self.store.add_user(self.admin,'54322','测试用户','Synthetic-Only');user=self.store.login('54322','Synthetic-Only')
        with self.assertRaises(PermissionError):self.store.configure_profile(user,company='无权限')
        with self.assertRaises(ValueError):self.store.configure_profile(self.admin,export_dir=str(self.store.root))
    def test_old_admin_id_and_local_upgrade_profile_remain_compatible(self):
        legacy=SealStore(self.root/'legacy'/'data');legacy.setup_admin('Synthetic-Only',name='旧示例',user_id='98765')
        (legacy.root.parent/'local-defaults.json').write_text(json.dumps({'company':'旧匿名示例章'}),encoding='utf-8')
        self.assertTrue(legacy.initialized());self.assertEqual(legacy.actor(legacy.login('98765','Synthetic-Only'))['name'],'旧示例')
        self.assertTrue(legacy.seal_data().startswith(b'\x89PNG'))

if __name__=='__main__':unittest.main()
