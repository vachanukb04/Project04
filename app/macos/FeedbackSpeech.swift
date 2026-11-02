// Short, user-triggered voice feedback. Image recognition never happens here.
import AppKit
import AVFoundation
import Speech
import Darwin

final class FeedbackListener {
    let engine = AVAudioEngine()
    var recognizer: SFSpeechRecognizer?
    var request: SFSpeechAudioBufferRecognitionRequest?
    var task: SFSpeechRecognitionTask?
    var latest = ""
    var finished = false
    var tapped = false
    let allowNetwork = CommandLine.arguments.contains("--allow-network")

    func finish(_ error: String? = nil) {
        if finished { return }
        finished = true
        engine.stop()
        if tapped { engine.inputNode.removeTap(onBus: 0) }
        request?.endAudio()
        task?.cancel()
        let payload: [String: Any] = error == nil
            ? ["transcript": latest, "on_device": request?.requiresOnDeviceRecognition ?? true]
            : ["error": error!]
        if let data = try? JSONSerialization.data(withJSONObject: payload),
           let json = String(data: data, encoding: .utf8) { print(json) }
        fflush(stdout)
        exit(error == nil ? 0 : 1)
    }
    func begin() {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                guard status == .authorized else {
                    self.finish("Speech permission denied. Use typed feedback or enable Speech Recognition in macOS Privacy & Security.")
                    return
                }
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    DispatchQueue.main.async {
                        if granted { self.listen() }
                        else { self.finish("Microphone permission denied. Typed feedback remains available.") }
                    }
                }
            }
        }
    }
    func listen() {
        guard let rec = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), rec.isAvailable else {
            finish("English speech recognition is unavailable. Use typed feedback."); return
        }
        recognizer = rec
        if !rec.supportsOnDeviceRecognition && !allowNetwork {
            finish("On-device recognition is unavailable. Use typed feedback, or explicitly enable --allow-network-voice."); return
        }
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.requiresOnDeviceRecognition = !allowNetwork
        req.shouldReportPartialResults = true
        req.contextualStrings = ["yes", "no", "this is", "these are", "AirPods", "phone"]
        request = req
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            finish("No working microphone input."); return
        }
        task = rec.recognitionTask(with: req) { result, error in
            DispatchQueue.main.async {
                if self.finished { return }
                if let result = result {
                    self.latest = result.bestTranscription.formattedString
                    if result.isFinal {
                        self.finish(self.latest.isEmpty ? "No speech heard." : nil)
                        return
                    }
                }
                if let error = error {
                    self.finish(self.latest.isEmpty ? error.localizedDescription : nil)
                }
            }
        }
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in req.append(buffer) }
        tapped = true
        do { engine.prepare(); try engine.start() }
        catch { finish(error.localizedDescription); return }
        // User feedback is a short utterance, not an always-on microphone.
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            if self.finished { return }
            self.engine.stop();req.endAudio()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                self.finish(self.latest.isEmpty ? "No speech heard. Press V to retry or C to type." : nil)
            }
        }
    }
}
let application = NSApplication.shared
application.setActivationPolicy(.accessory)
let listener = FeedbackListener()
DispatchQueue.main.async { listener.begin() }
DispatchQueue.main.asyncAfter(deadline: .now() + 70) { listener.finish("Speech authorization timed out.") }
application.run()
