"""Workflow tests use synthetic PDFs and temporary local accounts only."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
import pymupdf as fitz
from seal_core import SealStore, ADMIN_ID, digest

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.store=SealStore(self.root/'data')
        self.store.setup_admin('Synthetic-Admin-Only')
        self.admin=self.store.login(ADMIN_ID,'Synthetic-Admin-Only')
        self.store.configure_profile(self.admin,company='合成测试专用章')
        self.store.add_user(self.admin,'00002','合成测试申请人','Synthetic-User-Only')
        self.user=self.store.login('00002','Synthetic-User-Only')
        self.source=self.root/'synthetic.pdf'
        with fitz.open() as doc:
            p=doc.new_page();p.insert_text((50,60),'SYNTHETIC TEST ONLY')
            doc.save(self.source)
        self.params=dict(page=0,x=420,y=680,size=110)

    def tearDown(self):self.temp.cleanup()
    def pending(self):return self.store.submit(self.user,self.source,self.params)

    def test_admin_auto_approval_and_original_preserved(self):
        before=self.source.read_bytes()
        rid=self.store.submit(self.admin,self.source,self.params)
        self.assertEqual(self.store.request(self.admin,rid)['status'],'approved')
        self.assertEqual(self.source.read_bytes(),before)
        with fitz.open(self.store.output(self.admin,rid)) as d:
            self.assertEqual(len(d[0].get_images()),1)
        with self.assertRaises(ValueError):self.store.approve(self.admin,rid)
        self.assertTrue(self.store.output(self.admin,rid).exists())

    def test_non_admin_cannot_approve_or_auto_approve_other_user(self):
        rid=self.pending()
        with self.assertRaises(PermissionError):self.store.approve(self.user,rid)
        with self.assertRaises(PermissionError):self.store.approve(self.admin,rid,auto=True)
        self.assertEqual(self.store.request(self.user,rid)['status'],'pending')

    def test_manual_reposition_approve_export(self):
        rid=self.pending();p=dict(self.params,x=55,y=100)
        self.store.reposition(self.admin,rid,p);self.store.approve(self.admin,rid)
        target=self.root/'copy.pdf';self.store.export(self.user,rid,target)
        self.assertEqual(digest(target.read_bytes()),self.store.request(self.user,rid)['output_hash'])
        with self.assertRaises(ValueError):self.store.export(self.admin,rid,self.source)
        with self.assertRaises(ValueError):self.store.export(self.admin,rid,self.store.root/'other.pdf')

    def test_rejection_is_final_and_requires_reason(self):
        rid=self.pending()
        with self.assertRaises(ValueError):self.store.reject(self.admin,rid,' ')
        self.store.reject(self.admin,rid,'合成测试退回')
        with self.assertRaises(ValueError):self.store.approve(self.admin,rid)
        with self.assertRaises(ValueError):self.store.output(self.user,rid)

    def test_source_and_output_tampering_detected(self):
        rid=self.pending();p=self.store.root/'originals'/f'{rid}.pdf'
        p.write_bytes(p.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.store.approve(self.admin,rid)
        rid2=self.store.submit(self.admin,self.source,self.params)
        out=self.store.output(self.admin,rid2);out.write_bytes(out.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.store.output(self.admin,rid2)

    def test_preview_hash_change_rejected(self):
        old_hash=digest(self.source.read_bytes());self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.store.submit(self.admin,self.source,self.params,expected_hash=old_hash)

    def test_encrypted_invalid_and_wrong_extension_rejected(self):
        with fitz.open(self.source) as doc:
            enc=self.root/'encrypted.pdf';doc.save(enc,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='Synthetic-Only',user_pw='Synthetic-Only')
        with self.assertRaises(ValueError):self.store.submit(self.user,enc,self.params)
        bad=self.root/'invalid.pdf';bad.write_bytes(b'not a PDF')
        with self.assertRaises(Exception):self.store.submit(self.user,bad,self.params)
        text=self.root/'unsupported.docx';text.write_bytes(b'test')
        with self.assertRaises(ValueError):self.store.submit(self.user,text,self.params)

    def test_permissions_and_logout(self):
        rid=self.store.submit(self.admin,self.source,self.params)
        with self.assertRaises(PermissionError):self.store.request(self.user,rid)
        with self.assertRaises(PermissionError):self.store.add_user(self.user,'00003','测试','Synthetic-Only')
        self.assertEqual(self.store.list_requests(self.user),[])
        self.store.logout(self.user)
        with self.assertRaises(PermissionError):self.pending()

    def test_invalid_positions_and_page_types(self):
        for key,value in [('x',float('nan')),('y',float('inf')),('x',-1),('size',181),('y',800),('page',1),('page',0.5),('page',True)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                self.store.submit(self.user,self.source,dict(self.params,**{key:value}))

    def test_concurrent_approval_only_one_output(self):
        rid=self.pending()
        def run(_):
            try:self.store.approve(self.admin,rid);return 'ok'
            except ValueError:return 'already'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(run,range(2)))
        self.assertEqual(sorted(results),['already','ok'])
        self.assertTrue(self.store.output(self.admin,rid).exists())

    def test_rotated_page_position_uses_visible_geometry(self):
        with fitz.open(self.source) as doc:
            doc[0].set_rotation(90);rot=self.root/'rotated.pdf';doc.save(rot)
        rid=self.store.submit(self.admin,rot,dict(page=0,x=680,y=420,size=110))
        with fitz.open(self.store.output(self.admin,rid)) as doc:
            self.assertEqual(doc[0].rotation,0)
            self.assertAlmostEqual(doc[0].get_image_rects(doc[0].get_images()[0][0])[0].x0,680)

    def test_lockout_and_admin_cannot_be_recreated(self):
        for _ in range(5):
            with self.assertRaises(ValueError):self.store.login('00002','wrong')
        with self.assertRaisesRegex(ValueError,'锁定'):self.store.login('00002','Synthetic-User-Only')
        with self.assertRaises(ValueError):self.store.setup_admin('Synthetic-Again')
        with self.assertRaises(ValueError):self.store.add_user(self.admin,ADMIN_ID,'冒充','Synthetic-Only')

if __name__=='__main__':unittest.main()
