# Mac camera -> real SystemVerilog inference -> overlay and speech

**For learning from confirmations/corrections without a 20-view dataset, use the newer [feedback learning mode](feedback_learning.md): `python app/mac_rtl_camera.py learn --speak --voice`.** This page describes the separate offline-trained MLP path, which still requires labeled captures. Default feedback mode now combines pretrained software detection with RTL appearance memory; use `--recognizer rtl-only` for memory without software detection. This remains separate from the neural network described below.

This is a small **custom-trained, single-center-crop classifier**, not the earlier pretrained COCO software detector. It has no pretrained everyday-object model. Collect labeled examples of your objects, train once, and run the exported network in actual RTL simulation. Up to 16 trained labels are supported. General everyday detection, multiple boxes, OCR, manufacturer recognition, and exact product identification are not implemented here.

## Execution boundary

| Operation | Implementation |
| --- | --- |
| Mac camera permission and capture | Python/OpenCV, macOS AVFoundation backend |
| Live preview, center square, stability and focus check | Python/OpenCV using capture timestamps |
| Offline model training and weight export | NumPy quantization-aware training; not inference |
| Resize center crop to 16x16 RGB | Camera adapter, matching offline training |
| Input quantization and both neural layers | `rtl/p04_camera_mlp.sv` |
| Winning class, approximate confidence and rejection | RTL |
| Crop mean RGB, brightness and coarse color | RTL |
| Display text and speak the RTL result | Camera adapter / macOS `say` |

Python is used for transport, UI, and offline training. **It does not execute the live recognition network.** `bridge.infer_rtl` compiles/launches Icarus and reads a result emitted by the SystemVerilog testbench. It never calls the verification reference or the old PyTorch detector. A missing simulator or invalid model is a hard error; there is no software detection fallback. The Mac camera adapter is not a native Swift application.

No ChipVerify, custom simulator, elaboration tool, synthesis, SDC generation, or STA development is part of this change. Icarus is an existing local simulator: https://steveicarus.github.io/iverilog/ . Its compiler is `iverilog`; its execution runtime is `vvp`.

## Mac setup

Inside your existing Project04 checkout:

```bash
git pull
source .venv-camera/bin/activate
python -m pip install -r app/requirements-rtl-camera.txt
brew install icarus-verilog
iverilog -V
vvp -V
```

The `brew` command assumes Homebrew is already installed (https://brew.sh). If you do not have it, install Homebrew using its official instructions, then reopen Terminal. This adds a local simulator; you do not need ChipVerify. Keep your working Python environment; this path needs only NumPy and GUI OpenCV, not Torch or downloaded pretrained weights. Do not install `opencv-python-headless` on the Mac used for preview.

## 1. Collect training views

Choose at least two and at most sixteen labels. Start with visually distinct objects. Include an `other` class with empty backgrounds and unrelated objects; this helps but does not guarantee rejection of unseen objects.

```bash
python app/mac_rtl_camera.py collect --label phone
python app/mac_rtl_camera.py collect --label airpods
python app/mac_rtl_camera.py collect --label other
```

For each command:

1. Allow Terminal or your IDE to access Camera in macOS Privacy & Security.
2. Place a single object inside the center square. The square is a fixed crop, not an RTL-generated bounding box.
3. Hold it in focus and steady. Five continuous stable seconds trigger one local PNG capture. Motion, poor sharpness, or a frame gap over 0.5 seconds reset the timer.
4. Press **Space**, rotate/reposition the object, then hold it steady again. The preview guides each view. The camera does not move itself.
5. Collect **at least 20 different captures per class** (50+ is preferable), then press **Q**. Repeat for every label.

Vary angle, scale, lighting, hand position, and backgrounds. Keep backgrounds balanced across classes, or this tiny model can learn your desk rather than the object. The user supplies the training label; it is not an automatically discovered label. Captures live under ignored `build/rtl_camera/data/<label>/`. Nothing is uploaded.

Use `--camera 1` for another camera. If capture never triggers, improve lighting/focus first. `--sharpness 15` lowers the focus gate; `--motion 3.5` relaxes the frame-difference gate. These are approximate image-quality checks, not guaranteed blur or object-motion detection. Duplicate frames delivered by a malfunctioning driver cannot reliably be distinguished from an absolutely static scene.

## 2. Train once and export the learned memories

```bash
python app/mac_rtl_camera.py train
```

This trains a small 768 -> 32 ReLU -> N-class MLP, with quantized weights/activations in the forward pass. It exports `w1.hex`, `b1.hex`, `w2.hex`, `b2.hex`, and a checksummed `model.json` to ignored `build/rtl_camera/model/`. Training is deterministic with seed 4; default 400 epochs. `--epochs 800` can extend training.

A stratified random 80/20 capture split reports integer-model validation accuracy. Adjacent captures can be highly correlated, so **this number is not a measured deployment accuracy**. Test fresh capture sessions, backgrounds, and objects. Very small images and a shallow network limit viewpoint robustness and fine product detail. A larger pretrained/quantized model is a future upgrade, not silently substituted software inference.

## 3. Run your camera through RTL

```bash
python app/mac_rtl_camera.py run --speak
```

The app compiles the SystemVerilog once. After a five-second stable view, it writes 256 RGB pixels, configures the RTL weights, simulates inference, reads the RTL output, overlays it, and speaks it. Preview remains active while a worker runs simulation. Press **Space** to rearm for a different view. Press **Q/Escape** to exit. Speech uses macOS `say`; omit `--speak` for silent operation.

Output includes label, approximate score, crop color, mean RGB, and brightness. Detailed results and the latest input pixel file live under `build/rtl_camera/run/`. This path deliberately saves the last resized frame/result for debugging, overwriting the previous result. Training mode saves captures explicitly after each stable interval.

The score is an approximate fixed-point softmax score, **not a calibrated probability that the identification is correct**. Default rejection threshold is 0.60 (`--threshold 0.8` raises it). Unseen objects may receive high scores; threshold rejection alone is not an out-of-distribution detector. The `other` class is spoken as `other`; below-threshold results are `unknown`.

Colors and brightness describe the **whole center crop**, including background. They do not segment the object's surface. No object location, physical dimensions, material, OCR text, manufacturer, model generation, or product specifications are inferred. Manufacturer and product model are explicitly `unknown`, even if a user-trained label happens to be a brand name.

## Offline image test

```bash
python app/mac_rtl_camera.py image --image /absolute/path/to/photo.jpg
```

This applies the same center crop and resize, runs the same actual RTL, and prints JSON without opening a camera. It requires your trained model, just like live mode.

## RTL interface and numerical contract

- Fixed input 16x16 RGB888, row-major, 256 accepted pixels; RGB is `pixel_rgb[23:16]`, green `[15:8]`, blue `[7:0]`.
- Configure all weight/bias RAMs while idle. `cfg_kind`: 0 = W1 (24,576 signed INT8), 1 = B1 (32 signed INT32), 2 = W2 (512 signed INT8, including padded classes), 3 = B2 (16 signed INT32). Weight layout is output-channel-major.
- `start` is accepted only while idle with `cfg_valid=0` and class_count in 2..16. Capture class_count and min_confidence on start. Wait for `pixel_ready`; assert `pixel_valid` for each supplied pixel. Source gaps are supported. Busy configuration/start attempts are ignored.
- Input Q3: `(pixel_byte >> 4) - 8`. W1 is Q6; B1 is Q9. Hidden accumulator uses signed INT32; arithmetic right shift 4 then clamp 0..127 gives unsigned Q5 ReLU.
- W2 is Q6; B2 and output logits are Q11. All 32 MACs execute in RTL. Exported biases are bounded to +/-2^24; at these dimensions the signed INT32 accumulator cannot overflow with valid memories.
- Argmax ties pick the first class. Approximate softmax uses `round(65535 * exp(-k/4))` for k=floor(logit_difference/512), 0..31; larger differences contribute zero. Confidence is floor(65535*255/sum), with max class contributing 65535. `class_id=255` when score is below min_confidence.
- `mean_r/g/b = channel_sum >> 8`. Brightness = `(77*R + 150*G + 29*B) >> 8`. Color IDs: 0 dark, 1 white, 2 mixed/neutral, 3 red, 4 green, 5 blue. These are coarse heuristics.
- Result outputs hold until a later result; `result_valid` pulses one cycle. Reset cancels an in-flight frame and clears outputs/control, but not model RAM. There is no partial-frame timeout in the hardware; a future camera interface must supply exactly 256 pixels or reset/restart.
- Testbench file IO (`$readmemh`, `$fdisplay`) is simulation-only. The neural-network module has register/array/MAC control logic; actual FPGA memory mapping, divider cost, clock closure, area, and power have not been evaluated. A hardware weight loader and camera preprocessing interface remain necessary for FPGA integration.

## Verification and limitations

Run the regression with Icarus and the Python dependencies installed:

```bash
python -m unittest discover -s tests -p 'test_rtl_camera.py' -v
```

It executes actual compiled RTL against an independent integer reference for randomized weights/images, saturation, all color branches, confidence rejection/ties, and a trained synthetic red/green dataset. It also verifies model checksum rejection and the real-time stability timer. Synthetic color samples validate the data path and training/export plumbing; they do not demonstrate recognition of phones, AirPods, or arbitrary real objects.

Live macOS capture, permissions, GUI, and speech must be checked on your Mac. No real-camera accuracy, latency, FPGA throughput, or ASIC implementation claim is made. The previously working `app/mac_camera.py` remains a separate software-only demo; use **`mac_rtl_camera.py`** for this RTL path.
