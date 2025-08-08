"""Text2Movie.py
  This script processes text input to create video clips with audio using OpenAI's TTS API.
  It extracts paragraphs, splits them into sentences, generates audio for each sentence,
  and creates video clips with the audio and text displayed.
  Usage: python Text2Movie.py <input_file> <suffix>(optional)
  Example: python Text2Movie.py input.txt my_suffix_
"""
import time
import random
import openai
import sys
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import io
import wave
import math
import struct
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip
import textwrap

TEST_MODE = False  # Set to True for testing without OpenAI API

@dataclass
class Config:
  """Configuration settings for the Text2Movie application."""
  temp_audio_file: str = "temp.mp3"
  output_folder: str = "output"
  temp_silent_file: str = "silence.mp3"
  process_speaker: str = "[Me]"
  video_width: int = 640
  video_height: int = 480
  font_size: int = 32
  text_wrap_width: int = 40
  min_sentence_length: int = 30
  fps: int = 30
  available_voices: List[str] = None
  
  def __post_init__(self):
    if self.available_voices is None:
      self.available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

@dataclass
class Paragraph:
  """Class to hold speaker and content pairs."""
  speaker: str = ""
  content: str = ""

@dataclass
class ReviewCard:
  """Class to hold audio path and text for each review card."""
  audio_path: str = ""
  text: str = ""

class Text2MovieProcessor:
  """Main processor class for Text2Movie functionality."""
  
  def __init__(self, config: Config = None):
    self.config = config or Config()
    self.review_cards: List[ReviewCard] = []
    
  def process_command_line_args(self) -> tuple:
    """Process command line arguments."""
    if len(sys.argv) < 2:
      print("Usage: python Text2Movie.py <input_file> <suffix>(optional)")
      sys.exit(1)

    input_text_file = sys.argv[1]
    suffix = sys.argv[2] if len(sys.argv) > 2 else ""
    return input_text_file, suffix

  def create_movie(self, text: str, audio_file: str, output_file: str = "test_with_audio.mp4"):
    """Create a movie with the given text and audio file."""
    img = Image.new('RGB', (self.config.video_width, self.config.video_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
      font = ImageFont.truetype("arial.ttf", self.config.font_size)
    except:
      font = ImageFont.load_default()
      font.size = self.config.font_size
    
    # Insert newline characters
    text = "\n".join([textwrap.fill(line, width=self.config.text_wrap_width) for line in text.splitlines()])

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
      ((self.config.video_width - text_width) / 2, (self.config.video_height - text_height) / 2),
      text, fill=(0, 0, 0), font=font
    )
    frame = np.array(img)

    audio_clip = AudioFileClip(audio_file)
    duration = audio_clip.duration - 2.0 / self.config.fps

    video_clip = ImageClip(frame).set_duration(duration).set_audio(audio_clip.set_duration(duration))
    video_clip.write_videofile(output_file, fps=self.config.fps, codec="libx264", audio_codec="aac")
    audio_clip.close()

  def get_paragraphs(self, input_string: str) -> List[Paragraph]:
    """Extract paragraphs from the input string."""
    paragraphs = []
    paragraph_pattern = re.compile(r'([a-zA-Z\[\]]+):\s*([\s\S]*?)(?=(?:[a-zA-Z\[\]]+:)|\Z)')
    for match in paragraph_pattern.finditer(input_string):
      paragraph = Paragraph()
      paragraph.speaker = match.group(1).strip()
      paragraph.content = match.group(2).strip()
      paragraphs.append(paragraph)
    return paragraphs

  def split_string_to_sentences(self, input_string: str, min_length: int = None) -> List[str]:
    """Split the input string into sentences based on punctuation."""
    if min_length is None:
      min_length = self.config.min_sentence_length
      
    sentences = re.split(r'(?<=[.!?])\s+', input_string)
    input_sentences = []
    acc_len_sentence = 0
    acc_sentence = ""
    
    for sentence in sentences:
      sentence = sentence.strip()
      acc_sentence += sentence + " "
      acc_len_sentence += len(sentence)
      if acc_len_sentence > min_length:
        input_sentences.append(acc_sentence.strip())
        acc_sentence = ""
        acc_len_sentence = 0
    if acc_sentence:
      input_sentences.append(acc_sentence.strip())
    
    return input_sentences

  def create_test_audio(self):
    """Create a test audio file with a sine wave."""
    duration = 2.0  # seconds
    sample_rate = 22050
    frequency = 440.0  # Hz
    amplitude = 32767

    num_samples = int(sample_rate * duration)
    sine_wave = [
      int(amplitude * math.sin(2 * math.pi * frequency * t / sample_rate))
      for t in range(num_samples)
    ]

    # Write to a WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
      wav_file.setnchannels(1)
      wav_file.setsampwidth(2)
      wav_file.setframerate(sample_rate)
      wav_file.writeframes(b''.join(struct.pack('<h', s) for s in sine_wave))

    wav_buffer.seek(0)

    # Convert WAV to MP3 using ffmpeg (if available)
    try:
      ffmpeg = subprocess.Popen(
        ['ffmpeg', '-y', '-f', 'wav', '-i', 'pipe:0', '-f', 'mp3', 'pipe:1'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
      )
      mp3_data, _ = ffmpeg.communicate(wav_buffer.read())
      if mp3_data:
        return mp3_data
    except Exception as e:
      print("ffmpeg not available or failed, returning WAV data instead.")
      return wav_buffer.getvalue()

  def get_speak_audio(self, text: str) -> Optional[bytes]:
    """Get audio from OpenAI TTS API."""

    if( TEST_MODE ):
      return self.create_test_audio()
    try:
      selected_voice = random.choice(self.config.available_voices)
      response = openai.audio.speech.create(
        model="tts-1",
        voice=selected_voice,
        input=text.strip(),
        response_format="mp3",
      )
      return response.content
    except Exception as e:
      print(f"Error generating speech: {e}")
      return None

  def create_audio_with_silence(self, audio_file: str, speed: float = 1.0):
    """Add silence to the end of the audio file."""
    try:
      # get the duration of the audio file
      audio_clip = AudioFileClip(self.config.temp_audio_file)
      # 50% longer than the audio duration plus 1 second
      silent_duration = int(audio_clip.duration*1.5 + 1.0)
      audio_clip.close()

      # Create silence file
      subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', 
        '-t', str(silent_duration), self.config.temp_silent_file
      ], check=True, capture_output=True)

      # create "audio_file" with adjusted speed of the temporary audio
      subprocess.run([
        'ffmpeg', '-i', self.config.temp_audio_file, '-filter:a', f'atempo={speed}', 
        '-vn', audio_file
      ], check=True, capture_output=True)

      combined_file = f"combined_{audio_file}"
      with open("concat_list.txt", "w") as f:
        f.write(f"file '{audio_file}'\n")
        f.write(f"file '{self.config.temp_silent_file}'\n")
      
      subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'concat_list.txt', 
        '-c', 'copy', combined_file
      ], check=True, capture_output=True)
      
      os.remove("concat_list.txt")
      os.replace(combined_file, audio_file)
      
    except subprocess.CalledProcessError as e:
      print(f"Error processing audio: {e}")
    except Exception as e:
      print(f"Unexpected error in audio processing: {e}")

  def create_output_files(self, suffix: str, all_movie_file: str):
    """Create output files for the review cards."""
    # Create output folder if it doesn't exist
    if not os.path.exists(self.config.output_folder):
      if os.path.isdir(self.config.output_folder):
        import shutil
        shutil.rmtree(self.config.output_folder)
      os.makedirs(self.config.output_folder)

    out_file_text = os.path.join(self.config.output_folder, "output_files.txt")

    # Create output file list
    with open(out_file_text, "a", encoding="utf-8") as f:
      for review_card in self.review_cards:
        base_name = review_card.audio_path.replace('.mp3', '.mp4')
        output_file = os.path.join(self.config.output_folder, f"{suffix}{base_name}")
        self.create_movie(review_card.text, review_card.audio_path, output_file)
        f.write(f"file '{suffix}{base_name}'\n")
    
    # Combine videos
    try:
      subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", out_file_text, 
        "-c", "copy", f"{self.config.output_folder}/{all_movie_file}"
      ], check=True)
    except subprocess.CalledProcessError as e:
      print(f"Error combining videos: {e}")

  def remove_temp_files(self):
    """Remove temporary files created during the process."""
    for review_card in self.review_cards:
      if os.path.exists(review_card.audio_path):
        os.remove(review_card.audio_path)
    if os.path.exists(self.config.temp_silent_file):
      os.remove(self.config.temp_silent_file)
    if os.path.exists(self.config.temp_audio_file):
      os.remove(self.config.temp_audio_file)

  def process_text_to_movies(self, input_text_file: str, suffix: str = ""):
    """Main processing function."""
    # Validate input file
    if not os.path.exists(input_text_file):
      print(f"Input file '{input_text_file}' does not exist.")
      sys.exit(1)
      
    with open(input_text_file, "r", encoding="utf-8") as f:
      input_string = f.read()

    # Setup OpenAI API
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
      print("Error: OPENAI_API_KEY environment variable not set.")
      sys.exit(1)

    paragraphs = self.get_paragraphs(input_string)
    
    sentence_idx = 0
    for paragraph in paragraphs:
      if paragraph.speaker.strip() != self.config.process_speaker:
        continue

      if len(paragraph.content) < self.config.min_sentence_length:
        continue

      # split paragraph.content into sentences
      input_sentences = self.split_string_to_sentences(paragraph.content)

      for sentence in input_sentences:
        print(f"Processing sentence: {sentence[:50]}...")
        audio_file = f"part_{sentence_idx}.mp3"
        print(f"creating {audio_file}")
        
        speak = self.get_speak_audio(sentence.strip())
        if speak is None:
          print(f"Failed to generate audio for: {sentence[:50]}...")
          continue
          
        with open(self.config.temp_audio_file, "wb") as out:
          out.write(speak)

        self.create_audio_with_silence(audio_file)      
        
        self.review_cards.append(
          ReviewCard(audio_path=audio_file, text=sentence.strip())
        )
        sentence_idx += 1

    if self.review_cards:
      self.create_output_files(suffix, all_movie_file=suffix+"ALL.mp4")
      
      # wait for some time to ensure the video is created
      time.sleep(5)
      
      self.remove_temp_files()
      print(f"Processing complete! Created {len(self.review_cards)} video clips.")
    else:
      print("No review cards were created. Check your input file and speaker configuration.")

if __name__ == "__main__":
  processor = Text2MovieProcessor()
  input_text_file, suffix = processor.process_command_line_args()
  processor.process_text_to_movies(input_text_file, suffix)
