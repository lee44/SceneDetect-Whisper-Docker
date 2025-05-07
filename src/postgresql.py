import os
import re
from os.path import splitext

import ffmpeg
import psycopg2
from psycopg2.extras import DictCursor
from tqdm import tqdm

SERVER_PATH = "\\\OLYMPUS\\videos"
DATABASE = "JAV"
HOST = "192.168.1.111"
USER = "postgres"
PASSWORD = "Boxerlee2015!13"
PORT = "5432"


class PostgresSQL:
    def __init__(self):
        self.postgres_connection = self.connect_db()

    def connect_db(self, database=DATABASE, host=HOST, user=USER, password=PASSWORD, port=PORT, cursor_factory=DictCursor):
        try:
            return psycopg2.connect(database=database, host=host, user=user, password=password, port=port, cursor_factory=cursor_factory)
        except (Exception, psycopg2.DatabaseError):
            print("Server Connection Failed")

            return None

    # Helper functions
    def extract_video_resolution(self, video_path: str) -> tuple:
        """
        Extracts the video resolution from the video file.

        Args:
            video_path (str): The path to the video file.

        Returns:
            tuple: A tuple containing the width and height of the video resolution.
        """
        video_streams = ffmpeg.probe(video_path, select_streams="v")

        return video_streams["streams"][0]["width"], video_streams["streams"][0]["height"]

    def extract_video_code(self, video: str):
        """
        Extract the video code, excluding -RM, -SUB, and trailing -001, -002, etc from the video filename.

        Args:
            video (str): The name of the video file.

        Returns:
            str: The extracted video code.
        """
        # Remove the '.mp4' extension from the video name
        video = video.replace(".mp4", "")

        # Split the video name into parts using '-' as the delimiter
        video_name_split = video.split("-")

        # Check the length of the video name split
        if len(video_name_split) == 4:
            # If the length is 4, remove the last part of the video name
            video = video[: video.rfind("-")]
        elif len(video_name_split) == 3:
            # If the length is 3, check if the video name contains '-SUB' or '-RM'
            if "-SUB" not in video and "-RM" not in video:
                # If it does not contain '-SUB' or '-RM', remove the last part of the video name
                video = video[: video.rfind("-")]

        # Return the extracted video code after removing leading and trailing whitespace
        return video.replace("-RM", "").replace("-SUB", "").strip()

    def has_subtitles_uncensored(self, video: str):
        """
        Check if the video has subtitles or uncensored.

        Args:
            video (str): The name of the video file.

        Returns:
            tuple: A tuple containing the subtitles status (bool) and uncensored status (bool).
        """
        # Initialize the subtitles and uncensored status as False
        subtitles = False
        uncensored = False

        # Check if the video contains '-SUB'
        if "-SUB" in video:
            # If it does, set the subtitles status to True
            subtitles = True
        # Check if the video contains '-RM'
        elif "-RM" in video:
            # If it does, set the uncensored status to True
            uncensored = True

        # Return the subtitles and uncensored status as a tuple
        return subtitles, uncensored

    def is_video_split(self, video: str):
        pattern = r"-0\d{2}"

        return bool(re.search(pattern, video))

    def is_video_deleted(self, actor: str, video: str):
        videos = self.find_all(actor)
        for vid in videos:
            if video == vid["video_code"]:
                return False

        return True

    # Database I/O Functions
    def find(self, video_code: str):
        sql = """SELECT * FROM videos WHERE video_code = %s"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (video_code,))

            return cursor.fetchall()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def find_all(self, actor: str):
        sql = """SELECT * FROM videos WHERE actress = %s"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (actor,))

            return cursor.fetchall()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def delete(self, video_code: str):
        sql = """DELETE FROM videos WHERE video_code = %s"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (video_code,))
            self.postgres_connection.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def update(self, video_info: dict):
        sql = "UPDATE videos SET "
        for key, property in video_info.items():
            if key == "video_code":
                continue

            sql += f"{key} = %({key})s, "

        sql = sql[:-2]
        sql += " WHERE video_code = %(video_code)s"

        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, video_info)
            self.postgres_connection.commit()

            print(f"Updated {video_info['video_code']}")
        except (Exception, psycopg2.DatabaseError) as error:
            print("Error updating data: %s" % error)

    def upsert(self, video_info: dict):
        """
        Upsert the video information into the videos table.

        Args:
            video_info (dict): A dictionary containing the video information.
        """
        sql = """INSERT INTO videos (actress, video_code, subtitles, uncensored, width, height, opened, video_split, subtitle_created) VALUES (%(actress)s, %(video_code)s, %(subtitles)s, %(uncensored)s, %(width)s, %(height)s, %(opened)s, %(video_split)s, %(subtitle_created)s) ON CONFLICT (video_code) DO UPDATE SET subtitles = %(subtitles)s, uncensored = %(uncensored)s, width = %(width)s, height = %(height)s, opened = %(opened)s, video_split = %(video_split)s, subtitle_created = %(subtitle_created)s"""

        try:
            # execute the SQL query
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, video_info)
            # commit the changes to the database
            self.postgres_connection.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            # if an error occurs, rollback the changes
            print("Error inserting/updating data: %s" % error)
            self.postgres_connection.rollback()

    # Database Sync Functions
    def update_video_resolutions(self, actor: str):
        """
        Updates the video resolutions in the PostgreSQL database.

        Args:
            actor (str): The name of the actor.
        """
        for video in os.listdir(os.path.join(SERVER_PATH, actor)):
            if video.endswith(".mp4"):
                video_code = self.extract_video_code(video)

                try:
                    width, height = self.extract_video_resolution(os.path.join(SERVER_PATH, actor, video))
                except Exception:
                    continue

                print(f"{video_code}: {width} x {height}")

                # Update the video information in the PostgreSQL database
                self.update(
                    {
                        "video_code": video_code,
                        "width": width,
                        "height": height,
                    }
                )

    def sync_database(self):
        """
        Sync database with actor's videos.
        """

        video_code_set = set()
        for actor in tqdm(os.listdir("actors"), desc="Actors", position=0, colour="green", leave=True):
            actor_dir = list(filter(lambda video: video.endswith(".mp4"), os.listdir(os.path.join(SERVER_PATH, actor))))
            for video in tqdm(actor_dir, desc=f"Syncing {actor}", position=1, colour="red", leave=False):
                video_code = self.extract_video_code(video)

                if video_code in video_code_set:
                    continue

                video_code_set.add(video_code)

                subtitles, uncensored = self.has_subtitles_uncensored(video)
                try:
                    width, height = self.extract_video_resolution(os.path.join(SERVER_PATH, actor, video))
                except Exception:
                    width, height = None, None
                    continue

                video_info = {
                    "actress": actor,
                    "video_code": video_code,
                    "subtitles": subtitles,
                    "uncensored": uncensored,
                    "width": width,
                    "height": height,
                    "opened": True,
                    "video_split": self.is_video_split(video),
                    "subtitle_created": True if splitext(video)[0] + ".srt" in actor_dir else False,
                    "deleted": self.is_video_deleted(actor, video_code),
                }

                # print(video_info)

                try:
                    self.upsert(video_info)
                    # print(f"Upserted: {video_code}")
                except Exception:
                    print(f"Failed to Upsert: {video_code}")
                    continue


if __name__ == "__main__":
    postgres = PostgresSQL()
    postgres.sync_database()
