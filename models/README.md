# Model selection and numerical reference

Select a compact trained object detector covering a broad set of everyday categories. The exact model and supported category count remain open until its graph, quality, and hardware cost are profiled.

Record these before inference RTL is frozen:

- Model source, version, license, artifact hashes, and class-name mapping.
- Input shape, color order, resize or letterbox transform, and normalization.
- Layer operations, tensor shapes, layouts, strides, weights, and biases.
- Quantization scales and zero points, rounding, saturation, and padding rules.
- Detection decoding, score thresholds, duplicate suppression, and target selection.
- MAC count, peak live tensors, memory traffic, and held-out recognition quality.
- Golden intermediate tensors and expected detections for repeatable tests.

No complete model weights are redistributed; compact learned-filter test vectors are included. Model training and software conversion are distinct from designing custom RTL.

## Selected software baseline

SSDLite320 MobileNet V3 Large COCO_V1 supplies a pretrained software detector with 80 object categories. Its source, weight hash, sample image provenance, software detections and first-layer patch vectors are recorded in `examples/image_nn/vectors.json`. See [the real-image milestone](../docs/image_nn.md). This selects a baseline for investigation, not a frozen end-to-end RTL-compatible quantized graph. Full model operator mapping and accuracy calibration remain open.
