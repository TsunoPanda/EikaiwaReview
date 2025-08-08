import random
import openai
import sys
import os
import re

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip
import textwrap

def create_movie(text, audio_file, output_file="test_with_audio.mp4"):
  # 画像の作成
  width, height = 640, 480
  img = Image.new('RGB', (width, height), color=(255, 255, 255))
  draw = ImageDraw.Draw(img)
  font_size = 32
  try:
      font = ImageFont.truetype("arial.ttf", font_size)
  except:
      font = ImageFont.load_default()
      font.size = font_size
  
  # insert newline characters every 40 characters
  text = "\n".join([textwrap.fill(line, width=40) for line in text.splitlines()])

  bbox = draw.textbbox((0, 0), text, font=font)
  text_width = bbox[2] - bbox[0]
  text_height = bbox[3] - bbox[1]
  draw.text(
      ((width - text_width) / 2, (height - text_height) / 2),
      text, fill=(0, 0, 0), font=font
  )
  frame = np.array(img)

  audio_clip = AudioFileClip(audio_file)
  duration = audio_clip.duration - 2.0 / 30  # Subtract 2 frames at 30 fps to avoid audio cut-off (noise at the end)

  video_clip = ImageClip(frame).set_duration(duration).set_audio(audio_clip.set_duration(duration))
  video_clip.write_videofile(output_file, fps=30, codec="libx264", audio_codec="aac")
  audio_clip.close()


# read OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

if len(sys.argv) < 2:
    print("Usage: python Text2Speak.py <input_file> <suffix>(optional)")
    sys.exit(1)

input_file = sys.argv[1]
with open(input_file, "r", encoding="utf-8") as f:
    input_string = f.read()

# if sys.argv[2] is provided, append it to the input string
if len(sys.argv) > 2:
    suffix = sys.argv[2]
else:
    suffix = ""

TEMP_AUDIO_FILE = "temp.mp3"
OUTPUT_FOLDER = "output"
TEMP_SILENT_FILE = "silence.mp3"
FINAL_OUTPUT_FILE = suffix+"ALL.mp4"

pairs = []
pattern = re.compile(r'([a-zA-Z\[\]]+):\s*([\s\S]*?)(?=(?:[a-zA-Z\[\]]+:)|\Z)')
for match in pattern.finditer(input_string):
  speaker = match.group(1).strip()
  content = match.group(2).strip()
  pairs.append((speaker, content))


card_list = []
idx = 0

# list of available voices (as per OpenAI documentation)
available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
# select a voice from the list at random
selected_voice = random.choice(available_voices)

for pair in pairs:
  if not "Me" in pair[0]:
    continue
  if len(pair[1]) < 30:
    continue

  # split pair[1] into sentences
  sentences = re.split(r'(?<=[.!?])\s+', pair[1])
  input_sentences = []
  acc_len_sentence = 0
  acc_sentence = ""
  for sentence in sentences:
    # remove leading and trailing whitespace
    sentence = sentence.strip()
    acc_sentence += sentence + " "
    acc_len_sentence += len(sentence)
    if acc_len_sentence > 30:
      input_sentences.append(acc_sentence.strip())
      acc_sentence = ""
      acc_len_sentence = 0
  if acc_sentence:
    input_sentences.append(acc_sentence.strip())

  for sentence in input_sentences:
    filename = f"part_{idx}.mp3"
    
    print(f"creating {filename}")

    speed = 1
    
    response = openai.audio.speech.create(
      model="tts-1",
      voice=selected_voice,
      input=sentence.strip(),
      response_format="mp3",
    )
    with open(TEMP_AUDIO_FILE, "wb") as out:
      out.write(response.content)

    # get the duration of the audio file
    audio_clip = AudioFileClip(TEMP_AUDIO_FILE)
    # 50% longer than the audio duration plus 1 second
    silent_duration = int(audio_clip.duration*1.5 + 1.0)
    audio_clip.close()

    # If TEMP_SILENT_FILE is already exist, this command will overwrite it.
    os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono -t {silent_duration} {TEMP_SILENT_FILE}')

    # 速度調整
    os.system(f'ffmpeg -i {TEMP_AUDIO_FILE} -filter:a "atempo={speed}" -vn {filename}')

    # Add silence at the end of the audio file
    combined_file = f"combined_{filename}"
    with open("concat_list.txt", "w") as f:
        f.write(f"file '{filename}'\n")
        f.write(f"file '{TEMP_SILENT_FILE}'\n")
    os.system(f'ffmpeg -f concat -safe 0 -i concat_list.txt -c copy {combined_file}')
    os.remove("concat_list.txt")
    os.replace(combined_file, filename)
    
    card_list.append([filename, sentence.strip()])

    idx += 1

os.remove(TEMP_SILENT_FILE)

# Create "OUTPUT_FOLDER" if it doesn't exist
if not os.path.exists(OUTPUT_FOLDER):
  #remove the folder if it exists
  if os.path.isdir(OUTPUT_FOLDER):
    import shutil
    shutil.rmtree(OUTPUT_FOLDER)
  os.makedirs(OUTPUT_FOLDER)

out_file_text = os.path.join(OUTPUT_FOLDER, "output_files.txt")

# 既存の出力ファイルリストがあれば追記、なければ新規作成
with open(out_file_text, "a", encoding="utf-8") as f:
  for card in card_list:
    audio_file = card[0]
    text = card[1]
    base_name = audio_file.replace('.mp3', '.mp4')
    output_file = os.path.join(OUTPUT_FOLDER, f"{suffix}{base_name}")
    create_movie(text, audio_file, output_file)
    f.write(f"file '{suffix}{base_name}'\n")
   
# 動画を結合
os.system(f"ffmpeg -f concat -safe 0 -i {out_file_text} -c copy {OUTPUT_FOLDER}/{FINAL_OUTPUT_FILE}")

# wait for some time to ensure the video is created
import time
time.sleep(5)

# 一時ファイル削除
for card in card_list:
  os.remove(card[0])
if os.path.exists(TEMP_SILENT_FILE):
  os.remove(TEMP_SILENT_FILE)
if os.path.exists(out_file_text):
  os.remove(out_file_text)
if os.path.exists(TEMP_AUDIO_FILE):
  os.remove(TEMP_AUDIO_FILE)
