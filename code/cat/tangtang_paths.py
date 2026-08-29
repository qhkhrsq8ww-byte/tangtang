#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖记忆目录：默认只写客厅 Mac Air 本机硬盘，不写路由器 NAS。

Mac:  ~/Library/Application Support/Tangtang
其它: ~/.local/share/tangtang
可用 TANGTANG_DATA_DIR 覆盖；现在不要填 Samba / 路由器盘路径。
"""
import glob
import os
import shutil
import sys

CAT_DIR = os.path.dirname(os.path.abspath(__file__))

MEMORY_FILES = (
    "cat-state.json",
    "cat-memory.json",
    "cat-habits.json",
    "cat-voiceprints.json",
    "cat-chat-history.json",
    "cat-remind-log.txt",
    "cat-turn-ledger.json",
    "cat-habit-growth.json",
)


def preferred_local_dir(platform=None, home=None):
    plat = platform if platform is not None else sys.platform
    home = os.path.abspath(os.path.expanduser(home or "~"))
    if plat == "darwin":
        return os.path.join(home, "Library", "Application Support", "Tangtang")
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg:
        return os.path.join(os.path.abspath(os.path.expanduser(xdg)), "tangtang")
    return os.path.join(home, ".local", "share", "tangtang")


def looks_like_network_volume(path):
    p = os.path.abspath(os.path.expanduser(path or ""))
    if p.startswith("//") or p.lower().startswith("smb:"):
        return True
    # Mac 上 /Volumes/ 多为外置盘或路由器 Samba，不是 Air 内置盘
    return p.startswith("/Volumes/")


def memory_sources(legacy_dir):
    names = list(MEMORY_FILES)
    pattern = os.path.join(legacy_dir, "cat-chat-history-*.json")
    names.extend(os.path.basename(p) for p in sorted(glob.glob(pattern)))
    # 去重且保持顺序
    seen = set()
    out = []
    for name in names:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def migrate_legacy(legacy_dir, dest_dir):
    """把 code/cat/ 里旧记忆拷到本机数据目录；已存在的文件不覆盖。"""
    if not legacy_dir or not dest_dir:
        return []
    legacy_dir = os.path.abspath(legacy_dir)
    dest_dir = os.path.abspath(dest_dir)
    if legacy_dir == dest_dir or not os.path.isdir(legacy_dir):
        return []
    os.makedirs(dest_dir, exist_ok=True)
    copied = []
    for name in memory_sources(legacy_dir):
        src = os.path.join(legacy_dir, name)
        dst = os.path.join(dest_dir, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            copied.append(name)
    return copied


def data_dir(env=None, legacy_dir=None, platform=None, home=None, warn=True):
    if env is None:
        env = (os.environ.get("TANGTANG_DATA_DIR") or "").strip()
    if env:
        path = os.path.abspath(os.path.expanduser(env))
    else:
        path = preferred_local_dir(platform=platform, home=home)
        migrate_legacy(legacy_dir if legacy_dir is not None else CAT_DIR, path)
    os.makedirs(path, exist_ok=True)
    if warn and looks_like_network_volume(path):
        sys.stderr.write(
            "警告：记忆目录在 /Volumes/ 或网络盘。"
            "当前约定先写 Mac Air 本机硬盘，不要写路由器硬盘。\n"
        )
    return path


def _selftest():
    import tempfile

    home = tempfile.mkdtemp(prefix="tangtang-home-")
    legacy = tempfile.mkdtemp(prefix="tangtang-legacy-")
    dest_override = tempfile.mkdtemp(prefix="tangtang-dest-")
    try:
        mac = preferred_local_dir(platform="darwin", home=home)
        assert mac.endswith(os.path.join("Library", "Application Support", "Tangtang")), mac
        other = preferred_local_dir(platform="linux", home=home)
        assert other.endswith(os.path.join(".local", "share", "tangtang")), other

        assert looks_like_network_volume("/Volumes/MiRouter/tangtang")
        assert not looks_like_network_volume(mac)

        open(os.path.join(legacy, "cat-state.json"), "w").write("{}")
        open(os.path.join(legacy, "cat-chat-history-hanghang.json"), "w").write("[]")
        copied = migrate_legacy(legacy, dest_override)
        assert "cat-state.json" in copied
        assert "cat-chat-history-hanghang.json" in copied
        # 不覆盖已有
        open(os.path.join(dest_override, "cat-state.json"), "w").write('{"keep":1}')
        open(os.path.join(legacy, "cat-state.json"), "w").write('{"old":1}')
        migrate_legacy(legacy, dest_override)
        with open(os.path.join(dest_override, "cat-state.json")) as f:
            assert '"keep"' in f.read()

        explicit = data_dir(env=dest_override, legacy_dir=legacy, warn=False)
        assert explicit == os.path.abspath(dest_override)

        auto = data_dir(env="", legacy_dir=legacy, platform="darwin", home=home, warn=False)
        assert auto == mac
        assert os.path.isfile(os.path.join(mac, "cat-state.json"))
        print("tangtang_paths selftest ok")
        print(mac)
    finally:
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(legacy, ignore_errors=True)
        shutil.rmtree(dest_override, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--selftest", "selftest"):
        _selftest()
    else:
        print(data_dir())
