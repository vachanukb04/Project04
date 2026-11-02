"""Offline training/export and verification reference. Not used to classify live frames."""
import hashlib
import json
from pathlib import Path
import numpy as np

INPUTS, HIDDEN, MAX_CLASSES = 768, 32, 16
FORMAT = 'p04-mlp-16x16-rgb-q3-q6-q5-v1'
FILES = {'w1': (24576, 8), 'b1': (32, 32), 'w2': (512, 8), 'b2': (16, 32)}
COLORS = ('dark', 'white', 'mixed/neutral', 'red', 'green', 'blue')

def features(images):
    """Exact RTL input: RGB high nibble minus 8, interpreted as signed Q3."""
    return (np.asarray(images, dtype=np.int64).reshape(-1, INPUTS) // 16 - 8)

def export_model(folder, labels, w1, b1, w2, b2, evidence):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    arrays = {'w1': np.rint(np.clip(w1, -127/64, 127/64)*64).astype(np.int64).reshape(-1),
              'b1': np.rint(b1*512).astype(np.int64),
              'w2': np.zeros((16, 32), dtype=np.int64), 'b2': np.zeros(16, dtype=np.int64)}
    arrays['w2'][:len(labels)] = np.rint(np.clip(w2, -127/64, 127/64)*64).astype(np.int64)
    arrays['w2'] = arrays['w2'].reshape(-1)
    arrays['b2'][:len(labels)] = np.rint(b2*2048).astype(np.int64)
    hashes = {}
    for name, (size, bits) in FILES.items():
        a = arrays[name].reshape(-1)
        if len(a) != size or (name.startswith('b') and np.max(np.abs(a)) > 2**24):
            raise ValueError('Invalid shape or unsafe accumulator bias')
        path = folder/(name+'.hex')
        path.write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n' for v in a))
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {'format': FORMAT, 'labels': labels, 'hashes': hashes,
                'training': evidence, 'confidence': 'approximate quantized softmax, not calibrated accuracy',
                'scope': 'one centered crop; custom trained classes only; no product/OCR metadata'}
    (folder/'model.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata

def load_model(folder):
    folder = Path(folder)
    metadata = json.loads((folder/'model.json').read_text())
    labels = metadata.get('labels', [])
    if metadata.get('format') != FORMAT or not 2 <= len(labels) <= MAX_CLASSES or len(set(labels)) != len(labels):
        raise ValueError('Unsupported model format or class list')
    arrays = {}
    for name, (size, bits) in FILES.items():
        path = folder/(name+'.hex')
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['hashes'][path.name]:
            raise ValueError(f'Model checksum mismatch: {path}')
        words = [int(v, 16) for v in path.read_text().split()]
        if len(words) != size or any(v < 0 or v >= 1 << bits for v in words):
            raise ValueError(f'Invalid model memory: {path}')
        a = np.array(words, dtype=np.int64)
        arrays[name] = np.where(a >= 1 << (bits-1), a-(1 << bits), a)
        if name.startswith('b') and np.max(np.abs(arrays[name])) > 2**24:
            raise ValueError('Bias exceeds supported arithmetic bounds')
    arrays['w1'] = arrays['w1'].reshape(32, 768)
    arrays['w2'] = arrays['w2'].reshape(16, 32)
    return metadata, arrays

def reference(image, arrays, classes, threshold=153):
    x = features(image)[0]
    hidden = np.clip((arrays['w1']@x+arrays['b1']) >> 4, 0, 127)
    logits = arrays['w2'][:classes]@hidden + arrays['b2'][:classes]
    best = int(np.argmax(logits))
    lut = np.rint(65535*np.exp(-np.arange(32)/4)).astype(np.int64)
    bins = (logits[best]-logits) >> 9
    exps = np.where(bins < 32, lut[np.minimum(bins, 31)], 0)
    confidence = 65535*255//int(exps.sum())
    r,g,b = (np.asarray(image, dtype=np.int64).reshape(256,3).sum(axis=0) >> 8).tolist()
    brightness = (77*r+150*g+29*b) >> 8
    color = 0 if brightness < 50 else 1 if brightness > 205 and max(r,g,b)-min(r,g,b)<20 else 3 if r>g+20 and r>b+20 else 4 if g>r+20 and g>b+20 else 5 if b>r+20 and b>g+20 else 2
    return [best if confidence >= threshold else 255, confidence, r,g,b,brightness,color]

def train(images, targets, labels, folder, epochs=400, seed=4):
    """Small quantization-aware MLP. Training is offline; recognition is in RTL."""
    rng = np.random.default_rng(seed)
    x = features(images).astype(np.float64)/8
    y = np.asarray(targets, dtype=np.int64)
    training, validation = [], []
    for c in range(len(labels)):
        indices = rng.permutation(np.flatnonzero(y == c))
        if len(indices) < 20: raise ValueError(f'{labels[c]} needs at least 20 captures; found {len(indices)}')
        cut = max(4, len(indices)//5)
        validation.extend(indices[:cut]); training.extend(indices[cut:])
    params = [rng.normal(0, np.sqrt(2/768), (32,768)), np.zeros(32),
              rng.normal(0, np.sqrt(2/32), (len(labels),32)), np.zeros(len(labels))]
    m = [np.zeros_like(p) for p in params]; v = [np.zeros_like(p) for p in params]; step = 0
    for epoch in range(epochs):
        order = rng.permutation(training)
        for begin in range(0, len(order), 64):
            batch = order[begin:begin+64]; xb=x[batch]; yb=y[batch]
            w1,b1,w2,b2 = params
            q1=np.rint(w1*64)/64; q2=np.rint(w2*64)/64
            z=xb@q1.T+np.rint(b1*512)/512
            h=np.clip(np.floor(z*32),0,127)/32
            scores=h@q2.T+np.rint(b2*2048)/2048
            scores-=scores.max(axis=1,keepdims=True)
            grad=np.exp(scores);grad/=grad.sum(axis=1,keepdims=True)
            grad[np.arange(len(batch)),yb]-=1;grad/=len(batch)
            dh=(grad@q2)*((z>0)&(z<127/32))
            grads=[dh.T@xb,dh.sum(axis=0),grad.T@h,grad.sum(axis=0)]
            step+=1
            for j,(p,g) in enumerate(zip(params,grads)):
                m[j]=.9*m[j]+.1*g;v[j]=.999*v[j]+.001*g*g
                p-=.003*(m[j]/(1-.9**step))/(np.sqrt(v[j]/(1-.999**step))+1e-8)
            params[0][:]=np.clip(params[0],-127/64,127/64)
            params[2][:]=np.clip(params[2],-127/64,127/64)
        if epoch%100==0: print(f'Training epoch {epoch}/{epochs}',flush=True)
    evidence={'seed':seed,'epochs':epochs,'captures':len(y),'training_samples':len(training),
              'validation_samples':len(validation), 'warning':'Random capture split; not independent real-world accuracy. Test fresh sessions/backgrounds.'}
    export_model(folder,labels,*params,evidence)
    metadata,arrays=load_model(folder)
    predicted=[reference(images[n],arrays,len(labels),0)[0] for n in validation]
    accuracy=float(np.mean(np.asarray(predicted)==y[validation]))
    metadata['training']['integer_validation_accuracy']=accuracy
    (Path(folder)/'model.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Integer held-out capture accuracy: {accuracy:.1%}. Test fresh views/backgrounds.',flush=True)
    return metadata
