#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 小米路由器控制（本地 Web API）
用法: cat-router.py status|devices|limit <mac> <上行Mbps> <下行Mbps>|block <mac>|unblock <mac>
密码: 本机 .router_key（600），不入库
"""
import sys, os, re, json, hashlib, argparse, urllib.request, urllib.parse, http.cookiejar

ROUTER = "http://192.168.31.1"
CAT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(CAT_DIR, '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from core.integrations.miwifi_router import normalize_mac, validate_control_request

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
    html = opener.open(ROUTER + "/cgi-bin/luci/web", timeout=25).read().decode("utf-8", "ignore")
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
    res = json.loads(opener.open(ROUTER + "/cgi-bin/luci/api/xqsystem/login", data=data, timeout=25).read())
    if res.get("code") != 0:
        raise RuntimeError("login failed: " + json.dumps(res, ensure_ascii=False)[:120])
    stok = (re.search(r";stok=([^/&]+)", res.get("url", "")) or [None, res.get("token", "")])[1]
    return stok

def api(stok, path):
    u = "%s/cgi-bin/luci/;stok=%s%s" % (ROUTER, stok, path)
    return json.loads(opener.open(u, timeout=25).read().decode("utf-8", "ignore"))

def main():
    parser = argparse.ArgumentParser(description='糖糖 · 小米路由器本地设备管控')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status', help='查看路由器状态（只读）')
    sub.add_parser('devices', help='查看在线/历史设备（只读）')
    for name in ('block', 'unblock'):
        p = sub.add_parser(name, help='禁止/恢复设备访问互联网（需要家长授权）')
        p.add_argument('mac', help='目标设备 MAC')
        p.add_argument('--confirm-mac', required=True, help='再次输入完整目标 MAC')
        p.add_argument('--parent-approved', action='store_true', help='确认这是家长在本机执行的授权操作')
    limit = sub.add_parser('limit', help='设置设备速度上限（需要家长授权）')
    limit.add_argument('mac', help='目标设备 MAC')
    limit.add_argument('up', type=int, help='上行 Mbps，1-1000')
    limit.add_argument('down', type=int, help='下行 Mbps，1-1000')
    limit.add_argument('--confirm-mac', required=True, help='再次输入完整目标 MAC')
    limit.add_argument('--parent-approved', action='store_true', help='确认这是家长在本机执行的授权操作')
    args = parser.parse_args()
    mac = None
    if args.command in ('block', 'unblock', 'limit'):
        try:
            mac = validate_control_request(args.mac, confirmed_mac=args.confirm_mac, parent_approved=args.parent_approved)
        except (ValueError, PermissionError) as exc:
            print('拒绝执行设备管控：{}'.format(exc), file=sys.stderr)
            return 2
        if args.command == 'limit' and not (1 <= args.up <= 1000 and 1 <= args.down <= 1000):
            print('速度上限必须在 1–1000 Mbps 之间。', file=sys.stderr)
            return 2
    try:
        stok = login()
        if args.command == 'status':
            s = api(stok, '/api/misystem/status')
            info = s.get('hardware', {}) or {}
            print(json.dumps({'model': info.get('model'), 'version': info.get('version'), 'temperature': s.get('temperature'), 'uptime': (s.get('uptime') or {}).get('upTime'), 'mem': (s.get('mem') or {}).get('usage'), 'wan': (s.get('wan') or {})}, ensure_ascii=False)[:600])
        elif args.command == 'devices':
            d = api(stok, '/api/misystem/devicelist')
            for dev in (d.get('list') or []):
                ips = dev.get('ip') or [{}]
                ip0 = ips[0] if isinstance(ips[0], dict) else {}
                print('%-22s %-15s %-17s 在线%.0fh  下载%sB/s' % (dev.get('name'), ip0.get('ip', '?'), dev.get('mac'), int(ip0.get('online', 0)) / 3600.0, ip0.get('downspeed', '0')))
        elif args.command == 'limit':
            query = urllib.parse.urlencode({'mac': mac, 'up': args.up, 'down': args.down})
            result = api(stok, '/api/misystem/set_speedlimit?' + query)
            print(json.dumps(result, ensure_ascii=False)[:300])
        elif args.command in ('block', 'unblock'):
            wan = 0 if args.command == 'block' else 1
            query = urllib.parse.urlencode({'mac': mac, 'wan': wan})
            result = api(stok, '/api/xqsystem/set_mac_filter?' + query)
            print(json.dumps(result, ensure_ascii=False)[:200])
        return 0
    except Exception as exc:
        print('路由器操作失败：{}'.format(type(exc).__name__), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
