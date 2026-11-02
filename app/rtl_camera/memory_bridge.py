"""File transport for RTL descriptor extraction, nearest-neighbor search, attributes."""
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
from .bridge import ROOT
from .feedback import descriptor_values,CAPACITY
from .model import COLORS

def compile_memory(build):
    build=Path(build).resolve();build.mkdir(parents=True,exist_ok=True)
    for tool in ('iverilog','vvp'):
        if shutil.which(tool) is None:raise RuntimeError(f'Missing {tool}: install Icarus Verilog first (brew install icarus-verilog).')
    executable=build/'visual_memory.vvp'
    run=subprocess.run(['iverilog','-g2012','-s','tb_p04_visual_memory','-o',str(executable),
        str(ROOT/'rtl/p04_visual_memory.sv'),str(ROOT/'tb/tb_p04_visual_memory.sv')],capture_output=True,text=True,timeout=60)
    if run.returncode:raise RuntimeError('RTL compile failed:\n'+run.stdout+run.stderr)
    return executable

def infer_memory(rgb,examples,build,executable):
    rgb=np.asarray(rgb)
    if rgb.shape!=(16,16,3) or rgb.dtype!=np.uint8:raise ValueError('Expected uint8 RGB 16x16')
    if len(examples)>CAPACITY:raise ValueError('Too many examples')
    build=Path(build).resolve();build.mkdir(parents=True,exist_ok=True)
    frame=build/'memory_frame.hex';memory=build/'memory_examples.hex'
    result=build/'memory_result.txt';descriptor=build/'memory_descriptor.hex'
    result.unlink(missing_ok=True);descriptor.unlink(missing_ok=True)
    frame.write_text(''.join(f'{int(r):02x}{int(g):02x}{int(b):02x}\n' for r,g,b in rgb.reshape(-1,3)))
    memory.write_text(''.join(f'{v:x}\n' for ex in examples for v in descriptor_values(ex['descriptor'])))
    run=subprocess.run(['vvp',str(executable),f'+MEMORY={memory}',f'+FRAME={frame}',
        f'+RESULT={result}',f'+DESCRIPTOR={descriptor}',f'+COUNT={len(examples)}'],capture_output=True,text=True,timeout=60)
    if run.returncode or not result.exists() or not descriptor.exists():raise RuntimeError('RTL memory simulation failed:\n'+run.stdout+run.stderr)
    values=[int(v) for v in result.read_text().split()]
    if len(values)!=8:raise RuntimeError('Invalid RTL output')
    slot,similarity,distance,r,g,b,brightness,color=values
    if (slot==255)!=(len(examples)==0) or (slot!=255 and not 0<=slot<len(examples)):
        raise RuntimeError('Invalid RTL memory slot')
    if not 0<=similarity<=255 or not 0<=distance<=11520 or not 0<=color<len(COLORS) or any(not 0<=v<=255 for v in (r,g,b,brightness)):
        raise RuntimeError('Invalid RTL attributes')
    features=descriptor_values([int(v,16) for v in descriptor.read_text().split()])
    report={'execution':'SystemVerilog descriptor, L1 search, similarity and crop attributes',
        'recognition':'confirmed-example memory; no pretrained semantic inference',
        'best_slot':slot,'label':examples[slot]['label'] if slot!=255 else 'unknown',
        'similarity_q8':similarity,'similarity_score':similarity/255,
        'distance':distance,'crop_mean_rgb':[r,g,b],'crop_brightness':brightness,'crop_color':COLORS[color],
        'descriptor':features,'manufacturer':'unknown','product_model':'unknown'}
    (build/'memory_result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
