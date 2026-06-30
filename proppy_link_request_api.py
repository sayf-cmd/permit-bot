class _DisabledResult:
    def __await__(self):
        async def _coro():
            return None
        return _coro().__await__()

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __str__(self):
        return ""

    def get(self, key, default=None):
        return default

    def items(self):
        return []

    def keys(self):
        return []

    def values(self):
        return []


def _disabled(*args, **kwargs):
    return _DisabledResult()


def search_proppy_link_request_data(*args, **kwargs):
    return _disabled(*args, **kwargs)

def format_proppy_data(*args, **kwargs):
    return _disabled(*args, **kwargs)


def __getattr__(name):
    return _disabled
