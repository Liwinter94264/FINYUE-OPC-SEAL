# Rebuild from this directory: python -m PyInstaller --clean --noconfirm OPC盖章.spec
from pathlib import Path
base=Path(SPECPATH)
assets=base/'assets'
notices=[(str(base/'LICENSE'),'.'),(str(base/'THIRD-PARTY-NOTICES.md'),'.'),(str(base/'licenses'),'licenses')]
a=Analysis([str(base/'app.py')],pathex=[str(base)],
    binaries=[],datas=([(str(assets),'assets')] if assets.exists() else [])+notices,
    hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['pandas','numpy','matplotlib','openpyxl','lxml'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='FINYUE-OPC-Seal-1.0.1-Windows-x64',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=False,disable_windowed_traceback=False,
    icon=str(base/'assets'/'app.ico') if (base/'assets'/'app.ico').exists() else None)
