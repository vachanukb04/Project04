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

No model or weights are included yet. Model training and software conversion are distinct from designing custom RTL.
