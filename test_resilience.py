import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json

# Ensure project directory is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import speech_recognition as sr
from logger import logger, LOG_FILE
import skills.voice_input as voice_input
import main
import status

class TestDeeksResilience(unittest.TestCase):

    def setUp(self):
        # Clear log file for tests if needed
        pass

    def test_logger_creates_file_and_logs(self):
        """Verify logger properly writes to logs/deeks.log."""
        logger.info("Unit test message: verification run")
        self.assertTrue(os.path.exists(LOG_FILE))
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Unit test message: verification run", content)

    @patch("skills.voice_input.sr.Microphone")
    @patch("skills.voice_input.sr.Recognizer")
    def test_speech_recognition_retry_and_internet_error(self, mock_recognizer_cls, mock_mic_cls):
        """Verify listen() retries on RequestError and returns 'error_internet' after max_retries."""
        mock_rec = MagicMock()
        mock_recognizer_cls.return_value = mock_rec
        mock_rec.listen.return_value = MagicMock()
        
        # Simulate network error on all attempts
        mock_rec.recognize_google.side_effect = sr.RequestError("Could not reach Google Speech API")

        result = voice_input.listen(max_retries=2, retry_delay=0.01)
        self.assertEqual(result, "error_internet")
        self.assertEqual(mock_rec.recognize_google.call_count, 3)

    @patch("skills.voice_input.sr.Microphone")
    @patch("skills.voice_input.sr.Recognizer")
    def test_speech_recognition_recovers_on_retry(self, mock_recognizer_cls, mock_mic_cls):
        """Verify listen() successfully returns text if a retry succeeds."""
        mock_rec = MagicMock()
        mock_recognizer_cls.return_value = mock_rec
        mock_rec.listen.return_value = MagicMock()
        
        # First attempt fails with network error, second attempt succeeds
        mock_rec.recognize_google.side_effect = [
            sr.RequestError("Temporary glitch"),
            "what time is it"
        ]

        result = voice_input.listen(max_retries=2, retry_delay=0.01)
        self.assertEqual(result, "what time is it")
        self.assertEqual(mock_rec.recognize_google.call_count, 2)

    @patch("main.speak")
    def test_execute_command_resilience_to_exceptions(self, mock_speak):
        """Verify execute_command handles unexpected errors in skills gracefully without crashing."""
        # Intentionally test various commands
        res = main.execute_command("what time is it")
        self.assertTrue(res)
        self.assertTrue(mock_speak.called)

        # Test command with memory
        res = main.execute_command("remember test key 123")
        self.assertTrue(res)
        
        res = main.execute_command("what did i tell you to remember")
        self.assertTrue(res)

        # Test shutdown command returns False
        res = main.execute_command("goodbye")
        self.assertFalse(res)

    def test_status_tracking(self):
        """Verify update_status writes status.json and deeks.pid and cleanup cleans it up."""
        main.update_status(is_running=True)
        st = status.get_status()
        self.assertTrue(st.get("is_running"))
        self.assertEqual(st.get("pid"), os.getpid())

        # Now clean up
        main.cleanup()
        st_after = status.get_status()
        self.assertFalse(st_after.get("is_running"))

    @patch("main.speak")
    def test_internet_warning_logic_flow(self, mock_speak):
        """Simulate internet warning state tracking."""
        internet_warned = False
        spoken_warnings = 0

        # Sequence of recognition results: 3 failures, then 1 success, then 1 failure
        events = ["error_internet", "error_internet", "error_internet", "what time is it", "error_internet"]
        for event in events:
            if event == "error_internet":
                if not internet_warned:
                    spoken_warnings += 1
                    internet_warned = True
            elif event is not None:
                if internet_warned:
                    internet_warned = False

        # Should only have spoken the warning twice total (once for 1st outage, once for 2nd outage)
        self.assertEqual(spoken_warnings, 2)



    @patch("urllib.request.urlopen")
    def test_weather_skill_get_weather(self, mock_urlopen):
        """Verify get_weather parses geocoding and forecast successfully."""
        from skills.weather_skill import get_weather
        
        # Mock responses for geocoding and forecast
        mock_geo_resp = MagicMock()
        mock_geo_resp.__enter__.return_value = mock_geo_resp
        mock_geo_resp.read.return_value = json.dumps({
            "results": [{"name": "Chicago", "country": "United States", "latitude": 41.85, "longitude": -87.65}]
        }).encode("utf-8")

        mock_forecast_resp = MagicMock()
        mock_forecast_resp.__enter__.return_value = mock_forecast_resp
        mock_forecast_resp.read.return_value = json.dumps({
            "current": {"temperature_2m": 22.4, "weather_code": 2},
            "daily": {"precipitation_probability_max": [15]}
        }).encode("utf-8")

        mock_urlopen.side_effect = [mock_geo_resp, mock_forecast_resp]

        res = get_weather("Chicago")
        self.assertTrue(res["success"])
        self.assertEqual(res["city"], "Chicago")
        self.assertEqual(res["temperature"], 22)
        self.assertEqual(res["condition"], "partly cloudy")
        self.assertEqual(res["chance_of_rain"], 15)
        self.assertIn("It's 22 degrees and partly cloudy", res["summary"])

    @patch("main.speak")
    @patch("main.get_weather")
    @patch("main.load_memory")
    def test_execute_weather_command(self, mock_load_memory, mock_get_weather, mock_speak):
        """Verify execute_command handles weather requests using default city."""
        mock_load_memory.return_value = "Chicago"
        mock_get_weather.return_value = {
            "success": True,
            "summary": "It's 22 degrees and partly cloudy, with a 15% chance of rain today in Chicago."
        }

        res = main.execute_command("what's the weather like")
        self.assertTrue(res)
        mock_get_weather.assert_called_with("Chicago")
        mock_speak.assert_called_with("It's 22 degrees and partly cloudy, with a 15% chance of rain today in Chicago.")

    def test_schedule_add_and_get(self):
        """Verify schedule skill parses events and retrieves agenda."""
        from skills.schedule_skill import add_event_from_text, get_schedule
        
        # Test adding event
        success, msg = add_event_from_text("add an event tomorrow at 3pm dentist appointment")
        self.assertTrue(success)
        self.assertIn("dentist appointment", msg)
        self.assertIn("3:00 PM", msg)

        # Test querying schedule
        tomorrow_schedule = get_schedule("tomorrow")
        self.assertIn("dentist appointment", tomorrow_schedule)
        self.assertIn("3:00 PM", tomorrow_schedule)

    @patch("main.speak")
    def test_execute_schedule_commands(self, mock_speak):
        """Verify execute_command handles add event and check schedule queries."""
        # Add event command
        res = main.execute_command("add an event tomorrow at 3pm dentist appointment")
        self.assertTrue(res)
        self.assertTrue(mock_speak.called)

        # Check schedule command
        res2 = main.execute_command("what's on my schedule tomorrow")
        self.assertTrue(res2)
        mock_speak.called

    @patch("urllib.request.urlopen")
    def test_news_skill_get_top_headlines(self, mock_urlopen):
        """Verify get_top_headlines parses RSS XML and formats spoken summary."""
        from skills.news_skill import get_top_headlines
        
        sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>BBC News</title>
                <item><title>Global Tech Summit kicks off in Tokyo - BBC News</title></item>
                <item><title>Space mission returns with lunar samples</title></item>
                <item><title>New renewable energy record set</title></item>
            </channel>
        </rss>"""
        
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = sample_rss.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        res = get_top_headlines(limit=3)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["headlines"]), 3)
        self.assertEqual(res["headlines"][0], "Global Tech Summit kicks off in Tokyo")
        self.assertIn("First: Global Tech Summit kicks off in Tokyo", res["summary"])

    @patch("main.speak")
    @patch("main.get_top_headlines")
    def test_execute_news_commands(self, mock_get_news, mock_speak):
        """Verify execute_command handles news queries."""
        mock_get_news.return_value = {
            "success": True,
            "headlines": ["Headline 1", "Headline 2"],
            "summary": "Here are the top headlines. First: Headline 1. Second: Headline 2."
        }

        res = main.execute_command("what's the news")
        self.assertTrue(res)
        mock_speak.assert_called_with("Here are the top headlines. First: Headline 1. Second: Headline 2.")

        res2 = main.execute_command("give me the headlines")
        self.assertTrue(res2)

    @patch("skills.briefing_skill.get_top_headlines")
    @patch("skills.briefing_skill.get_schedule")
    @patch("skills.briefing_skill.get_weather")
    @patch("skills.briefing_skill.load_memory")
    def test_briefing_skill_generation(self, mock_load_memory, mock_get_weather, mock_get_schedule, mock_get_news):
        """Verify get_daily_briefing formats time-of-day greeting, weather, schedule, and news smoothly."""
        from skills.briefing_skill import get_daily_briefing

        mock_load_memory.return_value = "Chicago"
        mock_get_weather.return_value = {
            "success": True,
            "summary": "It's 22 degrees and partly cloudy, with a 15% chance of rain today in Chicago."
        }
        mock_get_schedule.return_value = "On your schedule for today: at 3:00 PM, dentist appointment."
        mock_get_news.return_value = {
            "success": True,
            "headlines": ["Headline A", "Headline B", "Headline C"],
            "summary": "..."
        }

        briefing = get_daily_briefing()
        self.assertIn("Here is your daily briefing", briefing)
        self.assertIn("22 degrees and partly cloudy", briefing)
        self.assertIn("dentist appointment", briefing)
        self.assertIn("First, Headline A", briefing)
        self.assertIn("Second, Headline B", briefing)
        self.assertIn("Third, Headline C", briefing)

    @patch("main.speak")
    @patch("main.get_daily_briefing")
    def test_execute_briefing_command(self, mock_get_briefing, mock_speak):
        """Verify execute_command triggers daily briefing."""
        mock_get_briefing.return_value = "Good morning! Here is your daily briefing."

        res = main.execute_command("give me my daily briefing")
        self.assertTrue(res)
        mock_speak.assert_called_with("Good morning! Here is your daily briefing.")

        res2 = main.execute_command("brief me")
        self.assertTrue(res2)

    @patch("main.speak")
    @patch("skills.volume_control._get_volume_control")
    def test_volume_control_commands(self, mock_get_vol, mock_speak):
        """Verify volume control skill handles set, up, down, mute, and unmute commands."""
        mock_vol = MagicMock()
        mock_vol.GetMasterVolumeLevelScalar.return_value = 0.5
        mock_get_vol.return_value = mock_vol

        # Test set volume
        res = main.execute_command("set volume to 70")
        self.assertTrue(res)
        mock_vol.SetMasterVolumeLevelScalar.assert_called_with(0.7, None)
        mock_speak.assert_called_with("Volume set to 70 percent.")

        # Test volume up
        res_up = main.execute_command("volume up")
        self.assertTrue(res_up)
        mock_speak.assert_called_with("Volume increased to 60 percent.")

        # Test mute
        res_mute = main.execute_command("mute")
        self.assertTrue(res_mute)
        mock_vol.SetMute.assert_called_with(1, None)
        mock_speak.assert_called_with("Muted.")

        # Test unmute
        res_unmute = main.execute_command("unmute")
        self.assertTrue(res_unmute)
        mock_vol.SetMute.assert_called_with(0, None)
        mock_speak.assert_called_with("Unmuted.")

    @patch("main.speak")
    @patch("psutil.process_iter")
    def test_close_app_commands(self, mock_process_iter, mock_speak):
        """Verify close_application terminates matching processes and handles non-running apps."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {"name": "chrome.exe", "pid": 1234}
        mock_proc2 = MagicMock()
        mock_proc2.info = {"name": "chrome.exe", "pid": 5678}
        
        mock_process_iter.return_value = [mock_proc1, mock_proc2]

        # Test closing running app ("close chrome")
        res = main.execute_command("close chrome")
        self.assertTrue(res)
        mock_proc1.terminate.assert_called_once()
        mock_proc2.terminate.assert_called_once()
        mock_speak.assert_called_with("Closed Chrome")

        # Test quit app ("quit notepad" when not running)
        mock_process_iter.return_value = []
        res2 = main.execute_command("quit notepad")
        self.assertTrue(res2)
        mock_speak.assert_called_with("Notepad doesn't seem to be running")

    @patch("main.speak")
    @patch("main.lock_pc")
    @patch("main.take_screenshot")
    def test_system_utils_commands(self, mock_take_ss, mock_lock_pc, mock_speak):
        """Verify lock_pc and take_screenshot voice command handlers."""
        # Test Lock PC command
        res = main.execute_command("lock screen")
        self.assertTrue(res)
        mock_speak.assert_called_with("Locking your PC")
        mock_lock_pc.assert_called_once()

        # Test Screenshot command
        mock_take_ss.return_value = "Screenshot saved"
        res_ss = main.execute_command("take a screenshot")
        self.assertTrue(res_ss)
        mock_take_ss.assert_called_once()
        mock_speak.assert_called_with("Screenshot saved")

    @patch("main.speak")
    @patch("main.listen")
    @patch("os.system")
    def test_power_control_commands(self, mock_os_system, mock_listen, mock_speak):
        """Verify shutdown and restart confirmation, cancellation, and execution."""
        # Case 1: Shutdown confirmed
        mock_listen.return_value = "yes"
        res1 = main.execute_command("shut down the pc")
        self.assertTrue(res1)
        mock_speak.assert_any_call("Are you sure you want to shut down? Say yes to confirm.")
        mock_speak.assert_any_call("Shutting down in 5... 4... 3... 2... 1...")
        mock_os_system.assert_called_with("shutdown /s /t 0")

        # Case 2: Restart cancelled (user says no or times out)
        mock_listen.return_value = "no"
        res2 = main.execute_command("restart the pc")
        self.assertTrue(res2)
        mock_speak.assert_any_call("Are you sure you want to restart? Say yes to confirm.")
        mock_speak.assert_any_call("Restart cancelled.")

if __name__ == "__main__":
    unittest.main()
