#!/usr/bin/env node
// 糖糖发声核心：Edge 神经语音（XiaoxiaoNeural）
// 用法: node cat-tts.js "文本" [style] [voice]
//   style: cheerful / affectionate / gentle / default
//   默认 voice: zh-CN-XiaoxiaoNeural
const edgeTTS = require('edge-tts');
const fs = require('fs');
const { execFileSync } = require('child_process');

const text = process.argv[2] || '汪汪～';
const style = process.argv[3] || 'cheerful';
const voice = process.argv[4] || 'zh-CN-XiaoxiaoNeural';
const out = '/tmp/cat_tts.mp3';

const styleMap = {
  cheerful:     { rate: '-4%',  pitch: '+10Hz', style: 'cheerful',     degree: '1.3' },
  affectionate: { rate: '-8%',  pitch: '+6Hz',  style: 'affectionate', degree: '1.2' },
  gentle:       { rate: '-10%', pitch: '+4Hz',  style: 'gentle',       degree: '1.0' },
  default:      { rate: '-4%',  pitch: '+8Hz',  style: 'default',      degree: '1.0' },
};
const opt = styleMap[style] || styleMap.default;

(async () => {
  const tts = new edgeTTS.TTS({ voice, lang: 'zh-CN' });
  await new Promise((resolve, reject) => {
    const stream = tts.toStream(text, {
      rate: opt.rate, pitch: opt.pitch,
      style: opt.style, styledegree: opt.degree,
    });
    const f = fs.createWriteStream(out);
    stream.pipe(f);
    stream.on('error', reject);
    f.on('finish', resolve);
  });
  // 播放：走系统默认音频输出（投影蓝牙若连着 → 从投影出）
  try { execFileSync('afplay', [out]); }
  catch (e) { console.error('播放失败:', e.message); process.exit(2); }
})().catch(e => { console.error('合成失败:', e.message); process.exit(1); });
