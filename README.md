# Project04

## Everyday object recognition for smart glasses

Custom CPU and GPU hardware in SystemVerilog for looking at an everyday object, identifying it, and displaying or speaking its name.

The first development target is a verified inference datapath operating on stored images. Live camera input, spoken or displayed names, and glasses integration follow that foundation.

## Initial scope

- Recognize a broad set of everyday objects supported by the selected trained detector; recognition is not restricted to chairs.
- Develop and verify arithmetic units, memory movement, neural-network kernels, and a programmable SIMD compute engine.
- Use ChipVerify Lab for SystemVerilog simulation and waveform inspection.
- Begin with stored images and a software numerical reference before adding live camera input.
- Defer CPU firmware, FPGA selection, and wearable integration.

## Current status

Project structure only. No trained model has been selected, no RTL has been implemented, and no simulation or object-recognition result is claimed.

## Repository structure

| Directory | Purpose |
| --- | --- |
| `rtl/` | Synthesizable SystemVerilog modules |
| `tb/` | Self-checking testbenches and compact test vectors |
| `models/` | Model selection, numerical contract, class map, and artifact metadata |
| `docs/` | Architecture decisions, verification plan, and simulator workflow |

## Proposed data flow

```mermaid
flowchart TD
    Input["Stored image first, camera later"] --> Prep["Resize and quantize"]
    Prep --> Compute["Programmable SIMD compute engine"]
    Weights["Trained detector weights"] --> Compute
    Compute --> Decode["Decode detections and select target"]
    Decode --> Display["Display object name"]
    Decode --> Audio["Speak object name"]
```

The trained detector provides recognition through its learned weights. The custom hardware executes its calculations. The eventual CPU controls jobs and application behavior; the GPU subset executes parallel kernels. Model selection determines the required operators, tensor memory, and compute capacity.

This diagram describes planned behavior. No end-to-end inference system, display driver, audio driver, or trained model is implemented yet.

## First milestones

1. Select and profile a compact pretrained detector covering many everyday object categories.
2. Freeze tensor shapes, weights, quantization rules, supported operations, and class labels.
3. Implement a packed signed INT8 dot-product unit with INT32 accumulation and verify it against a software reference.
4. Implement and verify requantization, then one real convolution layer.
5. Integrate the supported model and validate full detections on stored images.

The eventual system includes a custom CPU and programmable parallel compute engine. CPU integration, live capture, audio, and display output follow numerical correctness of the inference datapath.

## Simulation

See [the ChipVerify workflow](docs/chipverify.md). Source files and testbenches will be versioned here; run logs and waveform dumps are generated outputs.

## Model artifacts

Do not commit third-party model weights until the model, redistribution permissions, provenance, and artifact size have been reviewed. Record exact hashes and acquisition instructions alongside the numerical reference.

## License

No project license has been selected. Third-party artifacts retain their own licenses and terms.
