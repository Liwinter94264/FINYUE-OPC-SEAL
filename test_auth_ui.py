"""Hidden Tk widget integration with synthetic accounts; no delivered EXE launch."""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock
from app import App
from seal_core import SealStore
from ui_auth import build_auth

PASSWORD='Synthetic-Only-Password'

class AuthUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.store=SealStore(self.folder/'data');self.root=tk.Tk();self.root.withdraw()
        self.cache=Mock();self.cache.restore.return_value=None
        self.app=App(self.root,self.store,self.cache)

    def tearDown(self):
        self.app.clear();self.root.destroy();self.temp.cleanup()

    def fill_registration(self,number):
        self.app.user.set(number);self.app.display_name.set('合成测试')
        self.app.password.set(PASSWORD);self.app.confirm.set(PASSWORD)
        self.app.legal_accepted.set(True);self.app.auth_submit()

    def test_register_logout_new_applicant_and_reopen_password_login(self):
        self.assertEqual(self.app.user.get(),'00001')
        self.fill_registration(self.app.user.get());self.assertTrue(self.store.actor(self.app.token)['admin'])
        self.assertEqual(self.store.actor(self.app.token)['id'],'00001')
        self.app.logout();build_auth(self.app,'register');self.fill_registration('00002')
        self.assertFalse(self.store.actor(self.app.token)['admin'])
        self.cache.restore.assert_not_called();self.cache.remember.assert_not_called()
        self.app.clear();self.root.destroy();self.root=tk.Tk();self.root.withdraw()
        self.app=App(self.root,SealStore(self.store.root),self.cache)
        self.assertIsNone(self.app.token);self.assertEqual(self.app.auth_button.cget('text'),'登录工作台')
        self.assertEqual(self.app.user.get(),'00001')
        self.app.user.set('00002');self.app.password.set(PASSWORD);self.app.auth_submit()
        self.assertEqual(self.app.store.actor(self.app.token)['id'],'00002')
        self.assertEqual(self.app.password.get(),'')

    def test_old_password_login_gates_workspace_until_consent(self):
        self.store.setup_admin(PASSWORD,'合成旧账号','10001');build_auth(self.app,'login')
        self.assertEqual(self.app.user.get(),'00001')
        self.app.user.set('10001');self.app.password.set(PASSWORD);self.app.auth_submit()
        self.assertEqual(self.store.actor(self.app.token)['id'],'10001')
        with self.store.db() as db:
            self.assertIsNone(db.execute('SELECT id FROM users WHERE id=?',('00001',)).fetchone())
        self.assertIsNotNone(self.app.token);self.assertFalse(self.store.has_current_consent(self.app.token))
        self.assertEqual(self.app.auth_button.cget('text'),'同意并继续')
        self.app.auth_submit();self.assertTrue(self.app.auth_error.get())
        self.app.legal_accepted.set(True);self.app.auth_submit()
        self.assertTrue(self.store.has_current_consent(self.app.token));self.assertTrue(hasattr(self.app,'canvas'))

    def test_old_private_session_still_requires_password_then_consent(self):
        self.store.setup_admin(PASSWORD,'合成旧账号','54321');token=self.store.login('54321',PASSWORD)
        (self.folder/'local-defaults.json').write_text(json.dumps({'windows_session_login':True}),encoding='utf-8')
        self.app.clear();self.root.destroy();self.root=tk.Tk();self.root.withdraw()
        self.cache.restore.return_value=token;self.app=App(self.root,self.store,self.cache)
        self.assertIsNone(self.app.token);self.assertEqual(self.app.auth_button.cget('text'),'登录工作台')
        self.cache.restore.assert_not_called()
        self.app.user.set('54321');self.app.password.set(PASSWORD);self.app.auth_submit()
        self.assertEqual(self.app.auth_button.cget('text'),'同意并继续')
        self.app.legal_accepted.set(True);self.app.auth_submit()
        self.assertTrue(hasattr(self.app,'canvas'));self.cache.remember.assert_not_called()

    def test_login_register_and_consent_geometry_fit_minimum_window(self):
        # Geometry is measured without operating any native app or taking a screenshot.
        for mode in ('login','register','consent'):
            with self.subTest(mode=mode):
                build_auth(self.app,mode);self.root.geometry('1020x680');self.root.update()
                self.assertLessEqual(self.app.auth_shell.winfo_width(),980)
                self.assertLessEqual(self.app.auth_shell.winfo_height(),632)
                for number,text in zip(self.app.auth_rule_numbers,self.app.auth_rule_texts):
                    self.assertLess(number.winfo_rootx(),text.winfo_rootx())
                    self.assertAlmostEqual(number.winfo_rooty(),text.winfo_rooty(),delta=1)
                self.assertEqual(len(set(text.winfo_rootx() for text in self.app.auth_rule_texts)),1)
                self.assertLessEqual(self.app.auth_button.winfo_rooty()+self.app.auth_button.winfo_height(),680)

if __name__=='__main__':unittest.main()
