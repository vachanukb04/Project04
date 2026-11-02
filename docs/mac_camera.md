# Mac live camera recognition

## Execution boundary

`app/mac_camera.py` is a native local Python desktop program. It opens your Mac camera through OpenCV's AVFoundation backend, runs the pretrained SSDLite320 detector on the CPU, and displays bounding boxes, names and scores on the matching captured frame. A capture thread continually drains the stream so inference uses the latest available frame. Frame rate depends on your Mac; no real-time deadline is guaranteed.

**Full object recognition currently executes in software. The app does not invoke the custom RTL or claim FPGA/ASIC inference.** A normal Mac cannot execute SystemVerilog as native camera software. The RTL needs simulation or a hardware device plus a host bridge. The existing RTL implements selected neural arithmetic; the complete model is not yet mapped into it.

## Install and launch on Mac

Use a supported Python version with compatible PyTorch/OpenCV wheels (Python 3.11 or 3.12 is a practical starting point). From the repository directory:

```sh
git pull
python3 -m venv .venv-camera
source .venv-camera/bin/activate
python -m pip install -r app/requirements-mac.txt
python app/mac_camera.py
```

Use normal PyPI for Mac, not the Linux CPU-wheel index used by the development container. Install dependency versions offered for your Mac architecture and macOS version. The first run downloads approximately 14 MB of official pretrained weights to ignored `build/image_nn/torch/`. Camera frames are processed locally; the program does not upload them. No captures are saved unless you press S or explicitly run image-file mode.

Allow the camera access prompt for the Terminal or IDE launching Python. If access was denied, enable that application under **System Settings > Privacy & Security > Camera**, then restart it. See [Apple's camera-access guide](https://support.apple.com/guide/mac-help/control-access-to-your-camera-mchlf6d108da/mac). An external camera may use `--camera 1` instead of index zero.

```sh
python app/mac_camera.py --camera 1
python app/mac_camera.py --speak
python app/mac_camera.py --threshold 0.6
```

Q, Escape, or closing the window exits. S writes a local annotated PNG and JSON report to ignored `build/camera_snapshots/`. Optional speech uses the Mac's `/usr/bin/say`, choosing the highest-scored detected object at most once every four seconds while the prior speech process is idle. Camera/speech/GUI behavior must be tested on your Mac; the remote development environment cannot open your local webcam.

## Saved-image test without webcam or GUI

```sh
python app/mac_camera.py --image /path/to/photo.jpg --output build/camera_test
```

This runs the exact same detection and annotation functions used by live capture and saves boxes, labels and scores in PNG/JSON output. Compare the boxes against the visible objects; scores are model outputs, not certainty. The model supports its 80 COCO categories and can miss or misidentify unfamiliar, small, obscured or poorly lit objects.

## New RTL camera stream block

`p04_camera_capture` accepts a same-clock RGB888 stream with `pixel_valid`, `pixel_ready`, `pixel_sof` and `pixel_rgb`. `FRAME_PIXELS` is a positive parameter, at most 2^30; default 16. It emits one 32-bit memory write request per accepted pixel, with addresses 0, 4, 8, ... and data `0x00RRGGBB`. A one-entry output buffer holds payload stable under memory backpressure. `frame_done` pulses only when the final pixel write is accepted; `frame_id` increments then.

The source must hold a valid pixel and SOF stable while not ready. A non-SOF pixel outside a frame raises `frame_error` and is discarded. A new SOF during an incomplete frame raises `frame_error` and restarts at address zero; earlier writes are not rolled back. With a single buffer, frame consumers must finish before the producer overwrites it. Active-low synchronous reset clears transaction/frame state, not external memory.

The output is a write-acceptance interface, not the earlier scratchpad response protocol: an eventual bridge must supply write=true, byte strobes, response/error handling and suitable memory ownership. A real camera unable to backpressure needs a FIFO/drop policy and any required clock-domain crossing. **USB camera enumeration, sensor configuration, raw Bayer processing, CSI reception, CDC, camera-to-Mac USB bridging and neural inference are not part of this block.** It is not connected to the Mac app yet.

For its independent ChipVerify test, load `sim/chipverify_camera/design.sv` and `sim/chipverify_camera/testbench.sv`, choose Verilator, and use:

```text
--timing --top-module tb_p04_camera_capture
```

Leave runtime arguments empty. Require `PASS Project04 camera capture stream` and `pixels=4 frames=1 stray_pixel_errors=1`. The test checks pixel packing, addresses, stalls, frame completion, stray-pixel rejection and reset. Its behavioral execution remains pending; static compilation is checked.

## Current validation

The saved-image path is tested in the development container using the public dog sample. Live camera permission, capture, display and speech require a local Mac run. RTL camera capture is statically compiled and has a self-checking testbench, but is not a complete webcam-to-RTL detector.
