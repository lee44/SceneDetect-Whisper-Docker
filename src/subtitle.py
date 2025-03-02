import functools
import logging
import multiprocessing
import os
import sys
from datetime import timedelta
from os.path import splitext

import questionary
import torch
import whisper
from dotenv import load_dotenv
from ffmpeg_progress_yield import FfmpegProgress
from tqdm import tqdm

whisper.torch.load = functools.partial(whisper.torch.load, weights_only=True)
load_dotenv()
torch.cuda.is_available()
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

logger = logging.getLogger("scene_detect_logger")
logger.propagate = False


class SubtitleGenerator:
    def __init__(self, folder: str, video_path: str):
        self.folder = folder
        self.video_path = video_path

    def filter_videos_without_audio(self):
        return list(
            filter(
                lambda filename: splitext(filename)[0] not in [splitext(file)[0] for file in os.listdir(os.path.join(self.video_path, "audio"))]
                and (
                    "-001" in filename
                    or "-002" in filename
                    or "-003" in filename
                    or "-004" in filename
                    or "-005" in filename
                    or "-006" in filename
                    or "-007" in filename
                    or "-008" in filename
                    or "-009" in filename
                    or "-10" in filename
                    or "-11" in filename
                    or "-12" in filename
                    or "-13" in filename
                    or "-14" in filename
                    or "-15" in filename
                    or "-16" in filename
                    or "-17" in filename
                    or "-18" in filename
                    or "-19" in filename
                    or "-20" in filename
                ),
                os.listdir(self.video_path),
            )
        )

    def filter_videos_with_subtitle(self):
        return list(
            filter(
                lambda filename: "-SUB" in filename or ".srt" in filename,
                os.listdir(self.video_path),
            )
        )

    def filter_videos_without_subtitle(self):
        videos_with_subtitles = self.filter_videos_with_subtitle()

        return list(
            filter(
                lambda filename: splitext(filename)[0] not in [splitext(file)[0] for file in videos_with_subtitles],
                os.listdir(self.video_path),
            )
        )

    def convert_video_to_audio_ffmpeg(self, position, video_title: str, video_path: str, output_audio_path: str, lock):
        """
        Converts the video at the given path to an audio file using ffmpeg

        Arguments:
            - position {int} -- Position of the bar in the tqdm progress bar
            - video_title {str} -- Title of the video
            - video_path {str} -- Path of the video file
            - output_audio_path {str} -- Path of the output audio file
            - lock {multiprocessing.Lock} -- Lock used to synchronize the tqdm progress bar
        """
        if os.path.exists(output_audio_path):
            return

        cmd = ["ffmpeg", "-y", "-i", video_path, f"{output_audio_path}"]

        ff = FfmpegProgress(cmd)
        with lock:
            # Create a tqdm progress bar
            bar = tqdm(total=100, position=position + 1, desc=f"{video_title}")

        for progress in ff.run_command_with_progress():
            # Update the progress bar
            with lock:
                bar.update(progress - bar.n)

        # Close the progress bar
        with lock:
            bar.close()

    def get_audio_paths(self) -> list[tuple[str, str, str]]:
        video_transcriber_params = []
        OUTPUT_AUDIO_PATH = os.path.join(self.video_path, "audio")

        audio_files = os.listdir(OUTPUT_AUDIO_PATH)

        # Filter out audio files that already have subtitles
        audio_files = list(
            filter(
                lambda filename: splitext(filename)[0] not in self.filter_videos_with_subtitle(),
                audio_files,
            )
        )

        for audio in audio_files:
            video_title = splitext(audio)[0]
            output_audio_path = os.path.join(OUTPUT_AUDIO_PATH, f"{video_title}.mp3")
            output_srt_path = os.path.join(self.video_path, video_title + ".srt")
            video_transcriber_params.append((video_title, output_audio_path, output_srt_path))

        return video_transcriber_params

    def generate_subtitle(self, video_title: str, output_audio_path: str, output_srt_path: str):
        model_path = "large"
        model = whisper.load_model(model_path, device=DEVICE)

        logger.info(f"\nGenerating Subtitles for {video_title}")
        result = model.transcribe(output_audio_path, verbose=False, language="ja", task="translate")
        segments = result["segments"]

        for seg in segments:
            start = str(0) + str(timedelta(seconds=int(seg["start"]))) + ",000"
            end = str(0) + str(timedelta(seconds=int(seg["end"]))) + ",000"
            text = seg["text"]
            segment_id = seg["id"] + 1
            segment = f"{segment_id}\n{start} --> {end}\n{text[1:] if text[0] == ' ' else text}\n\n"
            with open(output_srt_path, "a", encoding="utf-8") as f:
                f.write(segment)

    def mp_extract_audio(self, cores: str, lock):
        video_transcriber_params = []

        OUTPUT_AUDIO_PATH = os.path.join(self.video_path, "audio")
        if not os.path.exists(OUTPUT_AUDIO_PATH):
            os.makedirs(OUTPUT_AUDIO_PATH, exist_ok=True, mode=0o777)

        videos_without_audio = self.filter_videos_without_audio()
        videos_without_subtitles = self.filter_videos_without_subtitle()

        video_files = list(set(videos_without_audio) & set(videos_without_subtitles))

        for i, video in enumerate(video_files):
            video_title = splitext(video)[0]
            video_path = os.path.join(self.video_path, video)
            output_audio_path = os.path.join(OUTPUT_AUDIO_PATH, f"{video_title}.mp3")
            video_transcriber_params.append((i, video_title, video_path, output_audio_path, lock))

        logger.info(f"Generating {len(video_transcriber_params)} audio files")

        with multiprocessing.Pool(processes=int(cores)) as pool:
            pool.starmap_async(self.convert_video_to_audio_ffmpeg, video_transcriber_params, error_callback=logger.error)
            pool.close()
            pool.join()

    def mp_generate_subtitle(self, cores: str = "1"):
        video_transcriber_params = self.get_audio_paths()

        logger.info(f"Transcribing {len(video_transcriber_params)} videos using {DEVICE}")

        # 2 Max Cores
        # with multiprocessing.Pool(processes=int(cores)) as pool:
        #     pool.starmap_async(self.generate_subtitle, video_transcriber_params, error_callback=logger.error)
        #     pool.close()
        #     pool.join()

        for video_transcriber_param in video_transcriber_params:
            self.generate_subtitle(*video_transcriber_param)
