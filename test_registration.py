"""Synthetic registration/consent and login-policy regressions."""
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pymupdf as fitz
from legal_text import legal_manifest, DOCUMENTS
from login_policy import LoginPolicy
from seal_core import SealStore, ADMIN_ID

PASSWORD='Synthetic-Only-Password'

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=SealStore(self.root/'data')

    def tearDown(self):self.temp.cleanup()

    def register(self,number='10001'):
        return self.store.register(number,'合成测试',PASSWORD,PASSWORD,True)

    def test_first_admin_later_applicant_and_review_enforced(self):
        self.assertTrue(self.register());self.assertFalse(self.register('10002'))
        admin=self.store.login('10001',PASSWORD);user=self.store.login('10002',PASSWORD)
        self.assertTrue(self.store.has_current_consent(admin));self.assertTrue(self.store.has_current_consent(user))
        self.store.configure_profile(admin,company='合成测试专用章')
        source=self.root/'synthetic.pdf'
        with fitz.open() as pdf:pdf.new_page();pdf.save(source)
        params=dict(page=0,x=420,y=650,size=110)
        rid=self.store.submit(user,source,params)
        self.assertEqual(self.store.request(user,rid)['status'],'pending')
        with self.assertRaises(PermissionError):self.store.approve(user,rid)
        self.store.approve(admin,rid);self.assertTrue(self.store.output(user,rid).exists())
        own=self.store.submit(admin,source,params)
        self.assertEqual(self.store.request(admin,own)['status'],'approved')

    def test_two_first_registrations_exactly_one_admin(self):
        def run(number):return SealStore(self.store.root).register(number,'合成测试',PASSWORD,PASSWORD,True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            roles=list(executor.map(run,['10001','10002']))
        self.assertEqual(sorted(roles),[False,True])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT sum(admin),count(*) FROM users').fetchone()[:],(1,2))
            self.assertEqual(db.execute('SELECT count(*) FROM legal_consents').fetchone()[0],4)

    def test_invalid_registration_leaves_no_account_or_consent(self):
        defaults=dict(user_id='10001',name='合成测试',password=PASSWORD,confirmation=PASSWORD,accepted=True)
        for changes in ({'user_id':'123'},{'user_id':'１０００１'},{'name':''},{'name':'x\ny'},
                        {'password':'short'},{'password':'x'*257},{'confirmation':'different'},
                        {'accepted':False},{'accepted':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.store.register(**dict(defaults,**changes))
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM legal_consents').fetchone()[0],0)

    def test_duplicate_and_failed_consent_transaction_keep_original(self):
        self.register()
        with self.assertRaises(ValueError):self.register()
        with patch.object(self.store,'_record_consent',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):self.register('10002')
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM legal_consents').fetchone()[0],2)

    def test_old_accounts_confirm_without_replacing_credentials(self):
        self.store.setup_admin(PASSWORD,'合成旧管理员','54321')
        token=self.store.login('54321',PASSWORD)
        self.assertFalse(self.store.has_current_consent(token))
        with self.assertRaises(ValueError):self.store.accept_legal(token,False)
        self.store.accept_legal(token,True)
        other=SealStore(self.store.root);restored=other.login('54321',PASSWORD)
        self.assertTrue(other.has_current_consent(restored));self.assertTrue(other.actor(restored)['admin'])
        self.assertFalse(self.register('10002'))
        other.add_user(restored,'10003','合成测试',PASSWORD)
        self.assertFalse(other.has_current_consent(other.login('10003',PASSWORD)))

    def test_version_and_hash_changes_require_confirmation_keep_history(self):
        self.register();token=self.store.login('10001',PASSWORD)
        manifest=legal_manifest()
        with self.store.db() as db:
            rows=db.execute('SELECT * FROM legal_consents').fetchall()
        for row in rows:
            self.assertEqual(row['text_hash'],manifest[row['document']]['hash']);self.assertGreater(row['accepted'],0)
        for key in ('version','hash'):
            changed={name:dict(value) for name,value in manifest.items()}
            changed['service'][key]='synthetic-new-'+key
            with patch('seal_core.legal_manifest',return_value=changed):
                self.assertFalse(self.store.has_current_consent(token))
                self.store.accept_legal(token,True);self.assertTrue(self.store.has_current_consent(token))
        with self.store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM legal_consents').fetchone()[0],4)

    def test_public_policy_ignores_even_existing_valid_restore_and_never_remembers(self):
        self.register();token=self.store.login('10001',PASSWORD)
        cache=Mock();cache.restore.return_value=token
        policy=LoginPolicy(self.store.root,cache)
        self.assertIsNone(policy.restore(self.store));self.assertFalse(policy.remember(self.store,token))
        cache.restore.assert_not_called();cache.remember.assert_not_called()

    def test_old_session_option_cannot_disable_password_requirement(self):
        cache=Mock();cache.restore.return_value='synthetic-token';cache.remember.return_value=True
        settings=self.root/'local-defaults.json'
        for value in (False,'true',1,None):
            settings.write_text(json.dumps({'windows_session_login':value}),encoding='utf-8')
            self.assertIsNone(LoginPolicy(self.store.root,cache).restore(self.store))
        settings.write_text('broken json',encoding='utf-8')
        self.assertFalse(LoginPolicy(self.store.root,cache).windows_session)
        settings.write_text(json.dumps({'windows_session_login':True}),encoding='utf-8')
        policy=LoginPolicy(self.store.root,cache)
        self.assertIsNone(policy.restore(self.store));self.assertFalse(policy.remember(self.store,'token'))
        cache.restore.assert_not_called();cache.remember.assert_not_called()

if __name__=='__main__':unittest.main()
