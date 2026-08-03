import sys
from unittest.mock import MagicMock

# Mock paddleocr before it's imported by ocr.py
sys.modules['paddleocr'] = MagicMock()
