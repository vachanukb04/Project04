# Basic object detection with persistent correction learning

## What runs now

The default `learn` mode restores the pretrained detector used by the original Mac demo, then adds confirmed feedback memory. You no longer need to teach ordinary supported categories before the first guess. The model's COCO classes include **phone** (the model calls it `cell phone`), **laptop**, chair, keyboard, mouse, bottle, cup, book, person, dog, and many others. Support for a category does not guarantee detection in every view.

**This default is HYBRID:** the pretrained neural detector executes in **Python/PyTorch on your CPU**, while SystemVerilog executes appearance-descriptor extraction, confirmed-example L1 matching, similarity, and crop color/brightness. The complete pretrained detector has not been implemented in RTL. Startup, reports, and the overlay identify where a result came from.

This fixes the earlier feedback-only version, which could remember labels but had no knowledge of object names when memory was empty. That version is still available explicitly as `--recognizer rtl-only`.

The trained baseline is Torchvision `SSDLite320_MobileNet_V3_Large_Weights.COCO_V1`:
https://docs.pytorch.org/vision/main/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html . Phone/laptop recognition is generic: it does not identify an iPhone generation, AirPods variant, manufacturer specification, OCR text, tablet model, ID card fields, or a banknote denomination. Those require additional models or confirmed labels and cannot be inferred reliably from every image.

## Update and run on your Mac

Inside your existing checkout:

```bash
cd ~/Project04
git pull
source .venv-camera/bin/activate
python -m pip install -r app/requirements-hybrid-camera.txt
python app/mac_rtl_camera.py learn --speak --voice
```

This uses your existing local Icarus installation (`iverilog` and `vvp`). If missing, install it with `brew install icarus-verilog`; if `brew` is missing, follow https://brew.sh . To use native voice feedback, Apple command-line tools must be installed (`xcode-select --install` if needed). No ChipVerify server is used.

The new requirements include Torch, Torchvision, GUI OpenCV, NumPy and certifi. The official ~14 MB model downloads on first use and shares the original demo's cache under `build/image_nn/torch/`. Later starts use that cache. Keep SSL verification enabled: the code uses certifi if `SSL_CERT_FILE` is unset, and preserves explicit custom/enterprise CA settings. It reports model-download errors instead of silently reverting to an untrained classifier.

For spoken output with keyboard corrections only:

```bash
python app/mac_rtl_camera.py learn --speak
```

Allow Camera for Terminal/IDE and Microphone/Speech Recognition for the speech helper if prompted. The native helper requires on-device English speech recognition by default and is used only in short feedback windows. If unavailable, the app reports it and typed feedback works. Explicit `--allow-network-voice` permits Apple's speech service to process audio; it does not upload images. No silent network speech fallback occurs. Native Swift helper compilation and actual Mac microphone operation still need local Mac testing.

## Camera interaction

1. Place a clear object near the center of the preview, improve lighting/focus, then hold still for five seconds. The stability gate measures the center guide; the pretrained detector receives the **full captured frame** so a laptop is not cut down to the guide area.
2. Software detects supported objects. A center-weighted selection picks one target; non-person detections are preferred over a person when present, useful when holding an object. Other detected candidates remain in the JSON report.
3. The selected object's bounding crop goes into RTL for descriptor extraction, appearance-memory search and attributes. If there is no detection, the center crop is used instead.
4. A compatible confirmed memory with similarity >=0.94 may provide your learned name. Otherwise the pretrained object's name is used. If neither is available, the app asks for a name.
5. The captured frame freezes for feedback, with a selected bounding box and a thumbnail of the region that was actually compared. It does not draw an old box on a different live frame. Press **Space** to return to the next live capture.
6. Confirm or correct. Only explicitly confirmed examples change memory. Saved feedback loads after restart; no separate train command or 20-view collection is required.

The overlay distinguishes **pretrained detector score** from **memory similarity**. Neither is a calibrated guarantee of correctness. A previous confirmed name can still be wrong for another similar-looking object.

| Control | Action |
| --- | --- |
| Y | Confirm the guess, or save a staged correction |
| N | Reject the guess or discard a staged name |
| C | Type a name in the preview; Enter stages it, then Y saves it |
| V | Listen to another short voice correction, when enabled |
| Space | Next stable view; unsaved feedback is discarded |
| Q / Escape | Quit; Escape cancels typed entry while typing |

English voice commands include “Yes”, “No”, “No, these are AirPods”, “This is my phone”, “Call it my headphones”, and “Cancel”. Corrections are shown/read back before a subsequent yes saves them. Unrecognized conversation is not silently stored as a name. The captured image remains the one being labeled while you speak. The microphone is not an always-on ambient recorder. Typed entry is printable ASCII; OpenCV's rendering of non-ASCII voice labels is limited.

## Learning model and persistence

The learned component is an **episodic example model**, not online neural-network fine-tuning. The pretrained weights remain fixed. Confirmations accumulate distinct appearance examples for each name, gradually covering additional views. Manufacturer or exact product details remain unknown unless supplied as a user label; a user label is not independent proof of those details.

Default storage is **`build/rtl_camera/feedback/memory.json`**. It contains confirmed labels, RGB descriptors, confirmation counts, timestamps, and (for new hybrid captures) the base category and descriptor scope. It is local and ignored by Git. Keep this file to retain learning. `--memory /path/to/memory.json` selects another model file.

- Up to 64 confirmed views are retained. At capacity, the least recently confirmed example is evicted. The last 256 feedback events are retained.
- Exact descriptor/context duplicates are updated in place when corrected. Different views remain separate examples. Confirmations happen once per captured view.
- Context filtering prevents an example known to be a phone from overriding a newly detected laptop. Only examples for the same descriptor scope and compatible base category enter that RTL search.
- A similarity gate (default 0.94) prevents a weak appearance match from replacing the pretrained name. This can also miss legitimate memories when angle, lighting, scale, or the base detector category changes.
- Existing memory files are preserved. Old center-guide examples do not override newly detected-object crops because they describe different regions. They can still be used on the no-detection center-crop path or in `rtl-only` mode. Teaching one fresh hybrid view starts the new object-crop history; no old data is deleted automatically.
- Saving uses a file lock, revision check and atomic replacement. Do not run multiple camera processes writing the same memory.

The descriptor is still just 16x16 RGB high nibbles computed by RTL. Background and color can cause false matches. This is not a learned neural embedding and does not guarantee generalization to unseen angles. A pretrained embedding network is a future upgrade to the memory descriptor.

Inspect learned labels:

```bash
python app/mac_rtl_camera.py learn --inspect-memory
```

Optional controls:

```bash
python app/mac_rtl_camera.py learn --speak --threshold 0.35
python app/mac_rtl_camera.py learn --speak --memory-threshold 0.97
python app/mac_rtl_camera.py learn --recognizer rtl-only --speak
```

Lowering the detection threshold may reveal missed objects but increases false detections. Raising the memory threshold makes remembered names more conservative. RTL-only retains the previous nearest-example guessing behavior and does not load Torch or pretrained weights. It cannot name an unseen category without feedback.

## Offline check

```bash
python app/mac_rtl_camera.py learn --image /path/to/photo.jpg
python app/mac_rtl_camera.py learn --image /path/to/photo.jpg --teach "my phone"
python app/mac_rtl_camera.py learn --image /path/to/photo.jpg
```

`--teach` is an explicit user confirmation. Ordinary inference never writes confirmed memory. Pixel and JSON simulation diagnostics are saved locally under `build/rtl_camera/feedback/run/`; descriptors can reveal visual content, so treat them as camera data. No images or learned labels are uploaded by this code. Only initial model/package downloads and explicitly enabled network speech require network access.

## Verification and execution boundary

`app/rtl_camera/pretrained.py` owns software detection, target selection and hybrid result policy. `rtl/p04_visual_memory.sv` still owns nibble extraction, exact L1 search, distance/similarity and crop attributes. The bridge writes pixels/examples and reads actual simulator results; it does not compute the image distance in Python. `FeedbackSession` owns confirmation, and the memory file owns learned labels/context. The simulation-only testbench handles file IO. No synthesis, SDC, STA, FPGA integration or full pretrained RTL detector is claimed.

The combined path was executed on the existing real dog photograph with empty memory: pretrained software detected dog at score 0.749295, while actual Icarus RTL computed the crop attributes. After confirming `my dog` and reloading memory, another actual-model/RTL run returned `my dog` from confirmed memory at similarity 1.0. Policy tests use **controlled detections**, then actual RTL, to check phone/laptop selection, cold-start naming, confirmed correction overrides after reload, incompatible categories, weak-match rejection and unknown-category learning. These controlled detections do not measure real phone/laptop detector accuracy. Test those through your Mac camera.

Run regression tests:

```bash
python -m unittest discover -s tests -v
```

Native Mac camera, permission prompts, GUI, and Speech helper operation remain user-side tests. Actual accuracy depends on visibility, lighting, model coverage, and your confirmed examples.
