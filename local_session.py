"""Windows logon-scoped, DPAPI-protected app session. Never stores a password."""
import ctypes, json, os, uuid
from ctypes import wintypes as wt

def windows_context():
    if os.name!='nt':return None
    class LUID(ctypes.Structure):
        _fields_=[('low',wt.DWORD),('high',wt.LONG)]
    class Stats(ctypes.Structure):
        _fields_=[('token',LUID),('auth',LUID),('expires',ctypes.c_longlong),
                  ('kind',wt.DWORD),('level',wt.DWORD),('charged',wt.DWORD),
                  ('available',wt.DWORD),('groups',wt.DWORD),('privileges',wt.DWORD),('modified',LUID)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    advapi=ctypes.WinDLL('advapi32',use_last_error=True)
    ntdll=ctypes.WinDLL('ntdll')
    kernel.GetCurrentProcess.restype=wt.HANDLE
    kernel.CloseHandle.argtypes=[wt.HANDLE]
    advapi.OpenProcessToken.argtypes=[wt.HANDLE,wt.DWORD,ctypes.POINTER(wt.HANDLE)]
    advapi.GetTokenInformation.argtypes=[wt.HANDLE,ctypes.c_int,ctypes.c_void_p,wt.DWORD,ctypes.POINTER(wt.DWORD)]
    handle=wt.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(handle)):return None
    try:
        stats=Stats();returned=wt.DWORD()
        if not advapi.GetTokenInformation(handle,10,ctypes.byref(stats),ctypes.sizeof(stats),ctypes.byref(returned)):return None
    finally:kernel.CloseHandle(handle)
    boot=ctypes.create_string_buffer(64)
    ntdll.NtQuerySystemInformation.argtypes=[ctypes.c_int,ctypes.c_void_p,wt.ULONG,ctypes.POINTER(wt.ULONG)]
    ntdll.NtQuerySystemInformation.restype=wt.LONG
    if ntdll.NtQuerySystemInformation(90,boot,len(boot),None)<0:return None
    boot_id=uuid.UUID(bytes_le=boot.raw[:16])
    if boot_id.int==0:return None
    return f'{boot_id}:{stats.auth.high}:{stats.auth.low}'

def protect(data,decode=False):
    if os.name!='nt':raise OSError('会话保存仅支持Windows。')
    class Blob(ctypes.Structure):
        _fields_=[('size',wt.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    crypto=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32')
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    buf=ctypes.create_string_buffer(data);entropy_buf=ctypes.create_string_buffer(b'finyue-local-seal-session-v2')
    source=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)))
    entropy=Blob(len(entropy_buf)-1,ctypes.cast(entropy_buf,ctypes.POINTER(ctypes.c_ubyte)));output=Blob()
    fn=crypto.CryptUnprotectData if decode else crypto.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wt.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wt.BOOL
    if not fn(ctypes.byref(source),None,ctypes.byref(entropy),None,None,1,ctypes.byref(output)):
        raise OSError('Windows会话保护失败。')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(output.data)

class SessionCache:
    def __init__(self,path,context=windows_context,codec=protect):
        self.path=path;self.context=context;self.codec=codec

    def remember(self,store,token):
        context=self.context()
        if not context:return False
        secret=store.remember_session(token,context)
        try:
            data=self.codec(json.dumps({'context':context,'secret':secret}).encode())
            temp=self.path.with_suffix('.tmp');temp.write_bytes(data);os.replace(temp,self.path)
        except Exception:
            store.revoke_remembered(secret);raise
        return True

    def restore(self,store):
        try:
            context=self.context()
            if not context or not self.path.exists():return None
            if self.path.stat().st_size>16384:raise ValueError('会话文件无效。')
            data=json.loads(self.codec(self.path.read_bytes(),decode=True))
            if data['context']!=context:raise ValueError('Windows会话已结束。')
            return store.restore_session(data['secret'],context)
        except (OSError,ValueError,KeyError,TypeError,PermissionError):
            self.clear();return None

    def clear(self):self.path.unlink(missing_ok=True)
