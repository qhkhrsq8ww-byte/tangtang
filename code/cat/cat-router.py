#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 小米路由器控制（本地 Web API）
用法: cat-router.py status|devices|limit <mac> <上行Mbps> <下行Mbps>|block <mac>|unblock <mac>
密码: 本机 .router_key（600），不入库
"""
import sys, os, re, json, hashlib, urllib.request, urllib.parse, http.cookiejar

ROUTER = "http://192.168.31.1"
CAT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_SALT = "a2ffa5c9be07488bbb9a325bc770cb94"  # 小米固件固定盐（社区公开算法）

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (Macintosh)")]

def sha1(s): return hashlib.sha1(s.encode()).hexdigest()

def get_password():
    return open(os.path.join(CAT_DIR, ".router_key")).read().strip()

def login():
    import time, random, subprocess
    # 1) 设备专属 key（web 页面）
    html = opener.open(ROUTER + "/cgi-bin/luci/web", timeout=10).read().decode("utf-8", "ignore")
    m = re.search(r"key:\s*'([^']+)'", html)
    if not m:
        raise RuntimeError("device key not found")
    key = m.group(1)
    # 2) 路由器 MAC（arp 补零）
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
    mm = re.search(r"\(%s\) at ([0-9a-f:]+)" % re.escape("192.168.31.1"), out)
    if not mm:
        raise RuntimeError("router mac not found in arp")
    mac = ":".join(part.zfill(2) for part in mm.group(1).split(":")).replace(":", "")
    # 3) 客户端构造 nonce：0_<mac>_<时间戳>_<随机>
    nonce = "0_%s_%d_%d" % (mac, int(time.time()), random.randint(1000, 9999))
    # 4) 双重 SHA1
    pwd2 = sha1(nonce + sha1(get_password() + key))
    data = urllib.parse.urlencode({"username": "admin", "password": pwd2,
                                   "logtype": "2", "nonce": nonce}).encode()
    res = json.loads(opener.open(ROUTER + "/cgi-bin/luci/api/xqsystem/login", data=data, timeout=10).read())
    if res.get("code") != 0:
        raise RuntimeError("login failed: " + json.dumps(res, ensure_ascii=False)[:120])
    stok = (re.search(r";stok=([^/&]+)", res.get("url", "")) or [None, res.get("token", "")])[1]
    return stok

def api(stok, path):
    u = "%s/cgi-bin/luci/;stok=%s%s" % (ROUTER, stok, path)
    return json.loads(opener.open(u, timeout=10).read().decode("utf-8", "ignore"))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    stok = login()
    if cmd == "status":
        s = api(stok, "/api/misystem/status")
        info = s.get("hardware", {}) or {}
        print(json.dumps({"model": info.get("model"), "version": info.get("version"),
                          "temperature": s.get("temperature"),
                          "uptime": (s.get("uptime") or {}).get("upTime"),
                          "mem": (s.get("mem") or {}).get("usage"),
                          "wan": (s.get("wan") or {})}, ensure_ascii=False)[:600])
    elif cmd == "devices":
        d = api(stok, "/api/misystem/devicelist")
        for dev in (d.get("list") or []):
            ips = dev.get("ip") or [{}]
            ip0 = ips[0] if isinstance(ips[0], dict) else {}
            print("%-22s %-15s %-17s 在线%.0fh  下载%sB/s" % (
                dev.get("name"), ip0.get("ip", "?"), dev.get("mac"),
                int(ip0.get("online", 0)) / 3600.0, ip0.get("downspeed", "0")))
    elif cmd == "limit":
        mac, up, down = sys.argv[2], sys.argv[3], sys.argv[4]
        r = api(stok, "/api/misystem/set_speedlimit?mac=%s&up=%s&down=%s" % (mac, up, down))
        print(json.dumps(r, ensure_ascii=False)[:300])
    elif cmd == "block":
        r = api(stok, "/api/misystem/set_wifi_unblock" if False else "/api/misystem/block?mac=" + sys.argv[2])
        print(json.dumps(r, ensure_ascii=False)[:300])
    elif cmd == "unblock":
        r = api(stok, "/api/misystem/unblock?mac=" + sys.argv[2])
        print(json.dumps(r, ensure_ascii=False)[:300])
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
