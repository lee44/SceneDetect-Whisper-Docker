import json
import logging
import os
import re
from os.path import splitext
from pathlib import Path

from scenedetect import FrameTimecode, ThresholdDetector, detect, split_video_ffmpeg

logger = logging.getLogger("scene_detect_logger")


class SceneDetect:
    def __init__(self, folder: str, video_path: str):
        self.folder = folder
        self.video_path = video_path

    def split_video_exists(self, video: str) -> bool:
        """
        Check if the split video exists.

        Args:
            video (str): The name of the video file.

        Returns:
            bool: True if the split video exists, False otherwise.
        """

        for existing_video in os.listdir(os.path.join(self.video_path)):
            if ".mp4" in existing_video:
                if (
                    video + "-001.mp4" == existing_video
                    or video + "-002.mp4" == existing_video
                    or video + "-003.mp4" == existing_video
                    or video + "-004.mp4" == existing_video
                    or video + "-005.mp4" == existing_video
                    or video + "-006.mp4" == existing_video
                    or video + "-007.mp4" == existing_video
                    or video + "-008.mp4" == existing_video
                    or video + "-009.mp4" == existing_video
                    or video + "-010.mp4" == existing_video
                ):
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
            # Raise a TypeError if the scene file is not valid
            raise TypeError(f"Timecode format/type unrecognized for scene: {scene_path}\n{e}")

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
            logger.info("Video already split: " + video_path)
            return

        # Skip if video scene exists
        if self.video_scene_exists(video):
            logger.info("Video scene already exists: " + video_path)
            return

        try:
            logger.info("Extracting scenes for: " + video_path)
            scene_list = detect(video_path, detector=ThresholdDetector(), show_progress=True)
            if any(scene[1].get_seconds() - scene[0].get_seconds() > 3600 for scene in scene_list):
                scene_list = detect(video_path, detector=ThresholdDetector(threshold=225, method=1), show_progress=True)

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
            logger.info("Video does not exist: " + video_path)
            return

        video = Path(video_path).stem
        if self.split_video_exists(video):
            logger.info("Split video already exists for: " + video_path)
            return

        scene_list = self.serialize_scenes(scene_path)
        if len(scene_list) == 0:
            logger.info("No Scenes Found For: " + video_path)
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
                suppress_output=None,
                hide_progress=None,
            )

        except Exception as e:
            raise e
