"""
Access codes for LowCore's experimental features (1-use only).

Preserves all 50 SHA-256 hashes from LowCore's code generator (SALT = "lowcore-experimental-v1:"),
adds local permanent 1-use consumption tracking (config + ~/.lowcorelauncher/.consumed_codes.json
+ Windows Registry fallback), and supports global cross-PC 1-use atomic claiming via:
  1. Firebase Firestore REST API (set FIREBASE_PROJECT_ID — zero backend server required), OR
  2. Any HTTPS claim endpoint (set LICENSE_API_URL).
"""
import hashlib
import json
import os
import re
import sys
import time
import uuid
from typing import Iterable, Tuple

SALT = "lowcore-experimental-v1:"          # must match tools/make_codes.py
CONFIG_KEY = "experimental_license"
REVOKED_KEY = "revoked_licenses"
CONSUMED_KEY = "consumed_licenses"

# ---------------------------------------------------------------------------
# Cross-PC 1-Use Enforcement Configuration
# ---------------------------------------------------------------------------
# Option A (Zero backend server): Create a free Firebase project with Firestore,
# paste its Project ID below, and add the 1-use Firestore security rule shown
# in the LowCore Setup Guide. Every redeemed code becomes atomically claimed
# across all friends' PCs.
FIREBASE_PROJECT_ID = ""
FIREBASE_COLLECTION = "redeemed_codes"

# Option B (Custom HTTPS server / Cloudflare Worker): Receives JSON POST:
# {"hash": "<sha256>", "machine_id": "<id>", "ts": 1234567890}
# Should return HTTP 200/201 on first claim, HTTP 409/410 if already claimed.
LICENSE_API_URL = ""

CODE_HASHES = frozenset({
    "f95f1cd2f63cfc3bd475c4350ea0cd5b109cbf7ff7d94c64edaeff6af56b6cef",
    "3c1ba5b937a9764c1ec77418d19595e5b9594ed2f335b030e1f9e9fb2da1617d",
    "a88cd05850ace726fc098a9b4f7102e2537f63a8bf572e9b6f14139f3691a444",
    "0d07007ad5ad2a750669842d8f1ca74760661a9e0f44f06172f99ff6bcf05d5f",
    "afff8341731ba54c91c3b6b110d2f67b313ce6384f3770807820b3dd20d40c3f",
    "3860b036b114d315ad92ab1cf9be1a72afa0b9175bed721017fed5338497b729",
    "98fe274a18fe1c8a6d4f67926494f6ffdaeec795cc1f8856a2a700803fdadcd5",
    "158a21fb124d7e234f6b09c5ba8b3d7615c35dec1638b7de4f1ffd1a591d2b3f",
    "3109a3c0873554207061b6283e2f3a0e4b2c0d4d828a099af7f3a64ecf5dc297",
    "a23d89b7cbf4ded532f02f10d25da0c83041d415c57980b6828f459f6f0d493b",
    "d23f5329e646c861d717bb4df0c5bb61a2be27d1b0b99f45ef2f822f1158a654",
    "7207937cf5264a2eafeb43996d37b3634cab23c5d681e6fe3e4c1f7280d375c2",
    "a43495a66c33be6f066c5bc39c54bc1d16a41bc41b989af04a446c0cad349a15",
    "66e17ffd316a503c199f1d04456d0bd702486088fa64d79ee0c0232b0de15c22",
    "7ab604c84fbb471d5a8abd8942c642e2d88c879dfc5b3d8c56f39be21b339eac",
    "b02c96f43721da437bc155fb4f9473bc25bfbf7e020176c315e1200c18e8511a",
    "a52e5266208a3e7cd1c3fa66eda9f58fcac54b8a0cbfd533c1a7f6775b0876fb",
    "13d75f17aa9e1043052b447677e166eca7a097989754260c3d43f512a0a56ad7",
    "18a7ad651256431df5de903c5c6ce3bfa76bf3a49748ecffc3f854d36c2b9585",
    "2154f1dce73b8d3c66e6435ab61e56ae6d15bc31459cd869c3b8734d55141b51",
    "b78b4e570526e7bd97fcea166da1c60e1958087fccabe606a3bf7b20aa39cd68",
    "f5d6af4f650676da69608314614702fc6af1586131284bef3f22ab8f7a2af33a",
    "2bcc8cbe8af48223a6827116500781f13ce3d077d63828fdb79470e2b6436091",
    "ff7bdf3431b42700fa2a978342608663c7f2dc4cde5c8e13d1ba1520d05d1893",
    "9bde0ce4d5151e9efb982fc00e3636d61de877670a320975f08e7173550cbaae",
    "424971807de0f54fa6f2b3fbf17f04e43d548875e6ae80b4d1d45bf9d4a93853",
    "f80e06a4408053c2e5934007796aba2c7518d93b230fc8787db69ac7439909e7",
    "bd16aaca375575cdadfae93e9153474bee95058ba3c97c8dd5c5a810fe9a150e",
    "749179c44a6866a8abf98149a8ac7949cf5e8d6accbb84af3179a47bf93ea326",
    "7a4e997fc5b6a62866d3f541df24961657d71dd428e1bc360b9dbc09f68cba1c",
    "0c303b01728a9683e1faa41ed62f25247fa684f4b9a916282236034a3a6ebdce",
    "3f47a1ddcc293ba08178a6ac59bebc5efbc6eeca901004697c2ae1ebff329e17",
    "22f5519d9f35b06a8fa394acd23704c1b6aa449aa1ee158c554dcf12e9449f71",
    "712f092ac41b6b3e7db803fe182710e10bd8d5c74cc6dd5355b716171182e8cc",
    "ad65a40f0e9ad9bcba55a55f62098419b5a8687edb3d0c2b9cace508cce9a982",
    "f1cb29d3de99c2df0eb334c415b96a49f04bfe865f780ca69b5f1e4ffb196e6f",
    "33a4ebd9386628876c6da56a4234e50969a0837b1e53cbc93b7b4d8a33ecac76",
    "c29b8b3c400dcc518ad5b4c5719f5e00e0ca09c6d8841c4b80b8e3c773ac1ebe",
    "6009b33a4f278e705afd1be4bbe310aa187f664465dd146390de2002005b2452",
    "5ed9259354cf429d029120396ca5508e8fce461410d8b1178510b43589f9a883",
    "3278bdabeb8bd6b362b69bcb3bb7aad68752619770bce239a142c0b6249382e9",
    "b07b5ddf5d562198dc9fa6b9325bccc609ab2bb82a00b013f38968beb9f644dd",
    "140190d6383d60738c7495327b8ffaa604fff026a58eb6fcdc68768df7e141c9",
    "41997b3a473f58325540016eae5ca480ff99d521c7b1f8983f9b59d138bac07c",
    "66e0e76bd34ee5c721327421a83fe67ab5a229ed2ce6c12e98364dc28a1715f0",
    "d6fde87d038b0e14fb5dd94f46babb8992523c1d57214336118eff744996ce5b",
    "a5f4851807c537cd99d29b9ba5d2a2ec8e141371c17d49fa5ecdeacd53c9d283",
    "2f0e3e70814709d185554f7c94887da4dd9e6988b7238cdd1650602381b1d1dd",
    "5d006b99b3ceb98a7b0825d21d9c22670226ea62945c1abe4e551c4622360684",
    "3be716586e4b95bf5be85d266098d4e0c0c4172c957062f12e91d1403f4f454c",
})


def normalize_code(code: str) -> str:
    """Upper-case, drop dashes/spaces, optional LCX prefix, and fix look-alikes (O->0, I/L->1)."""
    n = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    if n.startswith("LCX") and len(n) == 18:
        n = n[3:]
    return n.translate(str.maketrans("OIL", "011"))


def code_hash(code: str) -> str:
    return hashlib.sha256((SALT + normalize_code(code)).encode("utf-8")).hexdigest()


def get_machine_id() -> str:
    """Deterministic hardware/OS fingerprint hashed for anonymous 1-use claiming."""
    raw_parts = [str(uuid.getnode())]
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                if val:
                    raw_parts.append(str(val))
        elif os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r", encoding="utf-8") as f:
                raw_parts.append(f.read().strip())
    except Exception:
        pass
    return hashlib.sha256(("lowcore-machine:" + "|".join(raw_parts)).encode("utf-8")).hexdigest()[:32]


class LicenseManager:
    def __init__(self, config):
        self.config = config

    def _ledger_path(self) -> str:
        cfg_dir = getattr(self.config, "config_dir", os.path.join(os.path.expanduser("~"), ".lowcorelauncher"))
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, ".consumed_codes.json")

    def _read_ledger(self) -> set:
        used = set()
        cfg_used = self.config.get(CONSUMED_KEY, [])
        if isinstance(cfg_used, list):
            used.update(str(x).lower() for x in cfg_used if isinstance(x, str))
        p = self._ledger_path()
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        used.update(str(x).lower() for x in data if isinstance(x, str))
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\LowCoreClient") as key:
                    val, _ = winreg.QueryValueEx(key, "UsedCodeHashes")
                    if isinstance(val, str) and val:
                        used.update(x.strip().lower() for x in val.split(",") if x.strip())
            except Exception:
                pass
        return used

    def _record_consumed(self, h: str):
        h = str(h or "").lower()
        if not h:
            return
        used = sorted(self._read_ledger() | {h})
        self.config.set(CONSUMED_KEY, used)
        try:
            with open(self._ledger_path(), "w", encoding="utf-8") as f:
                json.dump(used, f)
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\LowCoreClient") as key:
                    winreg.SetValueEx(key, "UsedCodeHashes", 0, winreg.REG_SZ, ",".join(used))
            except Exception:
                pass

    def _revoked(self) -> set:
        value = self.config.get(REVOKED_KEY, [])
        return set(value) if isinstance(value, list) else set()

    def _stored_hash(self) -> str:
        data = self.config.get(CONFIG_KEY, {})
        return data.get("hash", "") if isinstance(data, dict) else ""

    def is_unlocked(self) -> bool:
        """Re-checked against valid hashes and active/revoked status every time."""
        h = self._stored_hash()
        return bool(h) and h in CODE_HASHES and h not in self._revoked()

    def redeemed_at(self) -> int:
        data = self.config.get(CONFIG_KEY, {})
        return int(data.get("redeemed_at", 0)) if isinstance(data, dict) else 0

    def _claim_online(self, h: str) -> Tuple[bool, str]:
        """Atomically claim a 1-use code across PCs if a backend or Firebase project is configured."""
        mid = get_machine_id()
        now = int(time.time())

        if LICENSE_API_URL:
            import requests
            try:
                res = requests.post(
                    LICENSE_API_URL,
                    json={"hash": h, "machine_id": mid, "ts": now},
                    timeout=8,
                )
            except Exception as e:
                return False, f"Could not verify 1-use code online (check your internet connection): {e}"
            if res.status_code in (200, 201):
                return True, ""
            if res.status_code in (409, 410):
                self._record_consumed(h)
                return False, "This access code has already been redeemed on another PC (1-use only)."
            try:
                err_msg = (res.json() or {}).get("error")
            except Exception:
                err_msg = None
            return False, err_msg or f"License server rejected the code (HTTP {res.status_code})."

        if FIREBASE_PROJECT_ID:
            import requests
            url = (
                f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID.strip()}"
                f"/databases/(default)/documents/{FIREBASE_COLLECTION}?documentId={h}"
            )
            payload = {
                "fields": {
                    "machine_id": {"stringValue": mid},
                    "redeemed_at": {"integerValue": str(now)},
                }
            }
            try:
                res = requests.post(url, json=payload, timeout=8)
            except Exception as e:
                return False, f"Could not verify 1-use code online (check your internet connection): {e}"
            if res.status_code == 200:
                return True, ""
            if res.status_code == 409:
                self._record_consumed(h)
                return False, "This access code has already been redeemed on another PC (1-use only)."
            return False, f"Could not claim access code (HTTP {res.status_code})."

        return True, ""

    def redeem(self, code: str) -> Tuple[bool, str]:
        body = normalize_code(code)
        if len(body) != 15:
            return False, "That doesn't look like a full code. It should look like LCX-XXXXX-XXXXX-XXXXX."
        h = hashlib.sha256((SALT + body).encode("utf-8")).hexdigest()
        if h in self._revoked():
            return False, "This code has been disabled. Contact support if you think that's a mistake."
        if h not in CODE_HASHES:
            return False, "That code isn't valid. Check for typos and try again."
        if h in self._read_ledger() or h == self._stored_hash():
            return False, "This access code has already been used (1-use only)."

        ok_online, err_online = self._claim_online(h)
        if not ok_online:
            return False, err_online

        self._record_consumed(h)
        self.config.set(CONFIG_KEY, {"hash": h, "redeemed_at": int(time.time()), "machine_id": get_machine_id()})
        return True, "Code accepted (1-use claimed). Premium features are unlocked."

    def deactivate(self):
        h = self._stored_hash()
        if h:
            self._record_consumed(h)
        self.config.set(CONFIG_KEY, {})

    def set_revoked(self, hashes: Iterable[str]) -> bool:
        """Stores the revoked-code list from the update manifest. Returns True if it changed."""
        clean = sorted({h.lower() for h in (hashes or []) if isinstance(h, str) and re.fullmatch(r"[0-9a-fA-F]{64}", h)})
        if clean == sorted(self._revoked()):
            return False
        self.config.set(REVOKED_KEY, clean)
        return True
