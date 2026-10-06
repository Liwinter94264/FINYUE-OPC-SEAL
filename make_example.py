"""Create an anonymous PDF locally; has no signature or business effect."""
import sys
from pathlib import Path
import pymupdf as fitz

if __name__=='__main__':
    path=Path(sys.argv[1] if len(sys.argv)>1 else 'example.pdf')
    if path.exists():raise ValueError('Choose a new example filename')
    with fitz.open() as doc:
        page=doc.new_page();page.insert_text((54,72),'OPC PDF WORKSPACE / SYNTHETIC EXAMPLE',fontsize=17)
        page.insert_text((54,118),'For preview and software testing only. No business or legal effect.',fontsize=11)
        page.draw_line((54,140),(540,140),color=(.7,.75,.7))
        page.insert_text((54,190),'1. Add your own seal or signature.\n2. Review the preview.\n3. Export a new copy.',fontsize=12)
        doc.new_page(width=842,height=595).insert_text((54,72),'LANDSCAPE / SECOND PAGE',fontsize=17)
        doc.save(path)
