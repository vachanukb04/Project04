#!/usr/bin/env python3
"""Pretrained software object naming plus persistent RTL feedback memory."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import subprocess
import threading
import time
import cv2
from mac_rtl_camera import Camera,crop_frame,rgb_input
from rtl_camera.bridge import ROOT,Stability
from rtl_camera.feedback import FeedbackMemory,FeedbackSession
from rtl_camera.memory_bridge import compile_memory,infer_memory
from rtl_camera.voice import build_voice,listen_once
from rtl_camera.pretrained import BasicDetector,infer_hybrid

TITLE='Project04 feedback | Y yes | N no | C type | V voice | SPACE next | Q quit'

def public_report(report):return {k:v for k,v in report.items() if k!='descriptor'}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--memory',type=Path,default=ROOT/'build/rtl_camera/feedback/memory.json')
    ap.add_argument('--build',type=Path,default=ROOT/'build/rtl_camera/feedback/run')
    ap.add_argument('--camera',type=int,default=0)
    ap.add_argument('--recognizer',choices=['hybrid','rtl-only'],default='hybrid',help='hybrid: pretrained software naming plus RTL memory; rtl-only: previous appearance memory')
    ap.add_argument('--threshold',type=float,default=.45,help='Pretrained detector minimum score')
    ap.add_argument('--memory-threshold',type=float,default=.94,help='Minimum RTL appearance similarity for a confirmed memory to override pretrained naming')
    ap.add_argument('--speak',action='store_true')
    ap.add_argument('--voice',action='store_true',help='Listen once after each guess, and on V; requires Apple command-line tools')
    ap.add_argument('--allow-network-voice',action='store_true',help='Explicitly allow Apple Speech network processing if used')
    ap.add_argument('--sharpness',type=float,default=30.)
    ap.add_argument('--motion',type=float,default=2.5)
    ap.add_argument('--image',type=Path,help='Offline image through same RTL; no camera')
    ap.add_argument('--teach',help='Explicitly confirm this label for --image')
    ap.add_argument('--inspect-memory',action='store_true')
    args=ap.parse_args(argv)
    if args.motion<=0 or args.sharpness<0:ap.error('Invalid motion/sharpness')
    if not 0<=args.threshold<=1 or not 0<=args.memory_threshold<=1:ap.error('Thresholds must be 0..1')
    if args.teach and not args.image:ap.error('--teach requires --image; use C or voice to teach live frames')
    if args.allow_network_voice and not args.voice:ap.error('--allow-network-voice requires --voice')
    memory=FeedbackMemory(args.memory)
    if args.inspect_memory:
        print(json.dumps({'revision':memory.data['revision'],'views':len(memory.examples),
            'labels':sorted(set(e['label'] for e in memory.examples))},indent=2));return
    executable=compile_memory(args.build)
    detector=None
    if args.recognizer=='hybrid':
        print('HYBRID mode: basic object names from pretrained SOFTWARE; matching and crop attributes from RTL.',flush=True)
        print('Loading official pretrained detector (cached after first download)...',flush=True)
        detector=BasicDetector(args.threshold)
    def recognize(frame,examples):
        if detector is not None:return infer_hybrid(frame,examples,args.build,executable,detector,args.memory_threshold)
        return infer_memory(rgb_input(crop_frame(frame)[0]),examples,args.build,executable)
    if args.image:
        frame=cv2.imread(str(args.image))
        if frame is None:ap.error('Cannot read image')
        report=recognize(frame,memory.examples)
        print(json.dumps(public_report(report),indent=2))
        if args.teach:print(json.dumps(memory.learn(report['descriptor'],args.teach,context=report.get('learning_context')),indent=2))
        return
    if (args.voice or args.speak) and platform.system()!='Darwin':ap.error('Speech and microphone require macOS; omit these flags for typed feedback')
    voice_binary=None
    if args.voice:
        print('Building native Mac speech helper. On-device recognition is required unless explicitly allowed otherwise.',flush=True)
        try:voice_binary=build_voice(args.build)
        except (RuntimeError,subprocess.TimeoutExpired) as exc:print(f'Voice unavailable: {exc}\nUse C/Y/N feedback instead.',flush=True)
    print(f'Loaded {len(memory.examples)} confirmed views. No dataset or model training required.',flush=True)
    print('Pretrained names need no user training. Corrections are stored only after confirmation.' if detector else 'RTL-only mode: names come from your feedback; no pretrained naming.',flush=True)
    print('Similarity and detector scores are different measures; neither guarantees correctness.',flush=True)
    camera=Camera(args.camera);stability=Stability(motion_limit=args.motion,sharpness_min=args.sharpness)
    pool=ThreadPoolExecutor(max_workers=2);inference=None;voice=None;speech=None;voice_cancel=threading.Event()
    armed=True;auto_listen=False;typing=False;typed='';session=None;report=None;captured=None
    last_seq=-1;started=time.monotonic();status='Hold one object inside the square';result_lines=[]
    def speak(text):
        nonlocal speech
        if args.speak:
            if speech is not None and speech.poll() is None:
                speech.terminate();speech.wait(timeout=2)
            speech=subprocess.Popen(['/usr/bin/say',text])
    def save_feedback():
        nonlocal status,auto_listen
        try:status=session.confirm()
        except (RuntimeError,ValueError,OSError) as exc:status=str(exc)
        auto_listen=False;print(status,flush=True)
        if session.committed:speak(status)
    try:
        while True:
            if camera.error:raise RuntimeError(camera.error)
            seq,timestamp,frame=camera.latest()
            if frame is None:
                if time.monotonic()-started>15:raise RuntimeError('No camera frames for 15 seconds')
                time.sleep(.01);continue
            if seq==last_seq:
                if time.monotonic()-timestamp>2:raise RuntimeError('Camera stalled')
                time.sleep(.005);continue
            last_seq=seq
            crop,(x,y,side)=crop_frame(frame)
            gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            ready,elapsed,_=stability.update(cv2.resize(gray,(64,64)),float(cv2.Laplacian(gray,cv2.CV_64F).var()),timestamp)
            if inference is not None and inference.done():
                report=inference.result();inference=None
                session=FeedbackSession(memory,report)
                status='Y confirm | N reject | C type correction | V speak correction'
                source=report.get('prediction_source','rtl_memory')
                detail=(f'Pretrained score {report["detector_score"]:.0%}' if report.get('detector_score') is not None else 'No pretrained detection')
                result_lines=[f'Tentative: {report["label"]} | {source}',
                    f'{detail} | memory similarity {report["similarity_score"]:.0%}',
                    f'Crop: {report["crop_color"]}; brightness {report["crop_brightness"]}/255']
                print(json.dumps(public_report(report),indent=2),flush=True)
                prompt=(f'My guess is {report["label"]}. Is that correct?' if session.guess else 'I have not learned this object. Say this is, followed by its name.')
                speak(prompt);auto_listen=voice_binary is not None
            if voice is not None and voice.done():
                try:
                    transcript=voice.result();print('Heard:',transcript,flush=True)
                    status=session.voice(transcript)
                    if session.pending and not session.committed:
                        speak(f'I heard {session.pending}. Say yes to save it, or no to discard it.')
                        auto_listen=True
                    elif session.committed:speak(status)
                    elif session.rejected:
                        speak('What should I call this object? Say this is, followed by its name.')
                        auto_listen=True
                except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as exc:status=f'Voice: {exc}. C to type or V to retry.'
                voice=None;print(status,flush=True)
            if auto_listen and voice is None and not typing and (speech is None or speech.poll() is not None):
                auto_listen=False;status='Listening up to 8 seconds: yes, no, or this is ...'
                voice=pool.submit(listen_once,voice_binary,args.allow_network_voice,voice_cancel)
            if armed and ready:
                armed=False;captured=frame.copy();result_lines=[]
                inference=pool.submit(recognize,captured.copy(),memory.examples)
                status='HYBRID detecting object + RTL memory...' if detector else 'RTL searching confirmed memory...'
            if session is not None and session.committed and result_lines:
                result_lines[0]=f'Confirmed: {session.guess} | saved for future views'
            # Results are drawn on the captured frame; a live frame may already show another object.
            output=captured.copy() if report is not None and captured is not None else frame.copy()
            cv2.rectangle(output,(x,y),(x+side,y+side),(100,160,100),1)
            if report is not None and report.get('box_xyxy'):
                bx1,by1,bx2,by2=report['box_xyxy'];cv2.rectangle(output,(bx1,by1),(bx2,by2),(0,255,0),2)
            if armed:status=f'Hold still/in focus: {min(elapsed,5):.1f}/5.0 seconds'
            if captured is not None and min(output.shape[:2])>=128:
                region=crop_frame(captured)[0]
                if report is not None and report.get('query_region_xyxy'):
                    rx1,ry1,rx2,ry2=report['query_region_xyxy'];region=captured[ry1:ry2,rx1:rx2]
                output[-120:-8,-120:-8]=cv2.resize(region,(112,112))
                cv2.putText(output,'Captured view',(output.shape[1]-120,output.shape[0]-125),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
            lines=([f'Type name: {typed}_ | ENTER review | ESC cancel'] if typing else [status])+result_lines
            if session is not None and session.pending and not session.committed:lines.append(f'Confirm label: {session.pending} | Y save | N discard')
            for n,line in enumerate(lines):
                for color,width in (((0,0,0),3),((0,255,255),1)):
                    cv2.putText(output,line[:100],(8,22+24*n),cv2.FONT_HERSHEY_SIMPLEX,.44,color,width)
            cv2.imshow(TITLE,output);key=cv2.waitKey(1)&255
            if typing:
                if key==27:typing=False;typed=''
                elif key in (10,13):
                    try:status=session.propose(typed);typing=False
                    except ValueError as exc:status=str(exc);print(status,flush=True)
                elif key in (8,127):typed=typed[:-1]
                elif 32<=key<=126:typed=(typed+chr(key))[:64]
                continue
            if 65<=key<=90:key+=32
            if key in (27,ord('q')) or cv2.getWindowProperty(TITLE,cv2.WND_PROP_VISIBLE)<1:break
            if voice is not None:continue # Keep feedback bound to this capture until transcription finishes.
            if key==32 and inference is None:
                armed=True;stability.reset();session=None;report=None;captured=None;result_lines=[];auto_listen=False
                if speech is not None and speech.poll() is None:speech.terminate();speech.wait(timeout=2)
            elif session is not None and not session.committed:
                if key==ord('y'):save_feedback()
                elif key==ord('n'):status=session.reject();auto_listen=False
                elif key==ord('c'):typing=True;typed='';auto_listen=False
                elif key==ord('v'):
                    if voice_binary is None:status='Voice not enabled/available. Restart with --voice, or C to type.'
                    else:
                        if speech is not None and speech.poll() is None:speech.terminate();speech.wait(timeout=2)
                        auto_listen=True
    finally:
        voice_cancel.set();camera.close();cv2.destroyAllWindows();pool.shutdown(wait=True)
        if speech is not None and speech.poll() is None:speech.terminate()

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as exc:raise SystemExit(str(exc))
