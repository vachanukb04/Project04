# Learning from confirmed feedback over time

## What changed

Use **`python app/mac_rtl_camera.py learn --speak --voice`** for the new feedback path. It requires no 20-view dataset and no training command. One confirmed view is enough to create the first memory. Later confirmed views add examples for other angles/backgrounds. The old `collect/train/run` MLP remains a separate optional experiment.

This implementation is **episodic appearance memory**, not a pretrained semantic neural network and not online backpropagation. It extracts a low-resolution RGB descriptor in RTL and searches confirmed examples in RTL. It cannot name an object it has never been taught: empty memory returns `unknown` and asks for a name. Once taught, it makes a tentative nearest-example guess, even for a weak match, as requested. It does not invent product specifications.

The previously discussed pretrained visual feature extractor is not implemented in this update. This simpler memory provides a working, testable correction loop first. Raw spatial color similarity can confuse different objects with similar colors/backgrounds, and may fail under rotation, scale, or lighting changes. Additional confirmed views can help but do not guarantee recognition. A pretrained embedding network is a future replacement for the descriptor, with the feedback protocol retained.

## Mac setup and run

From your Project04 checkout, with the virtual environment active:

```bash
git pull
source .venv-camera/bin/activate
python -m pip install -r app/requirements-rtl-camera.txt
iverilog -V
vvp -V
python app/mac_rtl_camera.py learn --speak
```

Icarus is still required for actual RTL execution. If missing, install it with `brew install icarus-verilog`; if `brew` is missing, follow https://brew.sh . No ChipVerify service is used. The app does not silently calculate matches in Python when the simulator is missing.

To enable microphone feedback, install Apple's command-line tools if needed:

```bash
xcode-select --install
python app/mac_rtl_camera.py learn --speak --voice
```

`xcode-select --install` may report that tools are already installed; that is fine. `xcrun swiftc` compiles the small native Speech helper and `codesign` applies a local ad-hoc signature. A developer account is not required for this local build. The helper is bundled with microphone/speech usage descriptions under ignored `build/rtl_camera/feedback/run/Project04Feedback.app/`.

macOS may request Camera access for Terminal/IDE and Microphone/Speech Recognition access for Terminal or Project04 Feedback. Allow only if you want those features. If helper compilation, permissions, language support, or microphone access fail, the app reports the error and typed feedback remains usable. No Swift compiler, AVFoundation/Speech runtime, or Mac GUI is available in the Linux development environment: this helper's compilation and operation require your Mac validation.

## Interaction

1. Hold one object in the center square, in focus, for five stable seconds. The camera stays fixed; you rotate the object yourself.
2. The app captures a crop and sends its 16x16 RGB pixels and confirmed memories into the SystemVerilog simulation.
3. RTL returns the nearest memory slot, visual similarity, crop mean RGB/brightness/color, and a descriptor for the captured view.
4. The app says “My guess is phone. Is that correct?” or asks for a name when memory is empty. A captured-view thumbnail distinguishes the result from the moving live preview.
5. Confirm or correct using the controls below. **Only confirmation changes persistent memory.**
6. Press **Space**, change the object/view, and hold still again. Memory is loaded automatically on the next launch.

| Control | Action |
| --- | --- |
| Y | Confirm the current guessed name, or save the staged correction |
| N | Reject the guess or discard a staged correction; nothing is learned |
| C | Type a name in the preview window; Enter stages it, then Y saves it |
| V | Listen to one short feedback utterance, if voice is enabled |
| Space | Discard unsaved feedback and capture the next stable view |
| Q / Escape | Quit (Escape cancels text entry while typing) |

In voice mode the app listens once after speaking a guess. Supported English feedback examples:

- “Yes” / “Correct”: confirm the current guess or pending correction.
- “No”: reject; the app then asks for a name.
- “No, these are AirPods” / “This is a phone” / “Call it my headphones”: stage a correction.
- “Yes” after the correction is shown/read back: save it.
- “Cancel” / “Skip”: discard pending feedback.

It is not a general conversational assistant. Unrecognized conversation does not become a label. A spoken correction is shown and read back before the next confirmation. The system stops its own speech before manually requested listening. The microphone is used in short, requested windows, not as a continuous ambient recorder. Preview keys are interpreted while the preview window has focus. Typed entry currently supports printable ASCII; voice labels may contain other visible characters, but OpenCV text rendering of non-ASCII names is limited.

## Voice privacy and availability

The native helper uses Apple's `SFSpeechRecognizer` for English (`en-US`) with **on-device recognition required by default**. It refuses to start transcription when that capability is unavailable. Audio is not saved by this application. Camera frames and feedback memory are not uploaded by this code.

If you explicitly choose network speech processing, run:

```bash
python app/mac_rtl_camera.py learn --speak --voice --allow-network-voice
```

This permits Apple's speech service to process audio over the network; it does not upload camera frames. Apple documents that `requiresOnDeviceRecognition` only works when `supportsOnDeviceRecognition` is true: https://developer.apple.com/documentation/speech/sfspeechrecognizer/supportsondevicerecognition and https://developer.apple.com/documentation/speech/sfspeechrecognitionrequest/requiresondevicerecognition . There is no silent network fallback.

## Persistent learning behavior

- Default file: **`build/rtl_camera/feedback/memory.json`**. Keep it between runs and updates; it is ignored by Git, so it stays local.
- `--memory /path/to/memory.json` selects another persistent file.
- Each confirmed example stores a label, 768 four-bit descriptor values, a confirmation count, and update time. At most **64 confirmed views**, not 64 neural classes, fit the current RTL search RAM.
- Identical descriptors are updated in place when corrected, preventing an exact wrong-label duplicate from winning future ties. Different views with the same label remain separate examples.
- At capacity, the least recently confirmed view is evicted. A rolling history of the last 256 confirmations records label corrections and evictions.
- Atomic file replacement and a local file lock protect saves. A process with stale memory refuses to overwrite another session's changes; restart extra camera sessions.
- Features bind to the **captured view**, not whatever moves into the live preview while you speak.
- A confirmation is saved once per captured view. Press Space for another view. Correcting another similar-but-different view does not remove all older examples of the rejected class.
- The descriptor is a low-resolution representation of the image and can reveal visual content. Treat the file and last simulation pixel files as camera data. Back up or remove them deliberately; do not commit personal captures or labels to GitHub.

Inspect learned labels without opening the camera:

```bash
python app/mac_rtl_camera.py learn --inspect-memory
```

## RTL boundary and contract

`rtl/p04_visual_memory.sv` performs descriptor extraction, exhaustive L1 matching, similarity calculation, and crop attributes. Python handles permission/capture/resize, saving confirmed examples, file transport, label lookup, preview, and speech. No image-distance calculation or semantic prediction runs in the Python bridge.

- 256 row-major RGB888 pixels, 16x16. Descriptor is the high nibble of each R/G/B channel: 768 values in 0..15.
- Configure memory while idle via `cfg_valid/cfg_addr/cfg_data`: example-major layout, 768 nibbles per example, up to 49,152 entries. Reset preserves example RAM.
- Start with `example_count` in 0..64 and `cfg_valid=0`. Wait for `pixel_ready`; gaps in `pixel_valid` are supported. Busy starts/configuration are ignored.
- L1 distance is sum(abs(query[i]-example[i])) over 768 values. Maximum distance is 11,520. Lowest distance wins; ties select the first slot.
- Similarity is `255 - floor(distance*255/11520)`. This is a coarse appearance score, **not a calibrated probability or a semantic confidence score**. The closest name is always tentative, even with a high score.
- Empty memory returns slot 255, similarity 0, distance 11,520. No name is guessed without examples. The Mac maps a nonempty winning slot to its stored label.
- Mean RGB/brightness/color use the same crop arithmetic as the MLP path; no object segmentation, exact manufacturer/model, OCR, physical dimensions, or inferred product specifications.
- `result_valid` pulses once; attributes hold until another result. Reset cancels partial frames and clears outputs/control without clearing loaded memory.
- The testbench's descriptor dump uses hierarchical access for simulation transport only; a later FPGA integration needs a descriptor readout/memory interface. File IO and macOS interfaces are not synthesizable hardware. No synthesis, SDC or STA flow is added.

## Offline test and verification

You can explicitly teach one saved image and test memory without a camera:

```bash
python app/mac_rtl_camera.py learn --image /path/to/phone.jpg --teach phone
python app/mac_rtl_camera.py learn --image /path/to/phone.jpg
```

`--teach` is an explicit user-supplied confirmation. Without it, offline inference does not change learned memory. Headless tests and live capture use the same RTL matcher.

Run tests:

```bash
python -m unittest discover -s tests -p 'test_feedback_memory.py' -v
```

The new regression checks real RTL against independent distances at memory sizes 0, 1, 2, 7, 16, and 64, exact/extreme matches, ties, descriptor extraction, reset cancellation, and input gaps. A correction test starts with a wrong remembered guess, stages a voice transcript, confirms it, reloads the file, and verifies the next actual RTL result changes to the corrected label while another example is retained. Persistence, exact relabeling, rejection, capacity eviction, and stale-writer protection are covered. Mock helper processes also verify transcript/error transport and cancellation on exit. The full regression passed 28 test methods and 42 image simulations across memory and MLP suites. These synthetic samples test memory behavior, not real-world recognition accuracy or native voice transcription.
