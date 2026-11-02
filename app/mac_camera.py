#!/usr/bin/env python3
"""Local webcam object detection. The detector executes in software, not RTL."""
import argparse,json,platform,subprocess,threading,time
from pathlib import Path
import cv2
import numpy as np
import torch
from torchvision.models.detection import ssdlite320_mobilenet_v3_large,SSDLite320_MobileNet_V3_Large_Weights

ROOT=Path(__file__).resolve().parents[1]
TITLE='Project04 | SOFTWARE detector | Q: quit, S: snapshot'

class LatestFrame:
    """Drain the capture stream so inference consumes the latest available frame."""
    def __init__(self,capture):
        self.capture=capture;self.lock=threading.Lock();self.frame=None;self.sequence=0
        self.stop=threading.Event();self.failure=None
        self.thread=threading.Thread(target=self.run,daemon=True)
    def run(self):
        misses=0
        try:
            while not self.stop.is_set():
                ok,frame=self.capture.read()
                if not ok:
                    misses+=1
                    if misses>=20:self.failure='Camera stopped returning frames';return
                    time.sleep(.05);continue
                misses=0
                with self.lock:self.frame=frame;self.sequence+=1
        except Exception as exc:self.failure=str(exc)
    def latest(self):
        with self.lock:return self.sequence,None if self.frame is None else self.frame.copy()
    def close(self):
        self.stop.set();self.thread.join(timeout=2);self.capture.release()

def load_detector():
    torch.set_num_threads(2)
    torch.hub.set_dir(str(ROOT/'build/image_nn/torch'))
    weights=SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    return ssdlite320_mobilenet_v3_large(weights=weights).eval(),weights.meta['categories']

def detect(model,labels,frame,threshold):
    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    tensor=torch.from_numpy(np.ascontiguousarray(rgb)).permute(2,0,1).float()/255
    with torch.inference_mode():pred=model([tensor])[0]
    return [{'label':labels[int(c)],'score':float(s),'box_xyxy':[float(v) for v in b]}
            for b,c,s in zip(pred['boxes'],pred['labels'],pred['scores']) if float(s)>=threshold]

def annotate(frame,detections,elapsed):
    output=frame.copy();height,width=output.shape[:2]
    for d in detections:
        x1,y1,x2,y2=d['box_xyxy']
        x1=max(0,min(width-1,round(x1)));x2=max(0,min(width-1,round(x2)))
        y1=max(0,min(height-1,round(y1)));y2=max(0,min(height-1,round(y2)))
        cv2.rectangle(output,(x1,y1),(x2,y2),(0,220,0),2)
        cv2.putText(output,f'{d["label"]} {d["score"]:.2f}',(x1,max(0,min(height-5,max(48,y1-7)))),
                    cv2.FONT_HERSHEY_SIMPLEX,.65,(0,220,0),2)
    cv2.putText(output,f'SOFTWARE detector | {elapsed*1000:.0f} ms | {len(detections)} objects',
                (10,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(30,220,255),2)
    return output

def save_snapshot(folder,image,detections):
    folder.mkdir(parents=True,exist_ok=True)
    stem=f'frame_{time.time_ns()}'
    png=folder/(stem+'.png');report=folder/(stem+'.json')
    if not cv2.imwrite(str(png),image):raise RuntimeError(f'Could not save {png}')
    report.write_text(json.dumps({'execution':'software CPU detector; no RTL inference',
        'detections':detections},indent=2)+'\n')
    print(f'Saved {png} and {report}',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--camera',type=int,default=0)
    ap.add_argument('--threshold',type=float,default=.5)
    ap.add_argument('--speak',action='store_true',help='Speak selected labels using macOS say')
    ap.add_argument('--image',type=Path,help='Test a saved image without camera or GUI')
    ap.add_argument('--output',type=Path,default=ROOT/'build/camera_snapshots')
    args=ap.parse_args()
    if not 0<=args.threshold<=1:ap.error('threshold must be between 0 and 1')
    print('Loading SOFTWARE detector; first run downloads official pretrained weights.',flush=True)
    model,labels=load_detector()
    if args.image:
        frame=cv2.imread(str(args.image))
        if frame is None:raise SystemExit(f'Cannot read image: {args.image}')
        t=time.perf_counter();detections=detect(model,labels,frame,args.threshold)
        output=annotate(frame,detections,time.perf_counter()-t)
        save_snapshot(args.output,output,detections)
        print(json.dumps(detections,indent=2));return
    if args.speak and platform.system()!='Darwin':ap.error('--speak requires macOS')
    backend=cv2.CAP_AVFOUNDATION if platform.system()=='Darwin' else cv2.CAP_ANY
    cap=cv2.VideoCapture(args.camera,backend)
    if not cap.isOpened():
        cap.release()
        raise SystemExit('Cannot open camera. On Mac, allow your Terminal/IDE under System Settings > Privacy & Security > Camera, then restart that app. Try --camera 1 for an external camera.')
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    stream=LatestFrame(cap);stream.thread.start()
    speech=None;last_spoken=0.;last_sequence=-1;started=time.monotonic()
    print('Camera is open. Q/Escape quits; S saves a local snapshot. No frames are uploaded.',flush=True)
    try:
        while True:
            if stream.failure:raise RuntimeError(stream.failure)
            sequence,frame=stream.latest()
            if frame is None:
                if time.monotonic()-started>15:raise RuntimeError('No camera frame received within 15 seconds')
                time.sleep(.02);continue
            if sequence==last_sequence:time.sleep(.005);continue
            last_sequence=sequence
            t=time.perf_counter();detections=detect(model,labels,frame,args.threshold)
            output=annotate(frame,detections,time.perf_counter()-t)
            cv2.imshow(TITLE,output)
            key=cv2.waitKey(1)&255
            if key in (27,ord('q')):break
            if key==ord('s'):save_snapshot(args.output,output,detections)
            if cv2.getWindowProperty(TITLE,cv2.WND_PROP_VISIBLE)<1:break
            if args.speak and detections and time.monotonic()-last_spoken>=4 and (speech is None or speech.poll() is not None):
                speech=subprocess.Popen(['/usr/bin/say',detections[0]['label']]);last_spoken=time.monotonic()
    finally:
        stream.close();cv2.destroyAllWindows()
        if speech is not None and speech.poll() is None:speech.terminate()

if __name__=='__main__':main()
