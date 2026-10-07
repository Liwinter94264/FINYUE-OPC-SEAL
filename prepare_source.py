"""Allowlisted standalone source archive. Never packages a database or local files."""
import argparse,hashlib,json,zipfile
from pathlib import Path

FILES=('app.py','seal_core.py','local_session.py','signatures.py','text_layer.py',
       'ui_theme.py','ui_layout.py','ui_auth.py','ui_signature.py','login_policy.py','legal_text.py','release_info.py',
       'requirements.txt','OPC盖章.spec','README.md',
       'test_seal_core.py','test_signature_session.py','test_export_undo.py','test_profile.py',
       'test_registration.py','test_auth_ui.py','test_handwriting_ui.py','prepare_source.py','make_example.py',
       'LICENSE','COPYRIGHT.md','SECURITY.md','.gitignore','.gitattributes','UPSTREAM-SOURCES.json',
       'THIRD-PARTY-NOTICES.md','assets/auth-decoration-v1.png',
       'assets/auth-decoration-v1.source.json')
LICENSES=('Tk-license.terms','Python-LICENSE.txt','PyMuPDF-COPYING','Pillow-LICENSE',
          'pyinstaller-COPYING.txt','pyinstaller-hooks-contrib-LICENSE','altgraph-LICENSE',
          'packaging-LICENSE','packaging-LICENSE.APACHE','packaging-LICENSE.BSD',
          'pefile-LICENSE','pywin32-ctypes-LICENSE.txt','setuptools-LICENSE')

def prepare(target,forbidden=()):
    base=Path(__file__).resolve().parent;target=Path(target)
    if target.exists():raise ValueError('Refuse to overwrite an existing source archive')
    entries={name:(base/name).read_bytes() for name in FILES}
    for name,data in entries.items():
        if not name.endswith('.png'):
            entries[name]=data.replace(b'\r\n',b'\n')
    entries.update({'licenses/'+name.name:name.read_bytes() for name in sorted((base/'licenses').glob('*')) if name.is_file()})
    # Built in surname/identity or local deployment details must never ship.
    for name,data in entries.items():
        for term in forbidden:
            if term.encode() in data:raise ValueError(f'Private identifier detected in {name}')
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in entries.items()}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in entries.items():archive.writestr('opc-seal/'+name,data)
        archive.writestr('opc-seal/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False))
    with zipfile.ZipFile(target) as archive:
        assert len(archive.namelist())==len(entries)+1 and archive.testzip() is None
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--private-terms');args=parser.parse_args()
    forbidden=Path(args.private_terms).read_text(encoding='utf-8').splitlines() if args.private_terms else ()
    manifest=prepare(args.output,[term for term in forbidden if term]);print(json.dumps({'files':len(manifest),'brandAssets':False,'localData':False}))
