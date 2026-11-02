#!/usr/bin/env python3
"""Run a real detector in SOFTWARE and export real first-convolution RTL vectors.

The exported INT8 first-layer exercise is not an end-to-end quantized detector.
Downloads official pretrained weights and a public PyTorch example image.
"""
import argparse, hashlib, json, urllib.request
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import torchvision
import PIL
from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
from torchvision.transforms.functional import pil_to_tensor

ROOT=Path(__file__).resolve().parents[1]
SAMPLE='https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg'
WEIGHTS='https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image',type=Path,help='Local RGB image; omit to download public dog example')
    ap.add_argument('--output',type=Path,default=ROOT/'examples/image_nn')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'build/image_nn';cache.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(2);torch.hub.set_dir(str(cache/'torch'))
    image_path=args.image
    if image_path is None:
        image_path=cache/'dog.jpg'
        if not image_path.exists():urllib.request.urlretrieve(SAMPLE,image_path)
    image=Image.open(image_path).convert('RGB')
    tensor=pil_to_tensor(image).to(torch.float32)/255.0
    weights=SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model=ssdlite320_mobilenet_v3_large(weights=weights).eval()
    with torch.inference_mode():
        pred=model([tensor])[0]
        transformed,_=model.transform([tensor],None)
    detections=[{'label':weights.meta['categories'][int(label)],'score':float(score),
                 'box_xyxy':[float(x) for x in box]}
                for box,label,score in zip(pred['boxes'],pred['labels'],pred['scores']) if score>=0.5]
    name,conv=next((n,m) for n,m in model.named_modules() if isinstance(m,torch.nn.Conv2d))
    assert conv.kernel_size==(3,3) and conv.in_channels==3 and conv.groups==1
    assert conv.stride==(2,2) and conv.padding==(1,1)
    assert conv.bias is None, 'This exporter currently handles a bias-free first convolution'
    x=transformed.tensors[0].numpy()
    xq=np.clip(np.rint(x*128),-128,127).astype(np.int8)
    w=conv.weight.detach().numpy()
    scales=np.max(np.abs(w),axis=(1,2,3))/127
    wq=np.clip(np.rint(w/scales[:,None,None,None]),-127,127).astype(np.int8)
    # Test four spatial positions and two learned output channels.
    # Include the top-left padded window; flatten in C,KY,KX order.
    padded=np.pad(xq,((0,0),(1,1),(1,1)),constant_values=0)
    with torch.inference_mode():
        independent=torch.nn.functional.conv2d(torch.from_numpy(xq.copy()).double()[None],
            torch.from_numpy(wq.copy()).double(),stride=2,padding=1)[0].numpy()
    def pack(values):
        v=list(values)+[0]*((-len(values))%4)
        return [sum((int(v[k+j])&255)<<(8*j) for j in range(4)) for k in range(0,len(v),4)]
    jobs=[]
    for oy,ox in [(0,0),(16,16),(64,80),(120,100)]:
        patch=padded[:,oy*2:oy*2+3,ox*2:ox*2+3].reshape(-1)
        for channel in [0,1]:
            kernel=wq[channel].reshape(-1)
            total=int(np.dot(patch.astype(np.int64),kernel.astype(np.int64)))
            assert total==int(independent[channel,oy,ox])
            assert -(1<<31)<=total<(1<<31)
            jobs.append({'output_y':oy,'output_x':ox,'output_channel':channel,
                'a_words':pack(patch),'b_words':pack(kernel),'bias':0,'expected':total})
    weight_path=cache/'torch/checkpoints'/Path(WEIGHTS).name
    manifest={'scope':'software detections plus INT8 first-convolution accumulation vectors; not full RTL inference',
        'model':'SSDLite320 MobileNet V3 Large COCO_V1','weights_url':WEIGHTS,
        'weights_sha256':hashlib.sha256(weight_path.read_bytes()).hexdigest(),
        'image_source':SAMPLE if args.image is None else 'user-provided local image',
        'image_sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),
        'image_size':list(image.size),'torch':torch.__version__,
        'versions':{'torch':torch.__version__,'torchvision':torchvision.__version__,'numpy':np.__version__,'pillow':PIL.__version__},
        'input_transform':'model.transform: actual SSD normalization and resize; exported tensor quantized with round-to-even and scale=1/128',
        'conv_name':name,'kernel_shape':list(wq.shape),'stride':2,'padding':1,
        'weight_quantization':'per-output-channel symmetric INT8 round-to-even, maxabs/127',
        'exported_weight_scales':scales[:2].tolist(),
        'omitted_operations':['batch normalization','nonlinearity','remaining backbone and head','box decoding and NMS in RTL'],
        'labels':[s for s in weights.meta['categories'] if s not in ('N/A','__background__')],
        'software_detections':detections,'jobs':jobs}
    (args.output/'vectors.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'software_detections':detections,'rtl_vector_jobs':len(jobs),
                     'first_layer_reference_check':'8 patch accumulations equal independent torch conv2d'},indent=2))

if __name__=='__main__':main()
