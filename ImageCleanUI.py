"""
UI for cleaning images
"""
import asyncio
import logging
import os
import platform
import platformdirs
import sys
import types

from multiprocessing import Value, Queue
from pathlib import Path
from datetime import datetime

os.environ["KIVY_NO_CONSOLELOG"] = "1"


# pylint: disable=wrong-import-position, missing-function-docstring

from kivy.config import Config
Config.set('graphics', 'resizable', False)

from kivy.clock import Clock
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty, NumericProperty
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.core.window import Window

sys.path.append('.') # required to satisfy imports of backend
from backend.cleaner import FileCleaner, Folder, APPLICATION, AUTHOR, VERSION  # pylint: disable=import-error
from ImageClean import ImageClean  # pylint: disable=import-error

if platform.system() == 'Windows':
    import win32timezone

Window.size = (1000, 600)

user_data_dir = Path(platformdirs.user_data_dir(APPLICATION, AUTHOR, VERSION))
user_data_dir.mkdir(parents=True, exist_ok=True)
config_data_dir = Path(platformdirs.user_config_dir(APPLICATION, AUTHOR, VERSION))
config_data_dir.mkdir(parents=True, exist_ok=True)
log_data_dir = Path(platformdirs.user_log_dir(APPLICATION, AUTHOR, VERSION))
log_data_dir.mkdir(parents=True, exist_ok=True)

run_path = user_data_dir
conf_file = config_data_dir.joinpath('config.pickle')
log_file = log_data_dir.joinpath(f'{APPLICATION}.log')

if not run_path.exists():
    os.mkdir(run_path)

if log_file.exists() and os.stat(log_file).st_size > 100000:  # pragma: no cover
    FileCleaner.rollover_file(log_file)

results_file = run_path.joinpath(f'{APPLICATION}.results')

if results_file.exists():
    results_file.unlink()
    FileCleaner.rollover_file(results_file)

RESULTS = open(results_file, "w+")  # pylint: disable=consider-using-with

if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_file(log_file)

debugging = os.getenv(f'{APPLICATION.upper()}_DEBUG')
logger = logging.getLogger(APPLICATION)

fh = logging.FileHandler(filename=str(log_file))
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)


# The App will run in the background,  value and queue are used for some basic info passing
cleaner_app = ImageClean(restore=True, parallel=True)  # save options over each run
mp_processed_value = Value("i", 0)
mp_input_count = Value("i", -1)
mp_output_count = Value("i", -1)
mp_print_queue = Queue()

input_count_task: asyncio.Task
output_count_task: asyncio.Task

if debugging:
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(fh_formatter)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)

logger.debug('Debugging is live')


def get_drives() -> dict:
    """
    On Windows systems return any drives,  this is not needed on Unix since we can navigate around from /
    :return:
    """
    drives = {}
    if platform.system() == 'Windows':
        import win32api  # pylint: disable=import-outside-toplevel

        for letter in [i for i in win32api.GetLogicalDriveStrings().split('\x00') if i]:
            data = win32api.GetVolumeInformation(f'{letter}\\')
            drives[letter] = data[0] if data[0] else 'Local Disk'
    return drives


def calculate_size(path, which):
    from datetime import datetime
    which.value = -1  # -1 is a test for uninitialized
    value = 0
    for base, dirs, files in os.walk(path):
        if not Folder.is_internal(Path(base)):
        # if Path(base) not in cleaner_app.ignore_folders:
            for _ in files:
                value += 1
    which.value = value


async def a_calculate_size(path: Path, which: Value):
    from datetime import datetime
    print(f'{datetime.now()} Starting calculation on: {path}')
    which.value = -1  # -1 is a test for uninitialized
    value = 0
    for base, dirs, files in os.walk(path):
        if Path(base) not in cleaner_app.ignore_folders:
            for _ in files:
                await asyncio.sleep(0)
                value += 1
    which.value = value
    print(f'{datetime.now()} {path}: {which.value}')


async def update_label(path: Path, which):
    from datetime import datetime
    print(f'{datetime.now()} Starting calculation on: {path}')
    value = 0
    for base, dirs, files in os.walk(path):
        if Path(base) not in cleaner_app.ignore_folders:
            for _ in files:
                await asyncio.sleep(0)
                value += 1
    which += f' ({value})'
    print(f'{datetime.now()} {path}: {which.value}')


async def run_application():
    #master = Folder(cleaner_app.input_folder,
    #                       parent=None,
    #                       root_folder=cleaner_app.input_folder,
    #                       output_folder=cleaner_app.output_folder)

    #master.description = None
    await cleaner_app.run()

    # root_folder=cleaner_app.no_date_path
    # suspicious_folders = cleaner_app.audit_folders(cleaner_app.output_folder)
    # if suspicious_folders:
    #     self.override_print('_', 'The following folders where found to contain a large number of files,  '
    #                              'thus they are suspicious\n'
    #     for folder in suspicious_folders:
    #         self.override_print('_', folder)


def dismiss_dialog(title, text):
    content = DismissDialog(text)
    _popup = Popup(title=title, content=content, size_hint=(0.9, 0.9))
    content.popup = _popup
    _popup.open()


def remove_widget_by_class(parent: Widget, class_name: str):
    """
    Can not re-add a widget using an ID,  so this is used to remove base on class name.
    :param parent:  Parent Widget
    :param class_name:  String for the class name
    :return:
    """
    for child in parent.children:
        if child.__class__.__name__ == class_name:
            parent.remove_widget(child)
            break
    return


class DismissDialog(BoxLayout):

    error_text = StringProperty()

    def __init__(self, message=None, **kwargs):
        super().__init__(**kwargs)
        self.error_text = message
        self.popup = None

    def dismiss(self):
        self.popup.dismiss()


class CheckBoxItem(BoxLayout):
    """
    Provide a get and set function for each checkbox item
    """

    def selected(self, checkbox):
        if hasattr(self, 'callback') and self.callback:
            self.callback(checkbox.active)

    @staticmethod
    def set_keep_originals(touch):
        cleaner_app.keep_original_files = touch

    @staticmethod
    def value_keep_originals():
        return cleaner_app.keep_original_files

    @staticmethod
    def set_process_small(touch):
        cleaner_app.check_for_small = touch

    @staticmethod
    def value_process_small():
        return cleaner_app.check_for_small

    @staticmethod
    def set_do_convert(touch):
        cleaner_app.convert = touch

    @staticmethod
    def value_do_convert():
        return cleaner_app.convert

    @staticmethod
    def set_check_folders(touch):
        cleaner_app.check_for_folders = touch

    @staticmethod
    def value_set_folders():
        return cleaner_app.check_for_folders


class Options(BoxLayout):
    pass


class RadioBoxItem(BoxLayout):
    """
    A group of mutually exclusive options

    """

    def __init__(self, text, check_value, callback, **kwargs):
        super(RadioBoxItem, self).__init__(**kwargs)
        self.ids['RB_Label'].text = text
        self.ids['RB_CheckBox'].active = check_value
        self.ids['RB_CheckBox'].on_active = callback
        self.callback = callback

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if not self.ids['RB_CheckBox'].active:
                self.ids['RB_CheckBox'].active = True
                if self.callback:
                    self.callback(self.ids["RB_Label"].text, True)


class LoadDialog(FloatLayout):
    def __init__(self, load_path=None, rooted=False, visible=1, multiselect=False, **kwargs):
        super(LoadDialog, self).__init__(**kwargs)
        self.filechooser.path = load_path if load_path else '/'
        self.filechooser.rootpath = None if not rooted else load_path
        self.filechooser.multiselect = multiselect
        self.newbutton.opacity = visible

    load = ObjectProperty(None)
    cancel = ObjectProperty(None)
    new = ObjectProperty(None)


class EnterFolder(TextInput):
    pass


class ButtonBox(FloatLayout):
    pass


class ActionBox(FloatLayout):

    def start_processing(self):
        cleaner_app.save_config()
        progress = Progress()
        self.parent.add_widget(progress)
        self.parent.add_widget(ButtonBox())
        progress.start_application()

        remove_widget_by_class(self.parent, 'Options')
        remove_widget_by_class(self.parent, 'ActionBox')
        pass


class ExitBox(FloatLayout):

    def restart(self):

        root = self.parent
        remove_widget_by_class(root, 'Progress')
        remove_widget_by_class(root, 'ExitBox')
        root.add_widget(Options())
        root.add_widget(ActionBox())


class Progress(BoxLayout):
    progress_bar = ObjectProperty(None)
    progress_summary = ObjectProperty(None)
    progress_text = ObjectProperty(None)
    bg_process = None
    max_results_size = 5000
    task = None
    updates = None

    def update_progress(self, _):
        """
        This will run at a present interval (ActionBox.start_processing) and update the progress bar and the text
        output.  When the child process dies,  update the summary text with useful information.
        :param: _:  It is the time since the last clock interval.   Not used
        :return:
        """
        # Update progress bar
        self.progress_bar.value = mp_processed_value.value

        # Update results text,  we need to truncate since the text box widget can not handle large amounts of data
        # todo: this truncation works but it makes for jumpy text,  maybe we can do better.
        new_text = self.progress_text.text
        while not mp_print_queue.empty():
            new_line = f'{mp_print_queue.get()}\n'
            RESULTS.write(new_line)  # This is the full output,  just in case.
            new_text = f'{new_text}{new_line}'

        if len(new_text) > self.max_results_size:
            new_text = new_text[len(new_text)-self.max_results_size:]
        self.progress_text.text = new_text

        if self.task and self.task.done():
            if self.task.exception():
                logger.error(self.task.exception())
            self.updates.cancel()
            calculate_size(cleaner_app.output_folder, mp_output_count)
            self.progress_text.text += f"Summary:\n\nInput Folder: {cleaner_app.input_folder} " \
                                       f"Input File Count: {mp_input_count.value}\n" \
                                       f"Output Folder: {cleaner_app.output_folder} " \
                                       f"Output File Count: {mp_output_count.value}"

            self.progress_text.text += f"\n\n\n Full Results can be found in: {RESULTS.name}\n"
            self.parent.remove_widget(self.parent.children[0])
            self.parent.add_widget(ExitBox())

    def start_application(self):

        cleaner_app.print = types.MethodType(self.override_print, cleaner_app)
        cleaner_app.increment_progress = types.MethodType(self.override_progress, cleaner_app)

        calculate_size(cleaner_app.input_folder, mp_input_count)
        calculate_size(cleaner_app.output_folder, mp_output_count)

        self.progress_bar.max = mp_input_count.value
        self.progress_text.text = "Results:\n\n"
        self.task = asyncio.create_task(run_application())
        self.updates = Clock.schedule_interval(self.update_progress, 1.0)

    def abort(self):
        if self.task and not self.task.done():
            self.task.cancel('Aborted')
        sys.exit(0)

    def override_print(self, _, text):
        """
        This method will take print statements from cleaner_app and redirect to this method (which should print into
        a textBox
        :param self:  (me)
        :param _:     (cleaner APP)
        :param text:  (what we want to display)
        :return:
        """
        if text:  # Don't bother printing empty lines of text
            mp_print_queue.put(f'{datetime.now()}:{text}')

    @staticmethod
    def override_progress(_):
        mp_processed_value.value = mp_processed_value.value + 1


class FolderSelector(BoxLayout):
    """
    Provide a get (for input_label_value) and optionally set/callback function for each checkbox item
    """

    input_label_value = StringProperty('')
    show_new_button = NumericProperty(1)
    load_callback = ObjectProperty(None)
    allow_multiselect = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(FolderSelector, self).__init__(**kwargs)
        self.new_base = None
        self._popup = None
        self._popup2 = None
        self.content = None
        self.input_label_value = ''
        self.load_base = '/'
        self.drives = get_drives()

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(self.load_base,
                             load=self.load, new=self.new, cancel=self.dismiss_popup,
                             visible=self.show_new_button, multiselect=self.allow_multiselect)
        self._popup = Popup(title="Select Folder", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) >= 1:
            if self.load_callback:
                self.load_callback(path, filename)
            else:
                self.input_label_value = os.path.join(path, filename[0])
            self.dismiss_popup()

    def new(self, path, filename):
        self.new_base = filename[0] if len(filename) == 1 else path
        self.content = EnterFolder(multiline=False, text='', hint_text='<Enter> to select')
        self.content.bind(on_text_validate=self.on_enter)
        self._popup2 = Popup(title="Folder Name", content=self.content, size_hint=(0.7, 0.2))
        self._popup2.open()

    def on_enter(self, value):
        new_path = None
        if not value.text:
            dismiss_dialog("Value Missing",
                           "You must enter a value for the new folder name,   select cancel if you changed your mind")
        else:
            new_path = Path(self.new_base).joinpath(value.text)

            try:
                os.mkdir(new_path) if not new_path.exists() else None
                cleaner_app.output_folder = Path(new_path)
                self.input_label_value = str(new_path)
                self._popup2.dismiss()
                self._popup.dismiss()
            except PermissionError:
                dismiss_dialog('New Folder Error',
                               f"We are unable to create the new folder {new_path}. \n\n"
                               f"This is usually due to a permission problem.  Make sure you actually select a folder\n"
                               f"before you make a new 'child' folder\n")

    def have_drives(self):
        if len(self.drives) < 2:
            return 0
        return 1

    def changed_drive(self, value, selected):
        self.load_base = Path(value).parts[0]
        self.input_label_value = value
        self._popup2.dismiss()

    def change_drives(self):
        if not platform.system() == 'Windows':
            return
        self.content = BoxLayout(orientation='vertical')
        base = Path(self.input_label_value).parts[0]
        for drive in self.drives:
            self.content.add_widget(
                RadioBoxItem(text=f'{drive}{self.drives[drive]}',
                             check_value=(drive == base),
                             callback=self.changed_drive)
            )

        self.content.bind(on_text_validate=self.on_enter)
        self._popup2 = Popup(title="Select Drive", content=self.content, size_hint=(0.7, 0.5))
        self._popup2.open()

    def get_input(self):
        """
        Getters should return the label value for the UI and set self.load_base for future load functions
        :return:
        """
        value = cleaner_app.input_folder if cleaner_app.input_folder else Path.home()
        self.input_label_value = str(value)
        self.load_base = str(value.parent)
        return str(value)

    def set_input(self, path, filename):
        self.input_label_value = os.path.join(path, filename[0])
        cleaner_app.input_folder = Path(self.input_label_value)
        asyncio.get_event_loop().create_task(a_calculate_size(cleaner_app.input_folder, mp_input_count))

    def get_output(self):
        value = cleaner_app.output_folder if cleaner_app.output_folder else Path.home()
        self.input_label_value = str(value)
        self.load_base = str(value.parent)
        return str(value)

    def set_output(self, path, filename):
        self.input_label_value = os.path.join(path, filename[0])
        cleaner_app.output_folder = Path(self.input_label_value)
        asyncio.get_event_loop().create_task(a_calculate_size(cleaner_app.output_folder, mp_output_count))


class Main(FloatLayout):
    # input_selector = ObjectProperty(None)

    input_task = ObjectProperty()
    output_task = ObjectProperty()

    # def __init__(self, **kwargs):
    #    super(Main, self).__init__(**kwargs)
    #     pass

    @staticmethod
    def help():
        dismiss_dialog(
            'Help',
            "\nPhoto Manager: Organize images based on dates and custom folder names.  The date format is:\n\n"
            "  * Level 1 - Year,  Level 2 - Month as in 2002/12 (December 5th, 2002)\n"
            "    Times are based off of 1) a existing directory with date values, 2) internal image time, 3) file time stamp\n"
            "  * If the original folder had a name like 'Florida',  the new folder would be 2002/12/Florida\n\n"
            "This structure should help you find your images much easier\n\n"
            "'Import Images From' is where the images will be loaded from\n"
            "'Save Images To' is where they will be stored - it can be the same as the From folder\n\n"
            "Options\n\n"
            "Keep Originals:        If selected no changes to Import From,  usually files are copied and deleted. \n"
            "Look for Thumbnails:   Isolate images that are very small (Often created by other importing software)\n"
            "Convert HEIC files:    Look for this format and if found convert to JPEG (HIEC are not displayed on Windows devices\n"
            "Preserve Folders:      On Image Import, check for descriptive folders. If not selected all files are store by date only\n"
        )

    @staticmethod
    def about():
        dismiss_dialog('About',
                       "This application is provided as is.\n\n"
                       "Author: Matthew Sargent\n"
                       "Support: matthew.sargent61@gmail.com\n\n")

    def check_keep_original(self, touch):
        """
        Selected when you want to not remove original files
        :param touch: set or cleared
        :return:
        """
        cleaner_app.set_keep_original_files(touch)
        logger.debug('Keep original is %s', touch)

    def log_hit(checkbox, value):
        pass

    def exit(self, value):
        """
        Leave the program
        :param value:  Exit return code (abort vs quit)
        :return:
        """
        sys.exit(value)


class PhotoManagerApp(App):
    """
    Main App
    """
    drives = []

    def build(self):
        return Main()

    def app_func(self):
        """
        This will run both methods asynchronously and then block until they
        are finished
        """
        # self.other_task = asyncio.ensure_future(self.waste_time_freely())

        async def run_wrapper():
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib='asyncio')
        return asyncio.gather(run_wrapper())


if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    loop.run_until_complete(PhotoManagerApp().app_func())
    loop.close()
