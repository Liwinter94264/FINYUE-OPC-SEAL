"""Regression tests for real GUI callbacks and export/withdraw lifecycle, synthetic data only."""
import concurrent.futures, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import pymupdf as fitz
from app import App
from seal_core import SealStore, ADMIN_ID, digest

class ExportUndoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=SealStore(self.root/'data');self.store.setup_admin('Synthetic-Only-Password')
        self.admin=self.store.login(ADMIN_ID,'Synthetic-Only-Password')
        self.store.accept_legal(self.admin,True)
        self.store.configure_profile(self.admin,company='合成测试专用章')
        self.store.add_user(self.admin,'00002','合成用户','Synthetic-Only-Password')
        self.user=self.store.login('00002','Synthetic-Only-Password')
        self.source=self.root/'测试.pdf'
        with fitz.open() as d:d.new_page();d.save(self.source)
        self.params=dict(page=0,x=420,y=680,size=110)

    def tearDown(self):self.temp.cleanup()

    def approved(self):return self.store.submit(self.admin,self.source,self.params)

    def test_default_export_creates_unique_verified_copies_beside_source(self):
        rid=self.approved();before=self.source.read_bytes()
        one=self.store.export_copy(self.admin,rid);two=self.store.export_copy(self.admin,rid)
        self.assertEqual(one.parent,self.source.parent.resolve());self.assertNotEqual(one,two)
        self.assertEqual(digest(one.read_bytes()),self.store.request(self.admin,rid)['output_hash'])
        self.assertEqual(one.read_bytes(),two.read_bytes());self.assertEqual(before,self.source.read_bytes())
        self.source.unlink();self.source.parent.joinpath('missing').mkdir()
        with self.store.db() as db:db.execute('UPDATE requests SET source_path=? WHERE id=?',(str(self.root/'missing2'/'old.pdf'),rid))
        fallback=self.store.export_copy(self.admin,rid)
        self.assertEqual(fallback.parent,(self.store.root.parent/'导出副本').resolve())

    def test_existing_file_hardlink_and_internal_target_are_not_overwritten(self):
        rid=self.approved();existing=self.root/'existing.pdf';existing.write_bytes(b'keep existing')
        for target in (existing,self.source,self.store.root/'bad.pdf'):
            with self.assertRaises(ValueError):self.store.export(self.admin,rid,target)
        self.assertEqual(existing.read_bytes(),b'keep existing')
        link=self.root/'hardlink.pdf';link.hardlink_to(self.source);original=self.source.read_bytes()
        with self.assertRaises(ValueError):self.store.export(self.admin,rid,link)
        self.assertEqual(self.source.read_bytes(),original)

    def test_withdraw_pending_owner_permissions_and_final_state(self):
        rid=self.store.submit(self.user,self.source,self.params)
        with self.assertRaises(ValueError):self.store.withdraw(self.user,rid,' ')
        self.assertEqual(self.store.withdraw(self.user,rid,'内容需要修改'),'withdrawn')
        for action in (lambda:self.store.approve(self.admin,rid),lambda:self.store.withdraw(self.admin,rid,'重复'),lambda:self.store.export_copy(self.admin,rid)):
            with self.assertRaises(ValueError):action()
        other=self.approved()
        with self.assertRaises(PermissionError):self.store.withdraw(self.user,other,'无权限')

    def test_revoke_preserves_original_output_audit_and_previously_exported_copy(self):
        rid=self.store.submit(self.user,self.source,self.params);self.store.approve(self.admin,rid)
        with self.assertRaises(PermissionError):self.store.withdraw(self.user,rid,'需要管理员')
        output=self.store.output(self.admin,rid);before=output.read_bytes();copy_path=self.store.export_copy(self.user,rid)
        self.assertEqual(self.store.withdraw(self.admin,rid,'测试作废'),'revoked')
        row=self.store.request(self.admin,rid)
        self.assertIsNotNone(row['reviewer']);self.assertIsNotNone(row['reviewed'])
        self.assertEqual(output.read_bytes(),before);self.assertEqual(copy_path.read_bytes(),before)
        self.assertEqual(self.store.original(self.admin,rid),self.source.read_bytes())
        with self.assertRaises(ValueError):self.store.export_copy(self.admin,rid)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM audit WHERE action=? AND request_id=?',('revoke_approval',rid)).fetchone()[0],1)

    def test_concurrent_revoke_and_export_leave_consistent_history(self):
        rid=self.approved();target=self.root/'racing.pdf'
        def export():
            try:self.store.export(self.admin,rid,target);return 'exported'
            except ValueError:return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(export);pool.submit(self.store.withdraw,self.admin,rid,'测试作废').result();result=future.result()
        self.assertEqual(target.exists(),result=='exported')
        with self.assertRaises(ValueError):self.store.export(self.admin,rid,self.root/'after.pdf')

    def test_gui_export_callback_and_edit_undo_and_revoke_callback(self):
        gui=tk.Tk();gui.withdraw()
        try:
            app=App(gui,self.store);app.token=self.admin;app.show_main()
            app.source=self.source;app.load(self.source.read_bytes())
            original_position=app.position
            app.position=(40,50);app.marker();self.assertTrue(app.undo_stack)
            app.undo();self.assertEqual(app.position,original_position)
            app.labels=[dict(text='测试日期',page=0,x=30,y=30,font_size=12)];app.marker()
            app.undo();self.assertEqual(app.labels,[])
            asset=self.store.create_signature(self.admin,name='合成测试')
            with patch('app.tk.Toplevel') as preview,patch('app.ttk.Label'),patch('app.ttk.Button'):
                app.set_signature(asset)
            self.assertTrue(app.sig_enabled.get());app.undo();self.assertFalse(app.sig_enabled.get())
            rid=self.approved();app.refresh();app.selected=rid;app.load(self.store.output(self.admin,rid).read_bytes(),self.params)
            with patch('app.messagebox.showinfo') as success,patch('app.messagebox.showerror') as error:
                app.export();error.assert_not_called();success.assert_called_once()
            with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM audit WHERE action=? AND request_id=?',('export',rid)).fetchone()[0],1)
            self.assertTrue(app.export_info.get().startswith('已导出：'))
            self.assertFalse(app.undo_stack)
            with patch('app.simpledialog.askstring',return_value='测试作废'),patch('app.messagebox.askyesno',return_value=True),patch('app.messagebox.showerror') as error:
                app.withdraw();error.assert_not_called()
            self.assertEqual(app.rows[rid]['status'],'revoked')
            self.assertEqual(str(app.export_button['state']),'disabled')
            gui.update()
        finally:app.clear();gui.destroy()

    def test_zoom_and_scroll_clicks_match_exported_rotated_page(self):
        from types import SimpleNamespace
        gui=tk.Tk();gui.withdraw()
        try:
            app=App(gui,self.store);app.token=self.admin;app.show_main()
            with fitz.open() as doc:
                page=doc.new_page(width=400,height=600);page.set_rotation(90);data=doc.tobytes()
            app.source=self.source;app.load(data)
            for zoom in ('适合宽度','75%','150%'):
                app.zoom.set(zoom);app.draw();app.canvas.yview_moveto(.3);app.canvas.xview_moveto(.2)
                x,y=120,130
                cx=app.preview_offset+(x+app.diameter()/2)*app.scale-app.canvas.canvasx(0)
                cy=16+(y+app.diameter()/2)*app.scale-app.canvas.canvasy(0)
                with patch('app.messagebox.showerror') as errors:
                    app.place(SimpleNamespace(x=round(cx),y=round(cy)));errors.assert_not_called()
                self.assertAlmostEqual(app.position[0],x,delta=1.5/app.scale)
                self.assertAlmostEqual(app.position[1],y,delta=1.5/app.scale)
                SealStore.check_position(data,app.params())
        finally:app.clear();gui.destroy()

    def test_bottom_right_enables_seal_places_it_and_scrolls_into_view(self):
        gui=tk.Tk();gui.withdraw()
        try:
            app=App(gui,self.store);app.token=self.admin;app.show_main()
            self.assertEqual(str(app.bottom_right_button['state']),'disabled')
            app.source=self.source;app.load(self.source.read_bytes());app.position=(20,30)
            app.seal_enabled.set(False);app.zoom.set('150%');app.draw();app.reset_history()
            with patch('app.messagebox.showerror') as error:
                app.bottom_right();error.assert_not_called()
            size=app.diameter();page=app.pdf[app.page]
            self.assertAlmostEqual(app.position[0],page.rect.width-size-24)
            self.assertAlmostEqual(app.position[1],page.rect.height-size-24)
            self.assertTrue(app.seal_enabled.get());self.assertTrue(app.canvas.find_withtag('seal'))
            self.assertGreater(app.canvas.yview()[0],0)
            self.assertIn('右下角',app.export_info.get());self.assertTrue(app.undo_stack)
            app.undo();self.assertEqual(app.position,(20,30));self.assertFalse(app.seal_enabled.get())
        finally:app.clear();gui.destroy()

    def test_approved_position_controls_disabled_and_direct_action_explains(self):
        gui=tk.Tk();gui.withdraw()
        try:
            app=App(gui,self.store);app.token=self.admin;app.show_main()
            rid=self.approved();before=self.store.output(self.admin,rid).read_bytes()
            app.refresh();app.tree.selection_set(rid);app.select_request(None)
            position=app.position
            for widget in (app.bottom_right_button,app.seal_size_input,app.signature_size_input,app.text_size_input):
                self.assertEqual(str(widget['state']),'disabled')
            self.assertIn('已固定',app.editor_hint.get())
            with patch('app.messagebox.showerror') as error:
                app.bottom_right();error.assert_called_once()
            self.assertEqual(app.position,position);self.assertEqual(self.store.output(self.admin,rid).read_bytes(),before)
        finally:app.clear();gui.destroy()

    def test_reviewer_can_place_pending_seal_but_applicant_cannot(self):
        rid=self.store.submit(self.user,self.source,self.params)
        gui=tk.Tk();gui.withdraw()
        try:
            app=App(gui,self.store);app.token=self.admin;app.show_main()
            app.tree.selection_set(rid);app.select_request(None)
            self.assertEqual(str(app.bottom_right_button['state']),'normal')
            with patch('app.messagebox.showerror') as error:app.bottom_right();error.assert_not_called()
            self.store.reposition(self.admin,rid,app.params())
            self.store.accept_legal(self.user,True);app.token=self.user;app.show_main()
            app.tree.selection_set(rid);app.select_request(None)
            self.assertEqual(str(app.bottom_right_button['state']),'disabled')
            self.assertIn('不能改动',app.editor_hint.get())
        finally:app.clear();gui.destroy()

if __name__=='__main__':unittest.main()
