# Real image neural network milestone

## What is implemented

This milestone connects a real photograph and pretrained model data to a hardware convolution arithmetic test. It also provides actual object detections from a full pretrained model executed in **software**. These are two different validation paths.

| Path | Implementation | Current evidence |
| --- | --- | --- |
| Full image detection | Torchvision SSDLite320 MobileNet V3 Large COCO_V1 on CPU | A public dog photograph produced a dog detection with score about 0.7493 |
| Learned first-layer arithmetic | Custom RTL packed convolution-patch engine and scratchpad | Eight real-image patch accumulators exported and reference-checked; ChipVerify execution pending |
| Pixel centering | Custom RTL RGB888 to signed INT8 stage | 256 RGB triplets and stall checks supplied in the same pending RTL bench |

The software detector covers the pretrained model's 80 COCO object categories. This is a baseline for model behavior, not a claim that all 80 classes now execute in custom RTL. One sample detection is a smoke test, not an accuracy evaluation.

## Reproducible image and weights

`examples/image_nn/vectors.json` records the original image URL and SHA256, the exact weights URL and SHA256, package versions, first-convolution identity, quantization, labels, software detections, packed input/weight words and expected INT32 accumulators.

- Image source: https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
- Weights source: https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth
- Model documentation: https://docs.pytorch.org/vision/main/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html

Original image and complete weights are downloaded to ignored `build/image_nn/` and are not redistributed in this repository. Observe the upstream model/data usage terms for your application. Only compact test patches and two output-channel filters are embedded in the test vectors.

Example CPU setup and execution:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-image.txt --index-url https://download.pytorch.org/whl/cpu
python3 scripts/prepare_image_nn.py
```

To try your own image while keeping the committed sample vectors unchanged:

```sh
python3 scripts/prepare_image_nn.py --image /path/to/photo.jpg --output build/my_image
```

Software inference returns labels, confidence scores and boxes in original-image pixel coordinates. The committed reference run found dog with score 0.749295 and box approximately `[146.85, 41.29, 1472.19, 1144.48]` in the original photo. No object name is hardcoded as an RTL decision.

## Neural numerical contract

The exporter uses the actual model transform to normalize and resize the input to 320 by 320. It quantizes that normalized tensor to symmetric signed INT8 with scale 1/128, nearest-even rounding and saturation. Each first-layer output channel's weights are separately quantized with scale maxabs/127. A 3 by 3 RGB window contains 27 values; flattening order is channel, kernel row, kernel column. Zero padding is applied in the normalized feature domain, and the 28th packed element is zero. Each job therefore accumulates seven DOT4 word pairs. First convolution bias is absent in this model.

Eight patch sums (four spatial positions, two learned output channels) were independently checked against `torch.nn.functional.conv2d` in float64 using the same integer tensors. The integer sums are exactly representable in float64. The emitted result is an INT32 convolution accumulator, not a box, label or final model activation.

Batch normalization, first-layer nonlinearities, subsequent layers, detection heads and RTL box decoding/NMS are not included. Quantizing this isolated first layer does not make the full FP32 reference model an INT8 hardware-compatible model. Full model operator mapping, accuracy calibration, quantized activation behavior and scheduling remain future work.

`p04_rgb888_to_int8` independently converts each raw 8-bit RGB channel using `q=pixel-128`, preserving channel order R[23:16], G[15:8], B[7:0]. It is a ready/valid registered stage with synchronous reset and stall retention. It performs no resize. **It is not the SSD model's complete normalization pipeline** and is tested separately from the offline model-transformed patch vectors.

## Convolution patch engine interface

`p04_conv_patch_engine` extends the memory request/response approach from the previous DOT4 engine. It captures A base, B base, destination, bias accumulator and 16-bit `word_count`. Read both packed words, compute a DOT4 update, advance addresses by four bytes, and repeat. Write exactly one INT32 result after the final update. Arithmetic overflow wraps and latches a sticky overflow flag across all words; inference must avoid overflow rather than use wrapped values as correct results.

Zero count, unaligned commands or source spans overflowing the 32-bit address space complete with error without memory traffic. Physical scratchpad range errors are returned by memory; a later read error prevents destination write. Starts during busy are rejected. Completion follows the final write response. Reset flushes engine/response state but does not roll back accepted writes or clear RAM. The caller must provide exclusive memory ownership until completion and preinitialize all accessed words. Tail values must be explicitly zero-padded by the producer.

Patch extraction and the image-to-tensor transform currently run offline. The engine is an im2col-style **single output accumulation engine**, not an image-window scanner, full feature-map generator, full GPU, or complete neural network.

## Run in ChipVerify

Use a separate project or replace both editor contents with:

- `sim/chipverify_image/design.sv`
- `sim/chipverify_image/testbench.sv`

Choose Verilator (SystemVerilog), then compile with:

```text
--timing --top-module tb_p04_image_nn
```

Leave runtime arguments empty. Expected completed output:

```text
image_patch=0 expected_acc=... matched
...
image_patch=7 expected_acc=... matched
PASS Project04 real-image convolution patches
real_image_patches=8 jobs=13 pixel_triplets=256 host_checks=...
Scope: first learned convolution accumulations only; object labels come from software reference
```

The extra five jobs check multiword bias accumulation, sticky overflow, zero count, address-span overflow and a physical memory read error. The bench also checks failed jobs preserve the destination, input command capture through engine state, memory stalls and request stability. The existing memory suite retains its independent busy-rejection and reset tests.

For optional short waveforms add `--trace-vcd --trace-depth 1` to compile arguments and `+WAVES` to runtime arguments. A missing PASS, fatal error, timeout or file-size error is not a passing run.

## Validation

Completed: real pretrained software detection, eight patch sums cross-checked against independent convolution, Python vector/contract checks, static SV compilation and generated-bundle consistency. **Behavioral simulation of the new RTL remains pending ChipVerify execution.** No hardware detection latency, power or full-model accuracy is claimed.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/bundle_image_nn.py --check
python3 scripts/check_image_sv.py
```

Regenerate after edits using `python3 scripts/bundle_image_nn.py`. Edit `tb/tb_p04_image_nn.template.sv` and canonical RTL, not the generated testbench or bundles.
