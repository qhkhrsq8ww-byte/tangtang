#!/usr/bin/env node
// 糖糖发声回退：百度翻译 TTS（只写 /tmp/cat_tts.mp3，不播放）
// 用法: node cat-tts-baidu.mjs "文本" [spd]   spd: 1~7, 默认 4(可爱慢柔)
import fs from 'node:fs';
import https from 'node:https';
import { URL } from 'node:url';

const text = process.argv[2] || '汪汪～';
const spd = process.argv[3] || '4'; // 1慢~7快, 4=自然偏慢, 3=更萌
const out = '/tmp/cat_tts.mp3';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.66 Safari/537.36 Edg/103.0.1264.44';

const query = new URLSearchParams({ lan: 'zh', text, spd, source: 'web' }).toString();
const url = `https://fanyi.baidu.com/gettts?${query}`;

function get() {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': UA, 'Referer': 'https://fanyi.baidu.com/' } }, res => {
      if (res.statusCode !== 200) { reject(new Error('HTTP ' + res.statusCode)); return; }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
}

(async () => {
  let buf;
  try { buf = await get(); }
  catch (e) { console.error('合成失败:', e.message); process.exit(1); }
  if (!buf || buf.length < 200) { console.error('合成结果为空/被拒'); process.exit(1); }
  fs.writeFileSync(out, buf);
  // 只合成，由 cat-say.sh / cat-talk.sh 负责播放，避免连播两遍
})();
