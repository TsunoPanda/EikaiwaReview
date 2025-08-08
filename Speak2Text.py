import whisper
import time

def transcribe_audio(file_path, model_size="base"):
    """
    Transcribe audio file to text using Whisper ASR.
    
    Args:
        file_path (str): Path to the audio file.
    
    Returns:
        str: Transcribed text.
    """
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path, language = "en")
    return result['text']

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python Speak2Text.py <audio_file_path> <model_size>")
        print("Example: python Speak2Text.py audio.wav base")
        sys.exit(1)
    
    audio_file_path = sys.argv[1]
    model_size = sys.argv[2]
    if model_size not in ["tiny", "base", "small", "medium", "large"]:
        print("Using 'base' model.")
        model_size = "base"

    try:
        start_time = time.time()  # Start timing
        transcription = transcribe_audio(audio_file_path, model_size)
        end_time = time.time()  # End timing

        with open("transcription.txt", "w", encoding="utf-8") as f:
          f.write(transcription)

        print(f"Elapsed time: {end_time - start_time:.2f} seconds")
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        sys.exit(1)

