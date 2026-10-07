"""Hidden Tk integration; synthetic strokes and temporary accounts only."""
import tempfile, tkinter as tk, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app import App
from seal_core import SealStore, ADMIN_ID

class HandwritingUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=SealStore(Path(self.temp.name)/'data')
        self.store.setup_admin('Synthetic-Only-Password')
        self.root=tk.Tk();self.root.withdraw();self.app=App(self.root,self.store,Mock())
        self.app.token=self.store.login(ADMIN_ID,'Synthetic-Only-Password')
        self.store.accept_legal(self.app.token,True);self.app.show_main()

    def tearDown(self):
        self.app.clear();self.root.destroy();self.temp.cleanup()

    def count(self):
        with self.store.db() as db:return db.execute('SELECT COUNT(*) FROM signatures').fetchone()[0]

    def stroke(self,pad,offset=0):
        pad.start(SimpleNamespace(x=41+offset,y=121))
        for x,y in [(81,41),(121,131),(191,51),(241,121)]:pad.move(SimpleNamespace(x=x+offset,y=y))
        pad.end()

    def test_blank_cancel_clear_and_undo_do_not_persist(self):
        self.app.make_signature();pad=self.app.signature_pad
        self.assertEqual(str(pad.save_button.cget('state')),'disabled')
        with patch('ui_signature.messagebox.showerror') as error:pad.save();self.assertTrue(error.called)
        self.assertEqual(self.count(),0)
        self.stroke(pad);self.stroke(pad,250);pad.undo();self.assertEqual(len(pad.strokes),1)
        pad.clear();self.assertFalse(pad.strokes);self.assertEqual(pad.point_count,0)
        self.stroke(pad);pad.close();self.assertEqual(self.count(),0)
        self.assertIsNone(self.app.signature_asset)

    def test_save_selects_asset_and_reopen_reuses_same_ink(self):
        self.app.make_signature();pad=self.app.signature_pad;self.stroke(pad)
        pad.save();self.assertFalse(pad.window.winfo_exists());self.assertEqual(self.count(),1)
        asset=self.app.signature_asset;data=self.app.signature_png
        self.assertTrue(self.app.sig_enabled.get());self.assertEqual(self.app.placement.get(),'signature')
        self.app.show_main();self.assertEqual(self.app.signature_asset,asset);self.assertEqual(self.app.signature_png,data)
        self.app.make_signature();self.app.signature_pad.close()
        self.assertEqual(self.app.signature_asset,asset);self.assertEqual(self.count(),1)

    def test_pad_geometry_and_leave_reenter_do_not_connect_strokes(self):
        self.app.make_signature();pad=self.app.signature_pad;pad.window.update_idletasks()
        self.assertLessEqual(pad.window.winfo_reqwidth(),760);self.assertLessEqual(pad.window.winfo_reqheight(),520)
        self.assertEqual(pad.canvas.cget('bg'),'#ffffff')
        pad.start(SimpleNamespace(x=50,y=60));pad.move(SimpleNamespace(x=100,y=80))
        pad.move(SimpleNamespace(x=-10,y=80));pad.move(SimpleNamespace(x=300,y=80));pad.end()
        self.assertEqual(len(pad.strokes),2)
        self.assertEqual(pad.strokes[0][-1],(99,79));self.assertEqual(pad.strokes[1][0],(299,79))

    def test_review_cannot_open_pad_or_replace_signature(self):
        self.app.selected='synthetic-request'
        with patch('app.messagebox.showerror') as error:self.app.make_signature();self.assertTrue(error.called)
        self.assertFalse(hasattr(self.app,'signature_pad'));self.assertEqual(self.count(),0)

if __name__=='__main__':unittest.main()
