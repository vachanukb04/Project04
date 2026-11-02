# Verification status

## Restored pretrained basic naming with RTL feedback memory

Default camera feedback now uses a HYBRID path: pretrained SSDLite COCO naming in Python/PyTorch, followed by detected-object crop extraction and actual RTL descriptor/L1 search/attributes. A strong compatible confirmed memory can override the baseline name. The code exposes model provenance, detector score, memory similarity and prediction source separately. No claim is made that the pretrained model runs in RTL or that confirmations fine-tune its neural weights.

The complete regression passed 35 test methods (51 RTL image simulations across the memory, MLP and new hybrid policy tests). Hybrid tests use controlled software detections, then real RTL, to verify cold-start naming/confirmation, persistent user corrections, crop attributes, incompatible category filtering, weak-match fallback, and unknown-category learning. Controlled phone/laptop labels are policy fixtures, not measured phone/laptop recognition accuracy.

A separate real-model run on the existing public dog photo detected dog at score 0.749295 with empty feedback memory and computed the detected crop's attributes through Icarus. After confirming the name `my dog` and reloading persistent memory, a second actual-model/RTL run returned `my dog` from confirmed memory at similarity 1.0. Native Mac camera/preview/voice remains pending user testing; real phone/laptop recognition through the user's camera has not been measured here. See [current run guide](feedback_learning.md).


## Earlier RTL-only feedback milestone

That RTL-only feedback mode needs no manually collected dataset or pretrained model. RTL extracts RGB high-nibble descriptors, searches up to 64 confirmed examples with L1 distance, and returns visual similarity and crop attributes. The Mac handles camera/voice, staged confirmation, label lookup, and atomic persistent storage. This is episodic appearance matching, not semantic neural-network recognition or online weight training.

Development verification: the 12 new test methods passed, including 14 actual Icarus visual-memory simulations. Independent checks cover memory sizes through 64 examples, exact/extreme distance and ties, descriptors, reset cancellation, and input bubbles. A staged correction followed by confirmation changes the next actual RTL prediction and survives file reload; the other object's example is retained. Memory rejection, exact relabeling, eviction, and stale writers pass. Mock voice subprocess tests cover transcript/error transport and cancellation; they do not validate Apple transcription. The complete final regression passed all 28 test methods, including the prior MLP/arithmetic tests (42 image simulations across the new memory and existing MLP suites). Offline CLI teaching followed by a separate invocation correctly restores the learned label.

Native Swift helper compilation, on-device English speech support, microphone permission, live Mac camera/preview/speech, and real-object matching remain pending Mac testing. The development environment has no Swift/macOS SDK. See [feedback learning guide](feedback_learning.md).


## Local Mac-to-RTL classifier

The new `p04_camera_mlp` network executes complete custom-model inference in SystemVerilog: 768 inputs, 32 ReLU units, up to 16 classes, approximate softmax confidence/rejection, and crop attributes. The Mac adapter does not compute neural predictions and has no software detector fallback.

Development validation used Icarus Verilog 12.0 and Linux: 16 test methods passed, including 28 actual image simulations compared with an independent signed-integer reference. Cases cover random models/images, hidden saturation, 16-class output, all crop-color branches, score rejection and argmax ties. Each simulation cancels a partial input frame with reset and then processes the full frame with retained model memories. Model checksum rejection and five-real-second stability/motion/focus/gap behavior also passed. A CLI smoke test collected synthetic files offline, trained/exported a network, and classified synthetic red through RTL, reporting mean RGB [211, 11, 11], brightness 71, and red color.

The synthetic training validation split achieved 100%; this is a plumbing check on easy synthetic colors, **not evidence of real-object accuracy**. No pretrained general model ships with this path. Users must collect and train their own classes. Live macOS permission handling, capture, preview, speech, and fresh-object accuracy remain pending local user testing. No synthesis, FPGA or ASIC results are claimed. See [Mac RTL camera guide](rtl_camera.md).


## Mac camera app and camera-stream RTL

The local camera app's saved-image path detected dog at score 0.749295 and saved an annotated image and JSON report. Eleven Python tests passed in the development environment, including frame annotation and latest-frame capture helper checks. Tests used headless OpenCV 4.14.0.94 in Linux; live Mac AVFoundation capture, window display, permission prompts and speech were not exercised. The new abstract camera-stream RTL and testbench pass static compilation with zero diagnostics; their behavioral simulation is pending. The software detector does not execute the custom RTL. See [the execution boundary and run instructions](mac_camera.md).

## Real image neural network milestone

A CPU software run of pretrained SSDLite320 MobileNet V3 Large COCO_V1 detected dog with score approximately 0.7493 in the public PyTorch dog photograph. Eight quantized first-convolution patch accumulators were independently checked against torch conv2d. Nine Python test methods pass, including packed vector checks. The new five-file SystemVerilog suite passes static compilation with zero diagnostics; generated bundles match sources. The user supplied `PASS Project04 real-image convolution patches`, `real_image_patches=8 jobs=13 pixel_triplets=256 host_checks=132`, and normal Verilog finish. This is user-reported first-layer integration evidence, not full RTL object detection. See [the detailed scope](image_nn.md): this pretrained COCO detector remains software-only; that milestone's RTL implements pixel centering and first-layer accumulation. The separate tiny custom-class MLP above now provides complete RTL classification.

## Memory engine integration

The scratchpad and memory-backed DOT4 controller are implemented with a separate integration testbench. Its four canonical files pass static compilation with zero diagnostics using pyslang 12.1.0; its generated bundle passes consistency checking. **User-reported ChipVerify behavioral simulation passed:** `PASS Project04 memory-backed DOT4 engine`, followed by `jobs=7 host_checks=21 request_stalls=2 response_stalls=4` and a normal Verilog `$finish`. This confirms completion of this deterministic integration suite, including exercised request and response backpressure. The simulator version and full compile transcript were not supplied; this was not independently rerun in the assistant browser. See [the memory-engine specification and run instructions](memory_engine.md). The arithmetic-run history below is separate from this new integration status.

## Completed checks

- Python numerical reference: **7 unittest methods passed**, covering packed signed operands, wrap/overflow, rounding ties and neighbors, zero/extreme multipliers, all shift values, activation clamps, invalid configuration and invalid reference API inputs.
- Static SystemVerilog compilation: **4 canonical source files parsed, type-checked and elaborated with zero diagnostics** using pyslang 12.1.0.
- Generated ChipVerify bundle consistency: checked against canonical sources with `scripts/bundle_chipverify.py --check`.

These checks are not a behavioral RTL simulation.

## Standalone arithmetic regression history

ChipVerify Lab was opened, the design and testbench bundles were loaded, Verilator was selected, and a simulation was requested. The platform responded: **Please sign in with Google to run simulations**. Its subsequent sign-in page also states that continuing agrees to ChipVerify's Terms and Conditions. No behavioral simulator result or passing RTL regression is claimed.

The user subsequently reported a successful platform status in Safari, followed by a traced run reporting **VCD output exceeded 100 MB**, **File size limit exceeded**, and a core-dump/timeout message alongside a green success banner. The project-specific PASS line and counters have not been supplied. The resource-limited run is incomplete or failed evidence; it does not establish an arithmetic PASS or an RTL arithmetic failure.

The testbench now separates the full untraced regression from a `+WAVES` smoke run of 520 cycles. Only the full run can print `PASS Project04 arithmetic regression` and must report `exhaustive_byte_pairs=65536`. The waveform run prints `PASS Project04 waveform smoke test (not full regression)` and reports zero exhaustive pairs. Static compilation and bundle consistency were rechecked for this change; the revised modes still need execution in ChipVerify.

The testbench is designed to exercise:

- Every one of the 65536 signed INT8 bit-pattern pairs in one DOT4 byte position with the other products zero.
- Directed four-product extremes, mixed signs, zero values, and INT32 overflow.
- Directed and deterministic random eight-lane vectors, active masks, inactive accumulator preservation, and lane-specific overflow.
- Positive and negative rounding ties, shift zero and large shifts, zero multiplier, signed zero points, saturation, activation clamps, and invalid clamp ordering.
- Input bubbles, output stalls, held requests, simultaneous consume/replace and reset with pending data.
- A drained final state, required scenario counters, explicit failures and a watchdog.

The random seed is `32'hc0ffee04`; the test is deterministic. Scenario counts printed by the bench are evidence only after a completed simulator run. Exhaustive pair coverage does not imply exhaustive coverage of four-byte combinations, accumulator states or pipeline transactions.

## Reproduce non-simulation checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/bundle_chipverify.py --check
pip install -r requirements-check.txt
python3 scripts/check_sv.py
```

## Evidence to record after simulation

Record the Git commit, bundle hashes, simulator/version, compile/runtime arguments, all warnings, exit result, PASS summary and printed counts. Then change this page to distinguish the completed run from the earlier authentication blocker. Keep model accuracy and hardware timing evidence separate from arithmetic functional checks.
