import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from arithmetic_reference import dot4

class ImageVectors(unittest.TestCase):
    def test_real_model_manifest(self):
        v=json.loads((ROOT/'examples/image_nn/vectors.json').read_text())
        self.assertEqual(len(v['labels']),80)
        self.assertEqual(v['kernel_shape'][1:],[3,3,3])
        self.assertEqual(len(v['weights_sha256']),64)
        self.assertEqual(len(v['jobs']),8)

    def test_packed_convolution_accumulators(self):
        v=json.loads((ROOT/'examples/image_nn/vectors.json').read_text())
        for j in v['jobs']:
            with self.subTest(y=j['output_y'],x=j['output_x'],channel=j['output_channel']):
                self.assertEqual(len(j['a_words']),7)
                self.assertEqual(len(j['b_words']),7)
                self.assertEqual(j['a_words'][-1]>>24,0)
                self.assertEqual(j['b_words'][-1]>>24,0)
                total=j['bias']
                for a,b in zip(j['a_words'],j['b_words']):
                    total,overflow=dot4(a,b,total)
                    self.assertFalse(overflow)
                self.assertEqual(total,j['expected'])

if __name__=='__main__':unittest.main()
