// AudioWorkletProcessor that forwards mono PCM (Float32) frames to the main
// thread. Replaces the deprecated ScriptProcessorNode for reliable capture in
// WKWebView / Safari and Chromium. Buffers ~2048 samples per message to keep
// postMessage traffic low.
class PCMRecorder extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(2048)
    this._offset = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (input && input[0]) {
      const channel = input[0]
      for (let i = 0; i < channel.length; i++) {
        this._buffer[this._offset++] = channel[i]
        if (this._offset >= this._buffer.length) {
          this.port.postMessage(this._buffer.slice(0))
          this._offset = 0
        }
      }
    }
    return true
  }
}

registerProcessor('pcm-recorder', PCMRecorder)
