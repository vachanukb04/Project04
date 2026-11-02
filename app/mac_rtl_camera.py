#!/usr/bin/env python3
"""Capture/train/run a small custom-class RTL classifier. No software detection fallback."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import re
import subprocess
import threading
import time
import cv2
import numpy as np
from rtl_camera.bridge import Stability, compile_simulator, infer_rtl
from rtl_camera.model import train, load_model

ROOT=Path(__file__).resolve().parents[1]
TITLE='Project04 RTL | Q quit | SPACE next view'

class Camera:
    def __init__(self,index):
        backend=cv2.CAP_AVFOUNDATION if platform.system()=='Darwin' else cv2.CAP_ANY
        self.cap=cv2.VideoCapture(index,backend)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError('Cannot open camera. Allow Terminal/IDE camera access in macOS Privacy & Security. Try --camera 1.')
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.lock=threading.Lock();self.frame=None;self.seq=0;self.error=None;self.timestamp=0.
        self.stop=threading.Event();self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
    def read(self):
        misses=0
        try:
            while not self.stop.is_set():
                ok,frame=self.cap.read()
                if not ok:
                    misses+=1
                    if misses>=20:raise RuntimeError('Camera stopped returning frames')
                    time.sleep(.05);continue
                misses=0
                with self.lock:self.frame=frame;self.seq+=1;self.timestamp=time.monotonic()
        except Exception as exc:self.error=str(exc)
    def latest(self):
        with self.lock:return self.seq,self.timestamp,None if self.frame is None else self.frame.copy()
    def close(self):
        self.stop.set();self.thread.join(timeout=2);self.cap.release()

def crop_frame(frame):
    h,w=frame.shape[:2];side=int(min(h,w)*.65);x=(w-side)//2;y=(h-side)//2
    return frame[y:y+side,x:x+side],(x,y,side)

def rgb_input(crop):
    return cv2.cvtColor(cv2.resize(crop,(16,16),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)

def train_captures(args):
    labels=sorted(p.name for p in args.data.iterdir() if p.is_dir() and list(p.glob('*.png')))
    if not 2<=len(labels)<=16:raise RuntimeError('Collect between 2 and 16 classes before training.')
    images=[];targets=[]
    for c,label in enumerate(labels):
        for path in sorted((args.data/label).glob('*.png')):
            image=cv2.imread(str(path))
            if image is None:raise RuntimeError(f'Unreadable capture: {path}')
            images.append(rgb_input(image));targets.append(c)
    train(np.stack(images),targets,labels,args.model,args.epochs)

def main():
    if len(sys.argv)>1 and sys.argv[1]=='learn':
        from mac_feedback_camera import main as feedback_main
        feedback_main(sys.argv[2:])
        return
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode',choices=['collect','train','run','image','learn'])
    ap.add_argument('--label',help='Class name when collecting, for example phone')
    ap.add_argument('--data',type=Path,default=ROOT/'build/rtl_camera/data')
    ap.add_argument('--model',type=Path,default=ROOT/'build/rtl_camera/model')
    ap.add_argument('--build',type=Path,default=ROOT/'build/rtl_camera/run')
    ap.add_argument('--image',type=Path)
    ap.add_argument('--camera',type=int,default=0)
    ap.add_argument('--epochs',type=int,default=400)
    ap.add_argument('--threshold',type=float,default=.60)
    ap.add_argument('--sharpness',type=float,default=30.,help='Minimum Laplacian variance; lower only if lighting is good but capture never triggers')
    ap.add_argument('--motion',type=float,default=2.5,help='Maximum mean gray difference between frames')
    ap.add_argument('--speak',action='store_true')
    args=ap.parse_args()
    if not 0<=args.threshold<=1:ap.error('threshold must be 0..1')
    if args.epochs<1 or args.motion<=0 or args.sharpness<0:ap.error('Invalid epochs/motion/sharpness')
    if args.mode=='train':train_captures(args);return
    executable=None
    if args.mode in ('run','image'):
        if not (args.model/'model.json').exists():
            ap.error('No trained model. First collect >=20 views for each of >=2 classes, then use train. No pretrained general detector is included.')
        metadata,_=load_model(args.model)
        print('RTL classes:',', '.join(metadata['labels']),flush=True)
        executable=compile_simulator(args.build)
    if args.mode=='image':
        if args.image is None:ap.error('image mode requires --image PATH')
        frame=cv2.imread(str(args.image))
        if frame is None:ap.error('Could not read image')
        report=infer_rtl(rgb_input(crop_frame(frame)[0]),args.model,args.build,executable,round(args.threshold*255))
        print(json.dumps(report,indent=2));return
    if args.speak and platform.system()!='Darwin':ap.error('--speak requires macOS')
    if args.mode=='collect':
        if not args.label or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,47}',args.label):
            ap.error('collect requires --label with 1..48 letters/numbers/spaces/_/-')
        folder=args.data/args.label;folder.mkdir(parents=True,exist_ok=True)
        print('Collect at least 20 varied views per class. Include an other/background class. Captures stay local.',flush=True)
    camera=Camera(args.camera)
    stability=Stability(motion_limit=args.motion,sharpness_min=args.sharpness)
    executor=ThreadPoolExecutor(max_workers=1);future=None;speech=None
    armed=True;last_seq=-1;result_lines=[];captured_crop=None;started=time.monotonic();status='Hold one object inside the square'
    try:
        while True:
            if camera.error:raise RuntimeError(camera.error)
            seq,timestamp,frame=camera.latest()
            if frame is None:
                if time.monotonic()-started>15:raise RuntimeError('Camera returned no frames for 15 seconds')
                time.sleep(.01);continue
            if seq==last_seq:
                if time.monotonic()-timestamp>2:raise RuntimeError('Camera stream stalled')
                time.sleep(.005);continue
            last_seq=seq
            crop,(x,y,side)=crop_frame(frame)
            gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            sharpness=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            small=cv2.resize(gray,(64,64),interpolation=cv2.INTER_AREA)
            ready,elapsed,motion=stability.update(small,sharpness,timestamp)
            if future is not None and future.done():
                report=future.result();future=None
                text=f'{report["label"]}: score {report["confidence_score"]:.0%}'
                attributes=f'Crop: {report["crop_color"]}; brightness {report["crop_brightness"]}/255'
                result_lines=[text,attributes,'Manufacturer/model: unknown']
                status='RTL complete. SPACE then rotate/reposition for next view'
                print(json.dumps(report,indent=2),flush=True)
                if args.speak:
                    if speech is not None and speech.poll() is None:speech.terminate()
                    speech=subprocess.Popen(['/usr/bin/say',f'{report["label"]}. Crop color {report["crop_color"]}. Brightness {report["crop_brightness"]} out of 255.'])
            if armed and ready:
                armed=False;captured_crop=crop.copy()
                if args.mode=='collect':
                    path=folder/f'view_{time.time_ns()}.png'
                    if not cv2.imwrite(str(path),crop):raise RuntimeError('Could not save capture')
                    status=f'Saved {args.label} ({len(list(folder.glob("*.png")))} total). SPACE, then change view'
                    print(status,flush=True)
                else:
                    # Only pixels go into the subprocess. Predictions and attributes come back from RTL.
                    rgb=rgb_input(crop)
                    future=executor.submit(infer_rtl,rgb,args.model,args.build,executable,round(args.threshold*255))
                    status='Running SystemVerilog inference...';result_lines=[]
            output=frame.copy();cv2.rectangle(output,(x,y),(x+side,y+side),(0,220,0),2)
            if armed:
                status=f'Hold still: {min(elapsed,5):.1f}/5.0s | sharpness {sharpness:.0f}'
                if sharpness<args.sharpness:status='Improve focus/lighting; then hold still'
            if captured_crop is not None and not armed:
                thumb=cv2.resize(captured_crop,(112,112))
                output[-120:-8,-120:-8]=thumb
                cv2.putText(output,'Captured view',(output.shape[1]-120,output.shape[0]-125),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
            lines=[status]+result_lines
            for n,line in enumerate(lines):
                cv2.putText(output,line,(8,22+24*n),cv2.FONT_HERSHEY_SIMPLEX,.46,(0,0,0),3)
                cv2.putText(output,line,(8,22+24*n),cv2.FONT_HERSHEY_SIMPLEX,.46,(0,255,255),1)
            cv2.imshow(TITLE,output);key=cv2.waitKey(1)&255
            if key in (27,ord('q')) or cv2.getWindowProperty(TITLE,cv2.WND_PROP_VISIBLE)<1:break
            if key==32 and future is None:
                armed=True;stability.reset();result_lines=[];captured_crop=None
    finally:
        camera.close();cv2.destroyAllWindows();executor.shutdown(wait=True)
        if speech is not None and speech.poll() is None:speech.terminate()

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,FileNotFoundError,subprocess.TimeoutExpired) as exc:raise SystemExit(str(exc))
