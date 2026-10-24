# -*- coding: utf-8 -*-
"""Tells you when a newer version is published on GitHub (it never installs anything by itself)."""
import os

import requests

from . import VERSION
from . import common as C


def repo_name(cfg):
    """'owner/repo': the setting, else the one written into the installer when it was built on GitHub."""
    if cfg.get("update_repo"):
        return cfg["update_repo"].strip()
    try:
        with open(C.resource_path(os.path.join("assets", "repo.txt")), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def check_latest(repo, current=VERSION, timeout=8):
    """Returns (version, url) when a newer release exists, else None. Network problems just return None."""
    if not repo or "/" not in repo:
        return None
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=timeout,
                         headers={"Accept": "application/vnd.github+json", "User-Agent": "Sleepify"})
        if r.status_code != 200:
            return None
        data = r.json()
        tag = str(data.get("tag_name", ""))
        if C.version_tuple(tag) > C.version_tuple(current):
            return tag.lstrip("v"), data.get("html_url") or f"https://github.com/{repo}/releases"
    except Exception as e:
        C.log_error(f"update check failed: {e}")
    return None
