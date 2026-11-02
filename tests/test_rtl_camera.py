"""End-to-end RTL checks; real simulation is mandatory for these tests."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from rtl_camera.bridge import Stability,compile_simulator,infer_rtl
from rtl_camera.model import export_model,load_model,reference,train

class StabilityTests(unittest.TestCase):
    def test_five_real_seconds_and_motion_reset(self):
        s=Stability();gray=np.zeros((64,64),np.uint8)
        self.assertFalse(s.update(gray,100,0)[0])
        for i in range(1,52):ready,_,_=s.update(gray,100,i/10)
        self.assertTrue(ready)
        self.assertFalse(s.update(gray+100,100,5.2)[0])
        self.assertFalse(s.update(gray+100,0,5.3)[0])
        self.assertFalse(s.update(gray+100,100,7)[0])

@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'Icarus is required for RTL regression')
class RTLCameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.exe=compile_simulator(cls.root/'run')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def check_frame(self,image,folder,threshold):
        meta,arrays=load_model(folder)
        expected=reference(image,arrays,len(meta['labels']),threshold)
        result=infer_rtl(image,folder,self.root/'run',self.exe,threshold)
        self.assertEqual(result['rtl_values'],expected)
        return result
    def test_random_model_images_and_saturation(self):
        rng=np.random.default_rng(12)
        folder=self.root/'random'
        w1=rng.uniform(-1.9,1.9,(32,768));b1=rng.uniform(-20,20,32)
        w2=rng.uniform(-1.9,1.9,(16,32));b2=rng.uniform(-20,20,16)
        export_model(folder,[f'class{i}' for i in range(16)],w1,b1,w2,b2,{'test_only':True})
        for n in range(12):
            self.check_frame(rng.integers(0,256,(16,16,3),dtype=np.uint8),folder,n*23)
    def test_colors_unknown_and_first_class_ties(self):
        folder=self.root/'ties'
        export_model(folder,['one','two'],np.zeros((32,768)),np.zeros(32),np.zeros((2,32)),np.zeros(2),{'test_only':True})
        for rgb in [(0,0,0),(255,255,255),(128,128,128),(250,30,10),(10,250,30),(10,30,250)]:
            image=np.full((16,16,3),rgb,dtype=np.uint8)
            self.assertEqual(self.check_frame(image,folder,153)['label'],'unknown')
            self.assertEqual(self.check_frame(image,folder,0)['class_id'],0)
    def test_corrupt_model_is_rejected(self):
        folder=self.root/'corrupt'
        export_model(folder,['one','two'],np.zeros((32,768)),np.zeros(32),np.zeros((2,32)),np.zeros(2),{})
        (folder/'w1.hex').write_text('ff\n')
        with self.assertRaises(ValueError):load_model(folder)
    def test_training_export_and_rtl(self):
        rng=np.random.default_rng(8)
        images=[];targets=[]
        for c in range(2):
            for _ in range(24):
                a=rng.integers(0,25,(16,16,3),dtype=np.uint8)
                a[:,:,c]+=200
                images.append(a);targets.append(c)
        folder=self.root/'trained'
        meta=train(np.stack(images),targets,['synthetic_red','synthetic_green'],folder,epochs=120)
        self.assertEqual(meta['training']['integer_validation_accuracy'],1.)
        for n in (0,23,24,47):
            self.assertEqual(self.check_frame(images[n],folder,153)['class_id'],targets[n])

if __name__=='__main__':unittest.main()
