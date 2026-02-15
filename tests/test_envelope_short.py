
import unittest
import numpy as np
from engine.envelope import Envelope

class TestEnvelopeShortNotes(unittest.TestCase):
    def test_minimum_attack_duration(self):
        # Create default envelope (attack ~45ms)
        env = Envelope(sample_rate=44100)
        
        # 1. Trigger Note On
        env.note_on()
        
        # 2. Trigger Note Off IMMEDIATELY (simulating 0-duration within same block)
        env.note_off()
        self.assertEqual(env._stage, 1) 
        self.assertTrue(env._release_pending)
        
        # 3. Render a small chunk (e.g. 10ms = 441 samples)
        # 15ms limit is ~661 samples.
        chunk1 = env.render(441)
        
        # Should still be in ATTACK because 441 < 661
        self.assertEqual(env._stage, 1)
        self.assertTrue(env._release_pending)
        # Output should involve rising values
        self.assertTrue(np.any(chunk1 > 0)) # At least some sound
        self.assertTrue(chunk1[-1] > chunk1[10]) # Rising envelope
        
        # 4. Render enough to pass the threshold (another 300 samples)
        # Total 741 samples > 661.
        chunk2 = env.render(300)
        
        # NOW it should have switched to RELEASE (Stage.RELEASE = 4)
        self.assertEqual(env._stage, 4)
        self.assertFalse(env._release_pending)
        self.assertEqual(env._stage, 4) 

        self.assertEqual(env._stage, 4) 

    def test_short_attack_duration(self):
        env = Envelope(sample_rate=44100, attack_ms=5.0) 
        env.note_on()
        env.note_off() # Trigger pending release
        
        self.assertTrue(env._release_pending)
        
        env.render(300)
        self.assertEqual(env._stage, 4)
        self.assertFalse(env._release_pending)
