#!/usr/bin/env node
// 猫咪「糖糖」发声核心：Edge 神经语音（可爱中文），带 Sec-MS-GEC 校验绕过 403
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import WS from 'ws';

const text = process.argv[2] || '汪汪～';
const tone = process.argv[3] || 'cute';
const voice = process.argv[4] || 'zh-CN-XiaoxiaoNeural';
const out = '/tmp/cat_tts.mp3';

const toneMap = {
  cute:  { rate: '-12%', pitch: '+14Hz', volume: '+0%' },
  sweet: { rate: '-8%',  pitch: '+8Hz',  volume: '+0%' },
  soft:  { rate: '-15%', pitch: '+6Hz',  volume: '-2%' },
  calm:  { rate: '-6%',  pitch: '+4Hz',  volume: '+0%' },
};
const opt = toneMap[tone] || toneMap.cute;

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.66 Safari/537.36 Edg/103.0.1264.44';
const TRUSTED = '6A5AA1D4EAFF4E9FB37E23D68491D6F4';
const GEC_KEY = '3PFB9BEF-1B43-4945-BC9A-4AE8A6B0C164';

// Sec-MS-GEC：8位hex，算法 = md5(timestamp10位 + GEC_KEY) 大写前8位
function getSecMsGec() {
  const stamp = Math.floor(Date.now() / 1000).toString();
  const h = crypto.createHash('md5').update(stamp + GEC_KEY).digest('hex').toUpperCase();
  return h.slice(0, 8);
}

function synth(text, opt, voice) {
  const connId = crypto.randomUUID().replace(/-/g, '');
  const stamp = Math.floor(Date.now() / 1000).toString();
  const gec = getSecMsGec();
  const wsUrl = `wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=${TRUSTED}&Sec-MS-GEC=${gec}&Sec-MS-GEC-Version=1-${stamp.slice(0,4)}&ConnectionId=${connId}`;
  return new Promise((resolve, reject) => {
    const ws = new WS(wsUrl, {
      host: 'speech.platform.bing.com',
      origin: 'chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold',
      headers: {
        'User-Agent': UA,
        'Sec-MS-Edge-Version': '103.0.1264.44',
      },
    });
    const audio = [];
    ws.on('message', (raw, isBinary) => {
      if (!isBinary) {
        const s = raw.toString();
        if (s.includes('turn.end')) { ws.close(); resolve(Buffer.concat(audio)); }
        return;
      }
      const sep = 'Path:audio\r\n';
      const i = raw.indexOf(sep);
      if (i >= 0) audio.push(raw.subarray(i + sep.length));
    });
    ws.on('error', reject);
    ws.on('open', () => {
      const cfg = `X-Timestamp:${new Date()}\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n${JSON.stringify({context:{synthesis:{audio:{metadataoptions:{sentenceBoundaryEnabled:false,wordBoundaryEnabled:false},outputFormat:"audio-24khz-48kbitrate-mono-mp3"}}}})}`;
      ws.send(cfg);
      const ssml = `X-RequestId:${crypto.randomUUID().replace(/-/g,'')}\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:${new Date()}Z\r\nPath:ssml\r\n\r\n<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='${voice}'><prosody pitch='${opt.pitch}' rate='${opt.rate}' volume='${opt.volume}'>${text}</prosody></voice></speak>`;
      ws.send(ssml);
    });
  });
}

(async () => {
  let buf;
  try { buf = await synth(text, opt, voice); }
  catch (e) { console.error('合成失败:', e.message); process.exit(1); }
  if (!buf || buf.length < 100) { console.error('合成结果为空/被拒'); process.exit(1); }
  fs.writeFileSync(out, buf);
  try { execFileSync('afplay', [out]); }
  catch (e) { console.error('播放失败:', e.message); process.exit(2); }
})();
