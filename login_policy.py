"""Every launch requires a password, including upgrades with old local settings."""

class LoginPolicy:
    def __init__(self, root, cache):
        self.cache = cache
        self.windows_session = False

    def restore(self, store):
        return None

    def remember(self, store, token):
        return False

    @property
    def description(self):
        return '每次打开均需密码登录，不保存自动登录凭据。'
