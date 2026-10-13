import unittest
from unittest.mock import MagicMock, patch
import gemini_model
import gpt_utils

class TestGeminiRetry(unittest.TestCase):
    @patch("gemini_model.genai.Client")
    @patch("gemini_model.time.sleep")
    def test_gemini_model_retries_each_model_5_times_total_15(self, mock_sleep, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # 15回 429 エラーを発生させる
        call_models = []
        def side_effect(model, contents, config):
            call_models.append(model)
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
            
        mock_client.models.generate_content.side_effect = side_effect
        
        with self.assertRaisesRegex(RuntimeError, "RESOURCE_EXHAUSTED"):
            gemini_model.generate_text_with_gemini("fake_key", "test prompt")
            
        # 3モデル × 5回 = 計15回
        self.assertEqual(len(call_models), 15)
        self.assertEqual(call_models.count('gemma-4-31b-it'), 5)
        self.assertEqual(call_models.count('gemma-4-26b-a4b-it'), 5)
        self.assertEqual(call_models.count('gemini-3.8-flash'), 5)

    @patch("gemini_model.genai.Client")
    @patch("gemini_model.time.sleep")
    def test_gemini_model_success_on_fallback(self, mock_sleep, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        call_models = []
        def side_effect(model, contents, config):
            call_models.append(model)
            if len(call_models) <= 5: # モデル1で5回失敗
                raise RuntimeError("500 INTERNAL_ERROR")
            # モデル2の1回目で成功
            mock_resp = MagicMock()
            mock_part = MagicMock()
            mock_part.thought = False
            mock_part.text = "成功回答"
            mock_resp.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
            return mock_resp
            
        mock_client.models.generate_content.side_effect = side_effect
        res = gemini_model.generate_text_with_gemini("fake_key", "test prompt")
        self.assertEqual(res, "成功回答")
        self.assertEqual(len(call_models), 6)
        self.assertEqual(call_models.count('gemma-4-31b-it'), 5)
        self.assertEqual(call_models.count('gemma-4-26b-a4b-it'), 1)

    @patch("gpt_utils.genai.Client")
    @patch("gpt_utils.time.sleep")
    def test_gpt_utils_retries_each_model_5_times_total_15(self, mock_sleep, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        call_models = []
        def side_effect(model, contents, config):
            call_models.append(model)
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
            
        mock_client.models.generate_content.side_effect = side_effect
        
        res = gpt_utils.get_description("fake_key", "test prompt [limit_size]", 100)
        self.assertIsNone(res)
        self.assertEqual(len(call_models), 15)
        self.assertEqual(call_models.count('gemma-4-31b-it'), 5)
        self.assertEqual(call_models.count('gemma-4-26b-a4b-it'), 5)
        self.assertEqual(call_models.count('gemini-3.8-flash'), 5)

    @patch("gemini_model.genai.Client")
    @patch("gemini_model.time.sleep")
    def test_gemini_model_404_switches_immediately(self, mock_sleep, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        call_models = []
        def side_effect(model, contents, config):
            call_models.append(model)
            if model == 'gemma-4-31b-it':
                # モデル1が404
                raise RuntimeError("404 NOT_FOUND: model is no longer available")
            # モデル2で成功
            mock_resp = MagicMock()
            mock_part = MagicMock()
            mock_part.thought = False
            mock_part.text = "切り替え後成功"
            mock_resp.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
            return mock_resp
            
        mock_client.models.generate_content.side_effect = side_effect
        res = gemini_model.generate_text_with_gemini("fake_key", "test prompt")
        self.assertEqual(res, "切り替え後成功")
        # モデル1は404のため1回のみで直ちに次モデルへ切り替わる
        self.assertEqual(call_models.count('gemma-4-31b-it'), 1)
        self.assertEqual(call_models.count('gemma-4-26b-a4b-it'), 1)

    @patch("gemini_model.genai.Client")
    @patch("gemini_model.time.sleep")
    def test_gemini_model_fatal_error_raises_immediately(self, mock_sleep, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        mock_client.models.generate_content.side_effect = RuntimeError("401 API_KEY_INVALID")
        with self.assertRaisesRegex(RuntimeError, "API_KEY_INVALID"):
            gemini_model.generate_text_with_gemini("fake_key", "test prompt")
        # 1回で即座にraiseされる（リトライされない）
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

if __name__ == "__main__":
    unittest.main()
