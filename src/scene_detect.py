import json
import logging
import os
import re
import time
from os.path import splitext
from pathlib import Path

from scenedetect import FrameTimecode, SceneManager, ThresholdDetector, detect, open_video, split_video_ffmpeg

logger = logging.getLogger("scene_detect_logger")


class SceneDetect:
    def __init__(self, folder: str, video_path: str):
        self.folder = folder
        self.video_path = video_path

    def is_file_downloading(self, filepath: str, interval=10, checks=3):
        if not os.path.exists(filepath):
            return False

        last_size = os.path.getsize(filepath)
        for _ in range(checks):
            time.sleep(interval)
            current_size = os.path.getsize(filepath)

            if current_size != last_size:
                return True  # File size changed, likely downloading

            last_size = current_size

        return False  # File size stable, likely finished

    def split_video_exists(self, video: str) -> bool:
        """
        Check if the split video exists.

        Args:
            video (str): The name of the video file.

        Returns:
            bool: True if the split video exists, False otherwise.
        """

        for existing_video in os.listdir(os.path.join(self.video_path)):
            if not existing_video.endswith(".mp4"):
                continue

            if re.match(r".*-\d{0,3}\.mp4", video):
                if "-RM" in video or "-SUB" in video:
                    return True

                if video.count("-") > 1:
                    return True

        return False

    def video_scene_exists(self, video: str) -> bool:
        """
        Check if the video scene file exists

        Arguments:
            video (str): The name of the video file.

        Returns:
            bool -- True if the scene file exists, False otherwise
        """

        for scenes in os.listdir(os.path.join(self.video_path, "scenes")):
            if splitext(video)[0] == splitext(scenes)[0]:
                return True

        return False

    def serialize_scenes(self, scene_path: str) -> list[tuple[FrameTimecode, FrameTimecode]]:
        """
        Serialize scenes from a video file.

        Args:
            scene_path (str): The path of the scene file.

        Returns:
            list: A list of tuples representing the start and end timecodes of each scene.
        """

        # Read the scene file and convert it to a list of tuples
        try:
            with open(scene_path, "r") as infile:
                json_object = json.load(infile)

                # Filter out scenes that are less than 2 minutes long
                scenes = []
                for scene_object in json_object:
                    if scene_object["end"]["seconds"] - scene_object["start"]["seconds"] > (2 * 60):
                        scenes.append(
                            (
                                FrameTimecode(
                                    timecode=scene_object["start"]["timecode"],
                                    fps=scene_object.get("framerate", 30.00),
                                ),
                                FrameTimecode(
                                    timecode=scene_object["end"]["timecode"],
                                    fps=scene_object.get("framerate", 30.00),
                                ),
                            )
                        )
        except Exception as e:
            raise e

        return scenes

    def save_scene_list(self, scene_name: str, scene_list: list[tuple[FrameTimecode, FrameTimecode]]):
        """
        Save the scene list as a JSON file.

        Args:
            scene_name (str): Name of the scene.
            scene_list (List[Tuple[FrameTimecode, FrameTimecode]]): A list of tuples representing the start and end timecodes of each scene.

        Returns:
            None
        """

        serializable_scene_list = []
        for scene in scene_list:
            if scene[1].get_seconds() - scene[0].get_seconds() > (2 * 60):
                serializable_scene_list.append(
                    {
                        "start": {
                            "timecode": scene[0].get_timecode(),
                            "seconds": scene[0].get_seconds(),
                            "frames": scene[0].get_frames(),
                            "framerate": scene[0].get_framerate(),
                        },
                        "end": {
                            "timecode": scene[1].get_timecode(),
                            "seconds": scene[1].get_seconds(),
                            "frames": scene[1].get_frames(),
                            "framerate": scene[1].get_framerate(),
                        },
                    }
                )

        SCENES_PATH = os.path.join(self.video_path, "scenes")

        logger.info("Saving scene list for: " + os.path.join(SCENES_PATH, scene_name) + ".json")

        with open(os.path.join(SCENES_PATH, scene_name) + ".json", "w+") as outfile:
            json.dump(serializable_scene_list, outfile)

        os.chmod(os.path.join(SCENES_PATH, scene_name) + ".json", 0o777)

    def extract_scenes(self, video: str):
        """
        Extracts video scenes from the given video file.

        Args:
            video (str): The name of the video file.
            minutes (int, optional): The minimum duration of scenes in minutes.

        Returns:
            list[tuple[FrameTimecode, FrameTimecode]]: A list of tuples representing the start and end timecodes of each scene.
        """
        video_path = os.path.join(self.video_path, video)

        # Skip split videos
        if re.match(r".*-\d{0,3}\.mp4", video):
            if "-RM" in video or "-SUB" in video:
                # logger.info("Video already split: " + video_path)
                return

            if video.count("-") > 1:
                # logger.info("Video already split: " + video_path)
                return

        # Skip if video scene exists
        if self.video_scene_exists(video):
            # logger.info("Video scene already exists: " + video_path)
            return

        if self.is_file_downloading(video_path):
            logger.info(f"File {video_path} is still downloading.")

            return

        try:
            logger.info("Extracting scenes for: " + video_path)

            # A low threshold (e.g., 12) is common for black cuts.
            # Pixel intensity is 0-255, so 12 is near black.
            BLACK_THRESHOLD = 12
            # A high threshold (e.g., 240) is for white cuts.
            # 240 is near white (255 is pure white).
            WHITE_THRESHOLD = 240
            # Minimum length of a scene in frames (e.g., 15 frames at 30 FPS = 0.5s)
            MIN_SCENE_LEN = 15

            # --- Processing ---
            # Open the video to get FrameTimecode objects
            video = open_video(video_path)
            scene_manager = SceneManager()

            # --- 1. Detector for Black Cuts/Fades ---
            # `ThresholdDetector.Method.FLOOR` detects when the average intensity
            # falls below the threshold (i.e., cuts/fades to black).
            black_detector = ThresholdDetector(threshold=BLACK_THRESHOLD, min_scene_len=MIN_SCENE_LEN, method=ThresholdDetector.Method.FLOOR)
            scene_manager.add_detector(black_detector)

            # --- 2. Detector for White Cuts/Fades ---
            # `ThresholdDetector.Method.CEILING` detects when the average intensity
            # rises above the threshold (i.e., cuts/fades to white).
            white_detector = ThresholdDetector(threshold=WHITE_THRESHOLD, min_scene_len=MIN_SCENE_LEN, method=ThresholdDetector.Method.CEILING)
            scene_manager.add_detector(white_detector)

            # Process the video
            scene_manager.detect_scenes(video, show_progress=True)

            # Get the list of scenes (start and end FrameTimecode tuples)
            scene_list = scene_manager.get_scene_list()

            path = Path(video_path)
            self.save_scene_list(path.stem, scene_list)

        except Exception as e:
            logger.info(e)

    def split_scenes(self, scene_path: str, video_path: str):
        """
        Split scenes from a video file.

        Args:
            scene_path (str): The path of the scene file.
            video_path (str): The path of the video file.

        Returns:
            None
        """

        if not os.path.exists(video_path):
            # logger.info("Video does not exist: " + video_path)
            raise Exception(f"{video_path} does not exist")

        video = Path(video_path).stem
        if self.split_video_exists(video):
            # logger.info("Split video already exists for: " + video_path)
            # raise Exception(f"{video_path} has already been split")
            return

        if self.is_file_downloading(video_path):
            logger.info(f"File {video_path} is still downloading.")

        scene_list = self.serialize_scenes(scene_path)
        if len(scene_list) == 0:
            # logger.info("No Scenes Found For: " + video_path)
            os.rename(video_path, os.path.join(self.video_path, video + "-001.mp4"))

        try:
            logger.info("Splitting videos for: " + video_path)

            split_video_ffmpeg(
                input_video_path=video_path,
                scene_list=scene_list,
                output_dir=os.path.join(self.video_path),
                output_file_template="$VIDEO_NAME-$SCENE_NUMBER.mp4",
                video_name=Path(video_path).stem,
                arg_override="-c:v h264_nvenc -preset slow -cq 18 -rc:v vbr -maxrate 5M -bufsize 10M -g 48 -r 30",
                show_progress=True,
                show_output=False,
            )

            logger.info("Splitting Video Completed")

        except Exception as e:
            raise e
