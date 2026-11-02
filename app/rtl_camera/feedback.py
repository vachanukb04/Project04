"""Confirmed episodic memory and feedback parsing. No image matching in Python."""
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata

FORMAT='p04-confirmed-rgb-nibbles-v1'
CAPACITY=64

def label_text(value):
    value=unicodedata.normalize('NFKC',value).strip()
    value=re.sub(r'\s+',' ',value)
    if not value or len(value)>64 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('Label must contain 1..64 visible characters')
    if value.casefold() in ('unknown','yes','no','cancel'):
        raise ValueError('Use an object name rather than a feedback command')
    return value

def descriptor_values(value):
    if not isinstance(value,list) or len(value)!=768 or any(type(v) is not int or not 0<=v<=15 for v in value):
        raise ValueError('Expected 768 RTL descriptor nibbles')
    return value

class FeedbackMemory:
    def __init__(self,path):
        self.path=Path(path).resolve()
        if self.path.exists():
            self.data=json.loads(self.path.read_text())
        else:self.data={'format':FORMAT,'revision':0,'examples':[],'events':[]}
        if self.data.get('format')!=FORMAT or type(self.data.get('revision')) is not int:
            raise ValueError('Unsupported feedback memory')
        if not isinstance(self.data.get('examples'),list) or len(self.data['examples'])>CAPACITY:
            raise ValueError('Invalid feedback memory capacity')
        if not isinstance(self.data.get('events'),list):raise ValueError('Invalid feedback history')
        for ex in self.data['examples']:
            label_text(ex['label']);descriptor_values(ex['descriptor'])
            if type(ex.get('confirmations')) is not int or ex['confirmations']<1:raise ValueError('Invalid confirmation count')
    @property
    def examples(self):return copy.deepcopy(self.data['examples'])
    def learn(self,descriptor,label,context=None):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another camera process is updating feedback memory. Retry later.')
            return self._learn_locked(descriptor,label,context)
    def _learn_locked(self,descriptor,label,context=None):
        descriptor=descriptor_values(descriptor);label=label_text(label)
        if context is not None:
            if context.get('descriptor_scope') not in ('detected-object-v1','center-crop-v1'):
                raise ValueError('Unsupported descriptor context')
            if context.get('base_label') is not None:label_text(context['base_label'])
            context=copy.deepcopy(context)
        # Refuse overwriting another process's updates. Single writer only.
        if self.path.exists():
            if json.loads(self.path.read_text()).get('revision')!=self.data['revision']:
                raise RuntimeError('Feedback memory changed in another process. Close extra camera sessions and restart.')
        elif self.data['revision']!=0:raise RuntimeError('Feedback file was removed externally. Restart before teaching.')
        update=copy.deepcopy(self.data);examples=update['examples'];now=time.time()
        canonical=next((e['label'] for e in examples if e['label'].casefold()==label.casefold()),label)
        label=canonical
        prior=None;evicted=None
        exact=next((e for e in examples if e['descriptor']==descriptor and (e.get('context')==context or (not e.get('context') and context and context['descriptor_scope']=='center-crop-v1'))),None)
        if exact is not None:
            prior=exact['label'];exact['label']=label;exact['confirmations']+=1;exact['updated_at']=now
            if context is not None:exact['context']=context
        else:
            if len(examples)==CAPACITY:
                oldest=min(range(len(examples)),key=lambda n:examples[n]['updated_at'])
                evicted=examples.pop(oldest)['label']
            examples.append({'label':label,'descriptor':descriptor.copy(),'confirmations':1,'updated_at':now,**({'context':context} if context is not None else {})})
        update['revision']+=1
        update['events'].append({'time':now,'label':label,'previous_label':prior,'evicted_label':evicted})
        update['events']=update['events'][-256:]
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # Atomic replacement keeps a failed write from destroying prior memory.
        fd,name=tempfile.mkstemp(prefix='.feedback-',suffix='.json',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(update,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
        self.data=update
        return {'label':label,'examples':len(examples),'revision':update['revision'],'evicted_label':evicted}

def parse_feedback(transcript):
    text=transcript.strip().strip('.,!? ')
    if text.casefold() in ('yes','yes correct','correct','that is correct','right'):
        return 'confirm',None
    if text.casefold() in ('cancel','skip','never mind'):return 'cancel',None
    if text.casefold() in ('no','incorrect','wrong','not correct'):return 'reject',None
    # Parse only explicit correction forms; never interpret arbitrary conversation as a label.
    match=re.fullmatch(r'(?:no[, ]+)?(?:it is|it\'s|this is|these are|that is|label(?: it)?|call it)\s+(.+)',text,re.IGNORECASE)
    if match:
        label=re.sub(r'^(?:a|an|the)\s+','',match.group(1),flags=re.IGNORECASE)
        return 'label',label_text(label)
    return 'unrecognized',None

class FeedbackSession:
    """Bind confirmations to the captured result, not the moving live camera."""
    def __init__(self,memory,report):
        self.memory=memory;self.descriptor=descriptor_values(report['descriptor']).copy()
        self.guess=report['label'] if report.get('has_guess',report['best_slot']!=255) else None
        self.context=copy.deepcopy(report.get('learning_context'))
        self.pending=None;self.committed=False;self.rejected=False
    def propose(self,label):
        self.pending=label_text(label);self.rejected=False
        return f'Heard "{self.pending}". Y/voice yes to save; N to discard.'
    def confirm(self):
        if self.committed:return 'Already saved this view. SPACE for another view.'
        label=self.pending or (None if self.rejected else self.guess)
        if label is None:return 'No name to confirm. C to type or V: say "this is ...".'
        saved=self.memory.learn(self.descriptor,label,context=self.context);self.committed=True
        self.guess=saved['label'];self.pending=None;self.rejected=False
        return f'Learned {saved["label"]}; {saved["examples"]} confirmed views. SPACE for next.'
    def reject(self):
        if self.committed:return 'Already saved. SPACE to capture a corrected view.'
        self.pending=None;self.rejected=True
        return 'Not saved. C to type or V: say "no, this is ...".'
    def voice(self,text):
        if self.committed:return 'Already saved this view. SPACE for next.'
        kind,label=parse_feedback(text)
        if kind=='confirm':return self.confirm()
        if kind=='label':return self.propose(label)
        if kind in ('reject','cancel'):return self.reject()
        return 'No feedback command recognized. Say yes, no, or "this is ...".'
