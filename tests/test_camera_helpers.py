import sys,time,unittest
from pathlib import Path
try:
    import cv2,numpy as np,torch,torchvision
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
    from mac_camera import annotate,LatestFrame
    AVAILABLE=True
except ImportError:
    AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'camera app dependencies are optional')
class CameraHelpers(unittest.TestCase):
    def test_annotation_keeps_original_frame(self):
        frame=np.zeros((100,160,3),dtype=np.uint8)
        output=annotate(frame,[{'label':'chair','score':.8,'box_xyxy':[-3,-3,999,999]}],.1)
        self.assertEqual(output.shape,frame.shape)
        self.assertTrue(np.any(output))
        self.assertFalse(np.any(frame))

    def test_latest_frame_copy_and_cleanup(self):
        class FakeCapture:
            released=False
            def read(self):
                time.sleep(.002)
                return True,np.ones((4,4,3),dtype=np.uint8)
            def release(self):self.released=True
        cap=FakeCapture();source=LatestFrame(cap);source.thread.start()
        try:
            deadline=time.monotonic()+2
            while source.latest()[1] is None and time.monotonic()<deadline:time.sleep(.005)
            seq,frame=source.latest();self.assertGreater(seq,0)
            frame[:]=0
            self.assertTrue(np.all(source.latest()[1]==1))
        finally:source.close()
        self.assertTrue(cap.released);self.assertFalse(source.thread.is_alive())

if __name__=='__main__':unittest.main()
