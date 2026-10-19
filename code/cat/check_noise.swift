import Foundation
import AudioToolbox

// 糖糖·环境音量检测工具
// 用内置麦克风录 N 秒，计算 RMS 音量，输出 LOUD/QUIET + 数值
// 用法: ./check_noise [秒数(默认4)] [阈值(默认0.02)]

let args = CommandLine.arguments
let durationSec = args.count > 1 ? Double(args[1]) ?? 4.0 : 4.0
let threshold = args.count > 2 ? Double(args[2]) ?? 0.02 : 0.02

let sampleRate = 16000.0
var pcmData = Data()
var queueRef: AudioQueueRef? = nil
var done = false

// 录音回调：收集 PCM
func recordCallback(_ inUserData: UnsafeMutableRawPointer?,
                    _ inAQ: AudioQueueRef,
                    _ inBuffer: AudioQueueBufferRef,
                    _ inStartTime: UnsafePointer<AudioTimeStamp>,
                    _ inNumPackets: UInt32,
                    _ inPacketDesc: UnsafePointer<AudioStreamPacketDescription>?) {
    let data = Data(bytes: inBuffer.pointee.mAudioData, count: Int(inBuffer.pointee.mAudioDataByteSize))
    pcmData.append(data)
    AudioQueueEnqueueBuffer(inAQ, inBuffer, 0, nil)
}

// 计算 RMS 音量（16-bit PCM）
func computeRMS(_ data: Data) -> Double {
    guard data.count >= 2 else { return 0.0 }
    var sumSq: Double = 0
    var count = 0
    data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
        let samples = raw.bindMemory(to: Int16.self)
        for s in samples {
            let v = Double(s) / 32768.0
            sumSq += v * v
            count += 1
        }
    }
    return count > 0 ? (sumSq / Double(count)).squareRoot() : 0.0
}

// 配置音频格式
var format = AudioStreamBasicDescription(
    mSampleRate: sampleRate,
    mFormatID: kAudioFormatLinearPCM,
    mFormatFlags: kAudioFormatFlagIsSignedInteger | kAudioFormatFlagIsPacked,
    mBytesPerPacket: 2,
    mFramesPerPacket: 1,
    mBytesPerFrame: 2,
    mChannelsPerFrame: 1,
    mBitsPerChannel: 16,
    mReserved: 0
)

var status = AudioQueueNewInput(&format, recordCallback, nil, nil, nil, 0, &queueRef)
guard status == noErr, let queue = queueRef else {
    print("ERROR: AudioQueueNewInput failed (\(status))")
    exit(1)
}

// 分配 3 个 buffer
let bufferSize: UInt32 = UInt32(sampleRate * 0.5) * 2 // 0.5秒 * 2字节
for _ in 0..<3 {
    var buffer: AudioQueueBufferRef? = nil
    AudioQueueAllocateBuffer(queue, bufferSize, &buffer)
    if let b = buffer {
        AudioQueueEnqueueBuffer(queue, b, 0, nil)
    }
}

// 开始录音
AudioQueueStart(queue, nil)
print("RECORDING \(Int(durationSec))s ...", terminator: "")
fflush(stdout)

Thread.sleep(forTimeInterval: durationSec)

AudioQueueStop(queue, true)
AudioQueueDispose(queue, true)

let rms = computeRMS(pcmData)
let db = 20.0 * log10(rms + 1e-9)
print(" RMS=\(String(format: "%.4f", rms)) (\(String(format: "%.1f", db))dB)")
if rms >= threshold {
    print("LOUD")
} else {
    print("QUIET")
}
exit(0)
