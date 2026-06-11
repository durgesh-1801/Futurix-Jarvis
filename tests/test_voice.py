import sys
import os
import unittest
import queue
import time
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice.text_to_speech import TextToSpeech
from voice.speech_to_text import SpeechToText, _ListenWorker

class TestTextToSpeechInterruption(unittest.TestCase):
    """Unit tests for TextToSpeech interruption functionality."""

    @patch("pyttsx3.init")
    def test_tts_queue_cleared_on_stop(self, mock_init):
        # Setup mock engine
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine
        
        # Instantiate TTS (this starts the worker thread)
        tts = TextToSpeech()
        
        # Populate speech requests
        tts.speak("First sentence to speak.")
        tts.speak("Second sentence to speak.")
        tts.speak("Third sentence to speak.")
        
        # Assert items are in the queue
        self.assertFalse(tts._queue.empty())
        
        # Call stop
        tts.stop()
        
        # Assert stop event is set and queue is cleared
        self.assertTrue(tts._stop_event.is_set())
        self.assertTrue(tts._queue.empty() or tts._queue.qsize() == 0)
        
        tts.shutdown()

    @patch("pyttsx3.init")
    def test_tts_interrupt_callback(self, mock_init):
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine
        
        tts = TextToSpeech()
        
        # Verify the started-word callback was connected
        mock_engine.connect.assert_called_with("started-word", unittest.mock.ANY)
        
        # Extract the registered callback
        callback_args = mock_engine.connect.call_args_list
        on_word_callback = None
        for arg in callback_args:
            if arg[0][0] == "started-word":
                on_word_callback = arg[0][1]
                break
                
        self.assertIsNotNone(on_word_callback, "started-word callback was not connected.")
        
        # Trigger callback when stop event is NOT set -> engine.stop should NOT be called
        tts._stop_event.clear()
        on_word_callback("test_word", 0, 4)
        mock_engine.stop.assert_not_called()
        
        # Trigger callback when stop event IS set -> engine.stop should be called
        tts._stop_event.set()
        on_word_callback("test_word", 0, 4)
        mock_engine.stop.assert_called_once()
        
        tts.shutdown()


class TestSpeechToTextCancellation(unittest.TestCase):
    """Unit tests for SpeechToText cancellation functionality."""

    @patch("voice.speech_to_text._import_speech_recognition")
    @patch("voice.speech_to_text._Microphone")
    @patch("voice.speech_to_text._Recognizer")
    def test_stt_cancellation_exits_loop(self, mock_rec_class, mock_mic_class, mock_import):
        # Setup mocks for speech recognition
        import voice.speech_to_text as stt
        stt._sr = MagicMock()
        stt._Microphone = mock_mic_class
        stt._Recognizer = mock_rec_class
        
        mock_import.return_value = None
        
        # Setup mock microphone source
        mock_source = MagicMock()
        mock_source.SAMPLE_RATE = 16000
        mock_source.SAMPLE_WIDTH = 2
        mock_source.CHUNK = 1024
        
        # Mock stream reading to return raw silence data (1024 bytes of \x00)
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * 1024
        mock_source.stream = mock_stream
        
        # Microphone context manager yields the source
        mock_mic_class.return_value.__enter__.return_value = mock_source
        
        # Setup mock recognizer
        mock_rec = MagicMock()
        mock_rec.energy_threshold = 100
        mock_rec.pause_threshold = 0.8
        mock_rec_class.return_value = mock_rec
        
        # Create worker
        worker = _ListenWorker(timeout=5, phrase_time_limit=10)
        
        # Connect slot to keep track of signals
        finished_signals = []
        worker.finished.connect(finished_signals.append)
        
        # Simulate worker cancel in a background thread or immediately
        # Since cancel needs to happen during the loop, we can mock source.stream.read to trigger cancel after 3 iterations
        call_count = 0
        def read_side_effect(chunk_size, exception_on_overflow=False):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                worker.cancel()
            return b"\x00" * chunk_size
            
        mock_stream.read.side_effect = read_side_effect
        
        # Run worker (it will execute standard run loop)
        worker.run()
        
        # Assert loop terminated and finished signal was emitted with empty string
        self.assertTrue(worker._cancelled)
        self.assertEqual(finished_signals, [""])
        self.assertTrue(call_count >= 3)


if __name__ == "__main__":
    unittest.main()
