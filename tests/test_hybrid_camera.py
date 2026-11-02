"""Hybrid policy with controlled detections and actual RTL memory execution."""
from pathlib import Path
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from rtl_camera.feedback import FeedbackMemory,FeedbackSession
from rtl_camera.memory_bridge import compile_memory
from rtl_camera.pretrained import infer_hybrid,choose_object,object_label,compatible_examples,setup_certificates

class FakeDetector:
    def __init__(self,detections):self.detections=detections
    def detect(self,frame):return self.detections

def detection(label='phone',box=None):return {'label':label,'score':.87,'box_xyxy':box or [8,8,56,56]}

class HybridPolicyTests(unittest.TestCase):
    def test_class_aliases_and_target_selection(self):
        self.assertEqual(object_label('cell phone'),'phone')
        self.assertEqual(object_label('laptop'),'laptop')
        selected=choose_object([detection('person'),detection('phone')],64,64)
        self.assertEqual(selected['label'],'phone')
        self.assertIsNone(choose_object([detection('bad',[4,4,4,4])],64,64))
        self.assertEqual(choose_object([detection('laptop',[-5,-5,70,70])],64,64)['box_xyxy'],[0,0,64,64])
    def test_custom_ca_is_preserved(self):
        with patch.dict(os.environ,{'SSL_CERT_FILE':'/custom/cert.pem'}):
            setup_certificates();self.assertEqual(os.environ['SSL_CERT_FILE'],'/custom/cert.pem')
    def test_legacy_memory_scope_is_explicit(self):
        old=[{'label':'phone','descriptor':[0]*768}]
        self.assertEqual(compatible_examples(old,{'base_label':'phone','descriptor_scope':'detected-object-v1'}),[])
        self.assertEqual(compatible_examples(old,{'base_label':None,'descriptor_scope':'center-crop-v1'}),old)

@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'Icarus required')
class HybridRTLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.exe=compile_memory(cls.root/'run')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.memory=FeedbackMemory(self.root/(self._testMethodName+'.json'))
    def infer(self,frame,label='phone',examples=None):
        detector=FakeDetector([] if label is None else [detection(label)])
        return infer_hybrid(frame,self.memory.examples if examples is None else examples,self.root/'run',self.exe,detector)
    def test_basic_label_works_with_empty_memory_and_can_be_confirmed(self):
        frame=np.full((64,64,3),(20,40,220),dtype=np.uint8) # BGR red
        result=self.infer(frame)
        self.assertEqual(result['label'],'phone')
        self.assertEqual(result['prediction_source'],'pretrained_software')
        self.assertEqual(result['best_slot'],255)
        session=FeedbackSession(self.memory,result)
        self.assertEqual(session.guess,'phone')
        session.voice('yes')
        self.assertEqual(self.memory.examples[0]['context']['base_label'],'phone')
        self.assertEqual(self.infer(frame)['prediction_source'],'confirmed_memory')
    def test_correction_overrides_same_object_after_reload(self):
        frame=np.full((64,64,3),(20,40,220),dtype=np.uint8)
        session=FeedbackSession(self.memory,self.infer(frame))
        session.voice('no this is my phone');self.assertEqual(len(self.memory.examples),0)
        session.voice('yes')
        examples=FeedbackMemory(self.memory.path).examples
        result=self.infer(frame,examples=examples)
        self.assertEqual(result['label'],'my phone')
        self.assertEqual(result['prediction_source'],'confirmed_memory')
        self.assertEqual(result['crop_mean_rgb'],[220,40,20])
    def test_other_class_and_weak_color_match_do_not_override_baseline(self):
        red=np.full((64,64,3),(0,0,255),dtype=np.uint8)
        session=FeedbackSession(self.memory,self.infer(red))
        session.propose('my phone');session.confirm()
        laptop=self.infer(red,'laptop')
        self.assertEqual(laptop['label'],'laptop');self.assertEqual(laptop['memory_candidates'],0)
        green=np.full((64,64,3),(0,255,0),dtype=np.uint8)
        result=self.infer(green)
        self.assertEqual(result['label'],'phone');self.assertFalse(result['memory_used'])
    def test_no_detection_still_learns_user_named_object(self):
        frame=np.full((64,64,3),(250,250,250),dtype=np.uint8)
        result=self.infer(frame,None);self.assertEqual(result['label'],'unknown')
        session=FeedbackSession(self.memory,result);session.propose('AirPods');session.confirm()
        result=self.infer(frame,None)
        self.assertEqual(result['label'],'AirPods');self.assertTrue(result['memory_used'])
