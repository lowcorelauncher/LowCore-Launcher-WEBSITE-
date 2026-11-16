"""
Update checker. It only LOOKS for a newer version and tells the user; it never downloads or runs
anything by itself (the user clicks Download and installs the new version normally).

Manifest format (version.json, hosted by you):
{
  "version": "1.1.0",
  "url": "https://example.com/downloads/LowCoreLauncher-1.1.0-setup.exe",
  "notes": ["Import instances from other launchers", "Faster launches"],
  "revoked": []          // optional: SHA-256 hashes of access codes to switch off
}
A GitHub "releases/latest" URL also works (tag_name, html_url and body are used).
"""
import re
import requests

USER_AGENT = "LowCoreLauncher-UpdateCheck/1.0"


def parse_version(text: str) -> tuple:
    """'v1.2.3-beta' -> (1, 2, 3). Missing parts count as 0."""
    core = re.split(r"[-+ ]", str(text).strip().lstrip("vV"), maxsplit=1)[0]
    nums = [int(x) for x in re.findall(r"\d+", core)][:4]
    return tuple(nums) if nums else (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def _notes_list(value) -> list:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        lines = [re.sub(r"^[\s\-*\u2022#]+", "", ln).strip() for ln in value.splitlines()]
        return [ln for ln in lines if ln]
    return []


def check_for_update(manifest_url: str, current_version: str, timeout: int = 8) -> dict:
    """Returns {"available", "latest", "current", "url", "notes", "revoked"}. Raises on network/format errors."""
    if not manifest_url.lower().startswith("https://"):
        raise ValueError("The update address must start with https://")

    res = requests.get(manifest_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=timeout)
    if res.status_code == 404 and "api.github.com" in manifest_url:
        raise ValueError("No release has been published on GitHub yet.")
    if res.status_code == 403 and "api.github.com" in manifest_url:
        raise ValueError("GitHub is limiting requests right now. Try again in a while.")
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected update data.")

    if "tag_name" in data:                      # GitHub release
        latest = str(data.get("tag_name", ""))
        url = str(data.get("html_url", ""))
        notes = _notes_list(data.get("body", ""))
        revoked = []
    else:
        latest = str(data.get("version", ""))
        url = str(data.get("url", ""))
        notes = _notes_list(data.get("notes", []))
        revoked = data.get("revoked", []) if isinstance(data.get("revoked", []), list) else []

    if not latest:
        raise ValueError("The update data has no version.")
    if url and not url.lower().startswith("https://"):
        url = ""                                 # never offer a non-https download link

    return {
        "available": is_newer(latest, current_version),
        "latest": latest.lstrip("vV"),
        "current": current_version,
        "url": url,
        "notes": notes,
        "revoked": revoked,
    }