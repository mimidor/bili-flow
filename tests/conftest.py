"""
pytest fixtures for tests
"""
import sys
import tempfile
import wave
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# Add project root to import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load the project .env for every test process.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


@pytest.fixture
def temp_dir():
    """Temporary directory fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_wav_path(temp_dir):
    """Create a simple test WAV file"""
    wav_path = temp_dir / "test.wav"

    sample_rate = 16000
    duration = 1
    num_samples = sample_rate * duration

    with wave.open(str(wav_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for _ in range(num_samples):
            wav_file.writeframes(struct.pack("<h", 0))

    return str(wav_path)


@pytest.fixture
def mock_config():
    """Mock Config fixture"""
    with patch("config.Config") as mock_cfg:
        mock_cfg.ASR_PROVIDER = "whisper"
        mock_cfg.ASR_API_KEY = ""
        mock_cfg.ASR_BASE_URL = ""
        mock_cfg.ASR_MODEL = "fun-asr"
        yield mock_cfg


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run fixture"""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run
