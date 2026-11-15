"""
Short-lived reuse of the Sigma ACCESS TOKEN (never the Client ID / Secret) for up to 1 hour.

Storage: Windows Credential Manager, generic credential "sigma-yaml-skill:<host>", persisted only for the
current Windows LOGON SESSION (CRED_PERSIST_SESSION): encrypted by Windows, readable only by the same Windows user,
gone at sign-out. The token carries its own expiry; an expired or rejected token is deleted and the user signs in again.
On non-Windows systems nothing is cached (always sign in).
Standard library only (ctypes).
"""
import json
import sys
import time

MAX_AGE = 3600          # never reuse a token for more than 1 hour
SAFETY = 120            # drop it 2 minutes before it expires

_OK = sys.platform == "win32"
if _OK:
    import ctypes
    from ctypes import wintypes

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_SESSION = 1

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _adv.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
    _adv.CredWriteW.restype = wintypes.BOOL
    _adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
    _adv.CredReadW.restype = wintypes.BOOL
    _adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    _adv.CredDeleteW.restype = wintypes.BOOL
    _adv.CredFree.argtypes = [ctypes.c_void_p]
    _adv.CredFree.restype = None


def _target(host):
    return f"sigma-yaml-skill:{host}"


def save(host, token, expires_in):
    if not _OK or not token:
        return False
    ttl = min(int(expires_in or MAX_AGE), MAX_AGE) - SAFETY
    if ttl <= 0:
        return False
    blob = json.dumps({"token": token, "expires_at": time.time() + ttl}).encode("utf-8")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = _CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=_target(host), CredentialBlobSize=len(blob),
                       CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                       Persist=CRED_PERSIST_SESSION, UserName="sigma-access-token")
    ok = bool(_adv.CredWriteW(ctypes.byref(cred), 0))
    ctypes.memset(buf, 0, len(blob))
    return ok


def load(host):
    """Return a still-valid token or None (expired entries are deleted)."""
    if not _OK:
        return None
    p = ctypes.POINTER(_CREDENTIAL)()
    if not _adv.CredReadW(_target(host), CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        return None
    try:
        raw = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
    finally:
        _adv.CredFree(p)
    try:
        d = json.loads(raw.decode("utf-8"))
    except ValueError:
        clear(host)
        return None
    if time.time() >= float(d.get("expires_at", 0)):
        clear(host)
        return None
    return d.get("token")


def remaining(host):
    """Seconds left on the cached token (0 if none) - for messages only."""
    if not _OK:
        return 0
    p = ctypes.POINTER(_CREDENTIAL)()
    if not _adv.CredReadW(_target(host), CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        return 0
    try:
        d = json.loads(ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize).decode("utf-8"))
    except ValueError:
        return 0
    finally:
        _adv.CredFree(p)
    return max(0, int(float(d.get("expires_at", 0)) - time.time()))


def clear(host):
    if _OK:
        _adv.CredDeleteW(_target(host), CRED_TYPE_GENERIC, 0)
