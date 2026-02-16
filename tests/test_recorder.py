
import unittest
import os
import time
import mido
from engine.recorder import Recorder

class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.filename = "test_recording.mid"
        self.recorder = Recorder()
        
    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)
            
    def test_record_and_save(self):
        self.recorder.start()
        self.assertTrue(self.recorder.is_recording)
        
        # Simulate some events
        self.recorder.record_event("note_on", 60, 64)
        time.sleep(0.1)
        self.recorder.record_event("note_off", 60, 0)
        time.sleep(0.1)
        self.recorder.record_event("note_on", 64, 64)
        time.sleep(0.1)
        self.recorder.record_event("note_off", 64, 0)
        
        self.recorder.stop()
        self.assertFalse(self.recorder.is_recording)
        
        saved = self.recorder.save(self.filename)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(self.filename))
        
        # Verify content
        mid = mido.MidiFile(self.filename)
        self.assertEqual(len(mid.tracks), 1)
        
        # Track 0 should have 4 messages + maybe meta messages (end of track)
        # We expect at least 4 note messages
        note_msgs = [m for m in mid.tracks[0] if m.type in ['note_on', 'note_off']]
        self.assertEqual(len(note_msgs), 4)
        
        self.assertEqual(note_msgs[0].note, 60)
        self.assertEqual(note_msgs[0].type, 'note_on')
        
        self.assertEqual(note_msgs[1].note, 60)
        self.assertEqual(note_msgs[1].type, 'note_off')
        
        self.assertEqual(note_msgs[2].note, 64)
        self.assertEqual(note_msgs[2].type, 'note_on')
        
        self.assertEqual(note_msgs[3].note, 64)
        self.assertEqual(note_msgs[3].type, 'note_off')

    def test_record_with_offset(self):
        # Start recording with 2.0s offset
        self.recorder.start(initial_offset=2.0)
        self.recorder.record_event("note_on", 60, 100)
        
        self.recorder.stop()
        
        events = self.recorder._events
        self.assertEqual(len(events), 1)
        # Timestamp should be approx 2.0 (allow small delta)
        self.assertAlmostEqual(events[0].timestamp, 2.0, delta=0.1)

    def test_get_midi_file(self):
        self.recorder.start()
        self.recorder.record_event("note_on", 60, 100)
        time.sleep(0.01)
        self.recorder.record_event("note_off", 60, 0)
        self.recorder.stop()
        
        mid = self.recorder.get_midi_file()
        self.assertIsNotNone(mid)
        self.assertEqual(len(mid.tracks), 1)
        
        # Check messages
        track = mid.tracks[0]
        self.assertGreater(len(track), 0)
        notes = [m for m in track if m.type == 'note_on']
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].note, 60)

if __name__ == '__main__':
    unittest.main()
