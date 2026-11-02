"""Pretrained SOFTWARE naming plus RTL appearance memory. Boundary is intentional."""
import math
import os
from pathlib import Path
import ssl
import urllib.error
import cv2
from .bridge import ROOT
from .memory_bridge import infer_memory

ALIASES={'cell phone':'phone','tv':'television','dining table':'table'}
MODEL_ID='torchvision/ssdlite320_mobilenet_v3_large/COCO_V1'

def setup_certificates():
    # Keep verification enabled. Respect any explicit enterprise/user CA setting.
    if not os.environ.get('SSL_CERT_FILE'):
        try:
            import certifi
            os.environ['SSL_CERT_FILE']=certifi.where()
        except ImportError:pass

def object_label(label):return ALIASES.get(label,label)

class BasicDetector:
    def __init__(self,threshold=.45):
        if not 0<=threshold<=1:raise ValueError('Detection threshold must be 0..1')
        setup_certificates()
        try:
            import torch
            from torchvision.models.detection import ssdlite320_mobilenet_v3_large,SSDLite320_MobileNet_V3_Large_Weights
        except (ImportError,RuntimeError) as exc:
            raise RuntimeError('Pretrained detector unavailable. Install app/requirements-hybrid-camera.txt in this environment. Use --recognizer rtl-only for memory-only mode. '+str(exc)) from exc
        self.torch=torch;self.threshold=threshold
        torch.set_num_threads(2);torch.hub.set_dir(str(ROOT/'build/image_nn/torch'))
        weights=SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
        try:self.model=ssdlite320_mobilenet_v3_large(weights=weights).eval()
        except (urllib.error.URLError,ssl.SSLError,OSError,RuntimeError) as exc:
            raise RuntimeError('Cannot load official pretrained weights. Check connectivity and SSL certificates; verification has not been disabled. Original error: '+str(exc)) from exc
        self.labels=weights.meta['categories']
        self.categories=[object_label(c) for c in self.labels if c not in ('N/A','__background__')]
    def detect(self,frame):
        import numpy as np
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        tensor=self.torch.from_numpy(np.ascontiguousarray(rgb)).permute(2,0,1).float()/255
        with self.torch.inference_mode():prediction=self.model([tensor])[0]
        return [{'label':object_label(self.labels[int(c)]),'score':float(s),'box_xyxy':[float(v) for v in b]}
            for b,c,s in zip(prediction['boxes'],prediction['labels'],prediction['scores']) if float(s)>=self.threshold]

def choose_object(detections,width,height):
    candidates=[]
    for d in detections:
        x1,y1,x2,y2=d['box_xyxy']
        if not all(math.isfinite(v) for v in (x1,y1,x2,y2,d['score'])):continue
        x1=max(0,min(width-1,int(math.floor(x1))));x2=max(0,min(width,int(math.ceil(x2))))
        y1=max(0,min(height-1,int(math.floor(y1))));y2=max(0,min(height,int(math.ceil(y2))))
        if x2<=x1 or y2<=y1:continue
        center_distance=math.hypot((x1+x2)/(2*width)-.5,(y1+y2)/(2*height)-.5)
        rank=d['score']*max(.1,1-1.5*center_distance)
        candidates.append((rank,{**d,'box_xyxy':[x1,y1,x2,y2]}))
    objects=[d for d in candidates if d[1]['label']!='person']
    pool=objects or candidates
    return max(pool,key=lambda x:x[0])[1] if pool else None

def compatible_examples(examples,context):
    # Keep old memory files, but do not compare old whole-guide descriptors to
    # detected-object descriptors or override a laptop using a known phone view.
    eligible=[]
    for ex in examples:
        saved=ex.get('context')
        if not saved:
            if context['descriptor_scope']=='center-crop-v1':eligible.append(ex)
            continue
        if saved.get('descriptor_scope')!=context['descriptor_scope']:continue
        a=saved.get('base_label');b=context.get('base_label')
        if a and b and a!=b:continue
        eligible.append(ex)
    return eligible

def infer_hybrid(frame,examples,build,executable,detector,memory_threshold=.94):
    if not 0<=memory_threshold<=1:raise ValueError('Memory threshold must be 0..1')
    detections=detector.detect(frame)
    h,w=frame.shape[:2];selected=choose_object(detections,w,h)
    if selected:
        x1,y1,x2,y2=selected['box_xyxy'];region=frame[y1:y2,x1:x2]
        context={'base_label':selected['label'],'descriptor_scope':'detected-object-v1'}
    else:
        side=int(min(h,w)*.65);x1=(w-side)//2;y1=(h-side)//2;x2=x1+side;y2=y1+side
        region=frame[y1:y2,x1:x2]
        context={'base_label':None,'descriptor_scope':'center-crop-v1'}
    candidates=compatible_examples(examples,context)
    rgb=cv2.cvtColor(cv2.resize(region,(16,16),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
    report=infer_memory(rgb,candidates,build,executable)
    candidate=report['label']
    use_memory=report['best_slot']!=255 and report['similarity_score']>=memory_threshold
    label=candidate if use_memory else selected['label'] if selected else 'unknown'
    report.update({'execution':'HYBRID: pretrained SOFTWARE detector; RTL descriptor, memory distance and crop attributes',
        'recognition':'pretrained COCO naming plus confirmed-example appearance adaptation',
        'label':label,'has_guess':label!='unknown',
        'prediction_source':'confirmed_memory' if use_memory else 'pretrained_software' if selected else 'unknown',
        'base_detector':MODEL_ID,'base_label':selected['label'] if selected else None,
        'detector_score':selected['score'] if selected else None,'detections':detections,
        'box_xyxy':[x1,y1,x2,y2] if selected else None,'query_region_xyxy':[x1,y1,x2,y2],
        'learning_context':context,'memory_candidate':candidate,'memory_used':use_memory,
        'memory_threshold':memory_threshold,'memory_candidates':len(candidates)})
    # The combined report supersedes the bridge's raw nearest-slot report.
    import json
    (Path(build)/'hybrid_result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
