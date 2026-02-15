
import unittest
import numpy as np
from engine.mixer import Mixer, EventType

class TestMixerPolyphony(unittest.TestCase):
    def setUp(self):
        self.mixer = Mixer(sample_rate=44100)
        
    def test_polyphony_on_same_note(self):
        # 1. Start note 60
        self.mixer.note_on(60)
        self.mixer._process_events()
        
        self.assertIn(60, self.mixer._active_voices)
        self.assertEqual(len(self.mixer._active_voices), 1)
        self.assertEqual(len(self.mixer._releasing_voices), 0)
        
        voice1 = self.mixer._active_voices[60]
        
        # 2. Start note 60 AGAIN (should move voice1 to releasing)
        self.mixer.note_on(60)
        self.mixer._process_events()
        
        self.assertIn(60, self.mixer._active_voices)
        self.assertEqual(len(self.mixer._active_voices), 1)
        self.assertEqual(len(self.mixer._releasing_voices), 0)
        
        voice2 = self.mixer._active_voices[60]
        self.assertEqual(voice1, voice2) 
        self.assertTrue(voice1.is_active) 
        
        # 3. Stop note 60
        self.mixer.note_off(60)
        self.mixer._process_events()
        
        self.assertEqual(len(self.mixer._active_voices), 0)
        self.assertEqual(len(self.mixer._releasing_voices), 1)
        self.assertEqual(self.mixer._releasing_voices[0], voice1)
        
    def test_voice_cleanup(self):
        self.mixer.note_on(60)
        self.mixer._process_events()
        self.mixer.note_off(60)
        self.mixer._process_events()
        
        self.assertEqual(len(self.mixer._releasing_voices), 1)
        
        # Render enough frames for the release to finish
        self.mixer.render(70000)
        
        # Render one more small chunk to trigger cleanup (since cleanup happens on checking is_active)
        self.mixer.render(100)
        
        # Should be empty now
        self.assertEqual(len(self.mixer._releasing_voices), 0)

if __name__ == '__main__':
    unittest.main()
