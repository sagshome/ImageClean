from pathlib import Path
from datetime import datetime
import asyncio

class ImageClean:
    def __init__(self, app: str, restore=False, **kwargs):
        self.app_name = app
        self.ignore_folders = []
        self.input_folder = Path('E:\\')
        self.output_folder = Path.home()
        self.progress = 0


    def print(self, text):
        """
        This is really only here so that I can override it in the GUI.
           cleaner_app.print = types.MethodType(self.progress.override_print, cleaner_app)

        :param text: something to display when verbose is true
        :return:  None
        """
        if self.verbose:
            print(text)

    def increment_progress(self):
        """
        Simple way to update progress / used in GUI
        :return:
        """
        self.progress += 1


    async def run(self):
        while True:
            await asyncio.sleep(1)
            self.print(f'One Cycle - {datetime.now()}')
            self.increment_progress()
            pass

    def save_config(self):
        return

