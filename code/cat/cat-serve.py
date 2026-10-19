#!/usr/bin/env python3
# 糖糖静态服务器（带 Range 支持——视频播放/拖动依赖 206 响应）
# 用法: /usr/bin/python3 cat-serve.py [port] [bind]
import os, re, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)$')


class RangeHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def send_head(self):
        # 安全：拒绝所有隐藏文件/目录（.llm_key .baidu_token 等）
        if "/." in self.translate_path(self.path):
            self.send_error(404, "Not Found")
            return None
        rng = self.headers.get('Range')
        if not rng or self.command not in ('GET', 'HEAD'):
            return super().send_head()
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.isfile(path):
            return super().send_head()
        m = RANGE_RE.match(rng.strip())
        if not m:
            return super().send_head()
        size = os.path.getsize(path)
        if m.group(1) == '' and m.group(2):
            # 后缀形式 bytes=-N：最后 N 字节
            start = max(0, size - int(m.group(2)))
            end = size - 1
        else:
            start = int(m.group(1) or 0)
            end = int(m.group(2) or (size - 1))
        if start >= size or start > end:
            self.send_response(416)
            self.send_header('Content-Range', 'bytes */%d' % size)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None
        end = min(end, size - 1)
        length = end - start + 1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.send_header('Content-Length', str(length))
        self.end_headers()
        if self.command == 'GET':
            with open(path, 'rb') as f:
                f.seek(start)
                self.wfile.write(f.read(length))
        return None


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    bind = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer((bind, port), RangeHandler)
    print('cat-serve %s:%d root=%s' % (bind, port, ROOT), flush=True)
    httpd.serve_forever()
