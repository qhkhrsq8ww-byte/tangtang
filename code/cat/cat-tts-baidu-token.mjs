#!/usr/bin/env node
// 糖糖「童声版」发声核心：百度语音合成（度小萌儿童音库 per=3）
// 用法: node cat-tts-baidu-token.mjs "文本" [spd] [pit]
//   spd: 1~9 语速, 默认 5（适中偏慢，适合小朋友听）
//   pit: 1~9 音调, 默认 7（偏高更萌）
// 依赖: 百度 TTS 已开通（和 ASR 同一应用），token 用 API key 换取
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import https from 'node:https';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const CAT_DIR = dirname(fileURLToPath(import.meta.url));
const text = process.argv[2] || '汪汪～';
const spd = process.argv[3] || '5';
const pit = process.argv[4] || '7';
const out = '/tmp/cat_tts.mp3';

// 读百度 key（cat-stt-config.sh）
function loadKeys() {
  const envKey = process.env.BAIDU_STT_API_KEY || '';
  const envSecret = process.env.BAIDU_STT_SECRET_KEY || '';
  if (envKey && envSecret) return { apiKey: envKey, secretKey: envSecret };
  try {
    const conf = fs.readFileSync(CAT_DIR + '/cat-stt-config.sh', 'utf-8');
    const apiKey = (conf.match(/BAIDU_STT_API_KEY="([^"]+)"/) || [])[1] || '';
    const secretKey = (conf.match(/BAIDU_STT_SECRET_KEY="([^"]+)"/) || [])[1] || '';
    return { apiKey, secretKey };
  } catch (e) { return { apiKey: '', secretKey: '' }; }
}

// 获取 access_token（缓存 20 天，token 有效期 30 天）
function getToken(apiKey, secretKey) {
  const cacheFile = CAT_DIR + '/.baidu_token';
  try {
    const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
    if (cached.token && Date.now() - cached.time < 20 * 24 * 3600 * 1000) return cached.token;
  } catch (e) {}
  const url = `https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=${encodeURIComponent(apiKey)}&client_secret=${encodeURIComponent(secretKey)}`;
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try {
          const j = JSON.parse(d);
          if (j.access_token) {
            fs.writeFileSync(cacheFile, JSON.stringify({ token: j.access_token, time: Date.now() }));
            resolve(j.access_token);
          } else reject(new Error('token 失败: ' + JSON.stringify(j).slice(0, 200)));
        } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

// 合成并返回 mp3 buffer
function synth(token, text) {
  const params = new URLSearchParams({
    tok: token, tex: text, cuid: 'mac-tangtang', ctp: 1, lan: 'zh',
    spd, pit, vol: 9, per: 3, aue: 3  // per=3 度小萌童声, aue=3 mp3
  });
  return new Promise((resolve, reject) => {
    https.get('https://tsn.baidu.com/text2audio?' + params.toString(), res => {
      if (res.statusCode !== 200) { reject(new Error('HTTP ' + res.statusCode)); return; }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
}

(async () => {
  const { apiKey, secretKey } = loadKeys();
  if (!apiKey) { console.error('❌ 未找到百度 key，请检查 cat-stt-config.sh'); process.exit(1); }
  let token;
  try { token = await getToken(apiKey, secretKey); }
  catch (e) { console.error('❌ token 获取失败:', e.message); process.exit(1); }

  let buf;
  try { buf = await synth(token, text); }
  catch (e) { console.error('❌ 合成失败:', e.message); process.exit(1); }
  if (!buf || buf.length < 200) { console.error('❌ 合成结果为空/被拒'); process.exit(1); }

  fs.writeFileSync(out, buf);
  // 播放：afplay 走系统默认输出（小米音箱）
  try { execFileSync('afplay', [out]); }
  catch (e) { console.error('⚠ 播放失败:', e.message); process.exit(2); }
})();
