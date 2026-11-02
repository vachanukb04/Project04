"""Camera-independent adapter. No neural inference in this module: launch real RTL."""
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from .model import load_model, COLORS

ROOT = Path(__file__).resolve().parents[2]

def compile_simulator(build):
    build=Path(build).resolve();build.mkdir(parents=True,exist_ok=True)
    for tool in ('iverilog','vvp'):
        if shutil.which(tool) is None:
            raise RuntimeError(f'Missing {tool}. Install Icarus Verilog (Mac: brew install icarus-verilog). No software-inference fallback is used.')
    executable=build/'camera_mlp.vvp'
    result=subprocess.run(['iverilog','-g2012','-s','tb_p04_camera_mlp','-o',str(executable),
        str(ROOT/'rtl/p04_camera_mlp.sv'),str(ROOT/'tb/tb_p04_camera_mlp.sv')],capture_output=True,text=True,timeout=60)
    if result.returncode: raise RuntimeError('RTL compilation failed:\n'+result.stdout+result.stderr)
    return executable

def infer_rtl(rgb,model_dir,build,executable,threshold=153):
    if not 0<=threshold<=255: raise ValueError('Threshold must be 0..255')
    model_dir=Path(model_dir).resolve();build=Path(build).resolve()
    metadata,_=load_model(model_dir) # Validate memory files; do not calculate predictions.
    rgb=np.asarray(rgb)
    if rgb.shape!=(16,16,3) or rgb.dtype!=np.uint8:raise ValueError('Expected uint8 RGB 16x16x3')
    frame=build/'frame.hex';result=build/'result.txt'
    result.unlink(missing_ok=True)
    frame.write_text(''.join(f'{int(r):02x}{int(g):02x}{int(b):02x}\n' for r,g,b in rgb.reshape(-1,3)))
    run=subprocess.run(['vvp',str(executable),f'+MODEL={model_dir}',f'+FRAME={frame}',
        f'+RESULT={result}',f'+CLASSES={len(metadata["labels"])}',f'+THRESHOLD={threshold}'],
        capture_output=True,text=True,timeout=60)
    if run.returncode or not result.exists():raise RuntimeError('RTL simulation failed:\n'+run.stdout+run.stderr)
    values=[int(v) for v in result.read_text().split()]
    if len(values)!=7:raise RuntimeError('Malformed RTL result')
    c,confidence,r,g,b,brightness,color=values
    if c!=255 and not 0<=c<len(metadata['labels']):raise RuntimeError('Invalid RTL class ID')
    if not 0<=color<len(COLORS) or any(not 0<=v<=255 for v in values):raise RuntimeError('Invalid RTL attributes')
    report={'execution':'SystemVerilog RTL simulated with Icarus; no Python neural inference',
        'class_id':c,'label':'unknown' if c==255 else metadata['labels'][c],
        'confidence_q8':confidence,'confidence_score':confidence/255,
        'confidence_note':'approximate softmax score, not calibrated correctness probability',
        'crop_mean_rgb':[r,g,b],'crop_brightness':brightness,'crop_color':COLORS[color],
        'manufacturer':'unknown','product_model':'unknown','rtl_values':values}
    (build/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

class Stability:
    """Five seconds of low motion AND adequate sharpness using monotonic wall time."""
    def __init__(self,seconds=5.,motion_limit=2.5,sharpness_min=30.):
        self.seconds=seconds;self.motion_limit=motion_limit;self.sharpness_min=sharpness_min
        self.previous=None;self.since=None;self.last_time=None
    def reset(self):
        self.previous=None;self.since=None;self.last_time=None
    def update(self,gray,sharpness,now):
        gray=np.asarray(gray,dtype=np.float32)
        motion=float('inf') if self.previous is None else float(np.abs(gray-self.previous).mean())
        # A blocked/stalled camera must not accrue a stability interval.
        gap=self.last_time is not None and now-self.last_time>.5
        if motion>self.motion_limit or sharpness<self.sharpness_min or gap:self.since=None
        elif self.since is None:self.since=now
        self.previous=gray.copy();self.last_time=now
        elapsed=0. if self.since is None else max(0.,now-self.since)
        return elapsed>=self.seconds,elapsed,motion
