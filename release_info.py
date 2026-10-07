"""Public product identity. Contains no account, credential or local settings."""
from pathlib import Path

VERSION = '1.0.1'
PRODUCT = 'FINYUE · OPC盖章'
PUBLISHER = '凛野（北京）文化传媒有限公司'
REPOSITORY = 'https://github.com/Liwinter94264/FINYUE-OPC-SEAL'
SUPPORT = REPOSITORY + '/issues'
WEBSITE = 'https://finyue.com/products/opc-seal'

def license_documents():
    base = Path(__file__).resolve().parent
    documents = {}
    for key, title, path in (
        ('license', '开源许可', base / 'LICENSE'),
        ('third-party', '第三方许可', base / 'THIRD-PARTY-NOTICES.md'),
    ):
        try:
            body = path.read_text(encoding='utf-8')
        except OSError:
            body = '许可文件缺失，请从官方对应源码中查阅：' + REPOSITORY
        if key == 'third-party':
            for notice in sorted((base / 'licenses').glob('*')):
                if notice.is_file():
                    body += '\n\n' + '=' * 40 + '\n' + notice.name + '\n\n' + notice.read_text(encoding='utf-8')
        documents[key] = (title, body)
    return documents
