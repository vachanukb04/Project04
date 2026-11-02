"""Persistent correction behavior plus real RTL nearest-neighbor regression."""
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from rtl_camera.feedback import FeedbackMemory,FeedbackSession,parse_feedback
from rtl_camera.memory_bridge import compile_memory,infer_memory
from rtl_camera.voice import listen_once

class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'memory.json'
        self.memory=FeedbackMemory(self.path)
    def tearDown(self):self.tmp.cleanup()
    def report(self,label='phone',slot=0):return {'label':label,'best_slot':slot,'descriptor':[2]*768}
    def test_voice_correction_needs_confirmation(self):
        session=FeedbackSession(self.memory,self.report())
        session.voice('No, these are AirPods.')
        self.assertEqual(len(self.memory.examples),0)
        self.assertEqual(session.pending,'AirPods')
        session.voice('yes')
        self.assertEqual(FeedbackMemory(self.path).examples[0]['label'],'AirPods')
        self.assertEqual(session.guess,'AirPods')
        self.assertIsNone(session.pending)
        session.voice('yes')
        self.assertEqual(self.memory.data['revision'],1)
    def test_rejection_does_not_learn_or_reconfirm_bad_guess(self):
        session=FeedbackSession(self.memory,self.report())
        session.voice('no');session.voice('yes')
        self.assertFalse(self.path.exists())
        session.voice('some unrelated conversation')
        self.assertEqual(len(self.memory.examples),0)
        session.voice('this is a tablet');session.voice('cancel');session.voice('yes')
        self.assertEqual(len(self.memory.examples),0)
    def test_empty_memory_and_typed_label(self):
        session=FeedbackSession(self.memory,self.report('unknown',255))
        session.confirm();self.assertFalse(self.path.exists())
        session.propose('phone');self.assertFalse(self.path.exists())
        session.confirm();self.assertEqual(len(FeedbackMemory(self.path).examples),1)
    def test_exact_wrong_label_replaced_not_duplicated(self):
        self.memory.learn([2]*768,'phone');self.memory.learn([2]*768,'AirPods')
        restored=FeedbackMemory(self.path)
        self.assertEqual(len(restored.examples),1)
        self.assertEqual(restored.examples[0]['label'],'AirPods')
        self.assertEqual(restored.data['events'][-1]['previous_label'],'phone')
    def test_capacity_eviction_and_stale_writer(self):
        stale=FeedbackMemory(self.path)
        for n in range(65):
            d=[0]*768;d[0]=n%16;d[1]=n//16
            self.memory.learn(d,f'object{n}')
        self.assertEqual(len(self.memory.examples),64)
        self.assertNotIn('object0',[e['label'] for e in self.memory.examples])
        with self.assertRaises(RuntimeError):stale.learn([3]*768,'stale')
    def test_bad_memory_and_labels(self):
        for d,label in [([0],'phone'),([16]*768,'phone'),([0]*768,'unknown'),([0]*768,'\n')]:
            with self.assertRaises(ValueError):self.memory.learn(d,label)
        self.assertEqual(parse_feedback('yes correct'),('confirm',None))
        self.assertEqual(parse_feedback('No, it is a phone.'),('label','phone'))

@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'Icarus required')
class MemoryRTLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.exe=compile_memory(cls.root/'run')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def infer(self,image,examples):return infer_memory(image,examples,self.root/'run',self.exe)
    def test_empty_exact_ties_and_extreme_distance(self):
        image=np.zeros((16,16,3),np.uint8)
        result=self.infer(image,[])
        self.assertEqual(result['best_slot'],255)
        self.assertEqual(result['descriptor'],[0]*768)
        examples=[{'label':'white','descriptor':[15]*768},{'label':'black','descriptor':[0]*768},
                  {'label':'black duplicate','descriptor':[0]*768}]
        self.assertEqual(self.infer(image,examples)['best_slot'],1)
        result=self.infer(image,examples[:1])
        self.assertEqual((result['distance'],result['similarity_q8']),(11520,0))
    def test_random_search_at_counts_including_capacity(self):
        rng=np.random.default_rng(31)
        for count in (1,2,7,16,64):
            image=rng.integers(0,256,(16,16,3),dtype=np.uint8)
            features=(image.reshape(-1).astype(np.int64)>>4)
            examples=[{'label':str(n),'descriptor':rng.integers(0,16,768).tolist()} for n in range(count)]
            distance=np.abs(np.array([e['descriptor'] for e in examples])-features).sum(axis=1)
            best=int(np.argmin(distance));expected=int(distance[best])
            result=self.infer(image,examples)
            self.assertEqual((result['best_slot'],result['distance'],result['similarity_q8']),
                (best,expected,255-expected*255//11520))
            self.assertEqual(result['descriptor'],features.tolist())
            means=image.reshape(-1,3).astype(np.int64).sum(axis=0)>>8
            self.assertEqual(result['crop_mean_rgb'],means.tolist())
    def test_feedback_changes_prediction_and_survives_reload(self):
        memory=FeedbackMemory(self.root/'learned.json')
        red=np.full((16,16,3),(220,20,20),np.uint8)
        green=np.full((16,16,3),(20,220,20),np.uint8)
        memory.learn(self.infer(red,[])['descriptor'],'phone')
        wrong=self.infer(green,memory.examples)
        self.assertEqual(wrong['label'],'phone')
        session=FeedbackSession(memory,wrong)
        session.voice('no this is AirPods')
        self.assertEqual(len(memory.examples),1) # transcript alone cannot alter memory
        session.voice('yes')
        restored=FeedbackMemory(memory.path)
        self.assertEqual(self.infer(green,restored.examples)['label'],'AirPods')
        self.assertEqual(self.infer(red,restored.examples)['label'],'phone')
        corrected=FeedbackSession(restored,self.infer(green,restored.examples))
        corrected.propose('tablet');corrected.confirm()
        self.assertEqual(self.infer(green,FeedbackMemory(memory.path).examples)['label'],'tablet')


class VoiceTransportTests(unittest.TestCase):
    def helper(self,source):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        path=Path(directory.name)/'helper'
        path.write_text('#!/usr/bin/env python3\n'+source);path.chmod(0o700)
        return path
    def test_transcript_transport(self):
        helper=self.helper('import json\nprint(json.dumps({"transcript":"no this is AirPods"}))\n')
        self.assertEqual(listen_once(helper),'no this is AirPods')
    def test_permission_error_is_exposed(self):
        helper=self.helper('import sys,json\nprint(json.dumps({"error":"microphone denied"}))\nsys.exit(1)\n')
        with self.assertRaisesRegex(RuntimeError,'microphone denied'):listen_once(helper)
    def test_microphone_helper_cancels_on_exit(self):
        helper=self.helper('import time\ntime.sleep(10)\n')
        cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(RuntimeError,'canceled'):listen_once(helper,cancel=cancel)
