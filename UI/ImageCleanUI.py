import asyncio
import logging
import os
import platform
import sys
from multiprocessing import Process, Value, Queue
import types

from pathlib import Path
from time import sleep  # Hangs head in shame

from kivy.clock import Clock
from kivy.app import App, async_runTouchApp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty, NumericProperty
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from Backend.cleaner import FileCleaner, FolderCleaner
from Backend.image_clean import ImageClean

application_name = 'Cleaner'  # I am hardcoding this value since I call it from cmdline and UI which have diff names

app_path = Path(sys.argv[0])
run_path = Path(Path.home().joinpath(f'.{application_name}'))
os.mkdir(run_path) if not run_path.exists() else None

log_file = run_path.joinpath('logfile')
# results_file = run_path.joinpath(f'{application_name}.results')
#
# if results_file.exists():
#     results_file.unlink()
#     #FileCleaner.rollover_name(results_file)
# RESULTS = open(results_file, "w+")

if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

debugging = os.getenv(f'{application_name.upper()}_DEBUG')
logger = logging.getLogger(application_name)

fh = logging.FileHandler(filename=str(log_file))
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

# The App will run in the background,  value and queue are used for some basic info passing
cleaner_app = ImageClean(application_name, restore=True)  # save options over each run
mp_processed_value = Value("i", 0)
mp_input_count = Value("i", -1)
mp_output_count = Value("i", -1)
mp_print_queue = Queue()

if debugging:
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(fh_formatter)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)

LOOP = asyncio.get_event_loop()


def calculate_size(path, which):
    which.value = -1  # -1 is a test for uninitialized
    value = 0
    for base, dirs, files in os.walk(path):
        if Path(base) not in cleaner_app.ignore_folders:
            for _ in files:
                value += 1
        # else:
        #    print(f'Ignoring: {base}')
    which.value = value


def run_application():
    master = FolderCleaner(cleaner_app.input_folder,
                           parent=None,
                           root_folder=cleaner_app.input_folder,
                           output_folder=cleaner_app.output_folder)

    master.description = None
    cleaner_app.run()
    # root_folder=cleaner_app.no_date_path))
    # suspicious_folders = cleaner_app.audit_folders(cleaner_app.output_folder)
    # if suspicious_folders:
    #     self.override_print('_', 'The following folders where found to contain a large number of files,  '
    #                              'thus they are suspicious\n')
    #     for folder in suspicious_folders:
    #         self.override_print('_', folder)


def dismiss_dialog(title, text):
    content = DismissDialog(text)
    _popup = Popup(title=title, content=content, size_hint=(0.9, 0.9))
    content.popup = _popup
    _popup.open()


class DismissDialog(BoxLayout):

    error_text = StringProperty()

    def __init__(self, message=None, **kwargs):
        super(DismissDialog, self).__init__(**kwargs)
        self.error_text = message
        self.popup = None

    def dismiss(self):
        self.popup.dismiss()


class CheckBoxItem(BoxLayout):
    '''
    Provide a get and set function for each checkbox item
    '''

    def selected(self, checkbox):
        if hasattr(self, 'callback') and self.callback:
            self.callback(checkbox.active)

    @staticmethod
    def set_recreate(touch):
        cleaner_app.set_recreate(touch)
        logger.debug(f'recreate is {touch}')

    @staticmethod
    def set_keep_originals(touch):
        cleaner_app.set_keep_original_files(touch)
        logger.debug(f'keep_originals is {touch}')

    @staticmethod
    def set_keep_others(touch):
        cleaner_app.set_keep_duplicates(touch)
        cleaner_app.set_keep_converted_files(touch)
        cleaner_app.set_keep_movie_clips(touch)
        logger.debug(f'keep_others is {touch}')

    @staticmethod
    def set_process_small(touch):
        #cleaner_app.set_keep_original_files(touch)
        logger.debug(f'process small is {touch}')


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


class ActionBox(BoxLayout):

    def start_processing(self):
        if cleaner_app.recreate:
            mp_output_count.value = 0
        cleaner_app.save_config()
        main = self.parent
        main.clear_widgets()
        main.add_widget(main.progress)
        Clock.schedule_interval(main.progress.update_progress, 1.0)
        main.progress.start_application()


class Progress(Widget):
    progress_bar = ObjectProperty(None)
    progress_summary = ObjectProperty(None)
    progress_text = ObjectProperty(None)
    exit_button = ObjectProperty(None)
    bg_process = None
    max_results_size = 5000

    def update_progress(self, _):
        """
        This will run at a present interval (ActionBox.start_processing) and update the progress bar and the text
        output.  When the child process dies,  update the summary text with useful information.
        :param _:  It is the time since the last clock interval.   Not used
        :return:
        """

        # Update progress bar
        self.progress_bar.value = mp_processed_value.value
        if cleaner_app.recreate:
            mp_output_count.value = mp_processed_value.value

        # Update results text,  we need to truncate since the text box widget can not handle large amounts of data
        # todo: this truncation works but it makes for jumpy text,  maybe we can do better.
        new_text = self.progress_text.text
        while not mp_print_queue.empty():
            new_line = f'{mp_print_queue.get()}\n'
            # RESULTS.write(new_line)  # This is the full output,  just in case.
            new_text = f'{new_text}{new_line}'

        if len(new_text) > self.max_results_size:
            new_text = new_text[len(new_text)-self.max_results_size:]
        self.progress_text.text = new_text

        if not self.bg_process.is_alive():  # We are complete
            self.exit_button.text = 'Exit'  # Change label from Abort to Exit
            self.parent.calculate_size(cleaner_app.output_folder, mp_output_count)
            self.progress_summary.text = f"Summary:\n\nInput Folder: {cleaner_app.input_folder}\n" \
                                         f"Input File Count: {mp_input_count.value}\n" \
                                         f"Output Folder: {cleaner_app.output_folder}\n" \
                                         f"Output File Count: {mp_output_count.value}"

            # self.progress_text.text += f"\n\n\n Full Results can be found in: {RESULTS.name}\n"
            # RESULTS.close()
            return False  # Stops this periodic task

    def start_application(self):
        # Take up to 30 seconds to see if values are in the background  todo: improve this approach
        count = 0
        while mp_input_count.value == -1 or mp_output_count.value == -1:
            sleep(1)
            count += 1
            if count == 30:
                logger.error(f'Input count {mp_input_count.value} Output count {mp_output_count.value} - Error')
                break

        self.progress_bar.max = mp_input_count.value
        self.progress_summary.text = f"Summary:\n\nInput Folder: {cleaner_app.input_folder}\n" \
                                     f"Input File Count: {mp_input_count.value}\n" \
                                     f"Output Folder: {cleaner_app.output_folder}\n" \
                                     f"Output File Count: {mp_output_count.value}"

        self.progress_text.text = "Results:\n\n"
        self.bg_process = Process(target=run_application)
        self.bg_process.start()

    def run_application(self):

        master = FolderCleaner(cleaner_app.input_folder,
                               parent=None,
                               root_folder=cleaner_app.input_folder,
                               output_folder=cleaner_app.output_folder)

        master.description = None
        cleaner_app.prepare()
        cleaner_app.process_folder(master)
        master.reset()
        cleaner_app.process_duplicates_movies(FolderCleaner(cleaner_app.no_date_path,
                                                            root_folder=cleaner_app.no_date_path))
        suspicious_folders = cleaner_app.audit_folders(cleaner_app.output_folder)
        if suspicious_folders:
            self.override_print('_', 'The following folders where found to contain a large number of files,  '
                                     'thus they are suspicious\n')
            for folder in suspicious_folders:
                self.override_print('_', folder)

    def abort(self):
        if self.bg_process and self.bg_process.is_alive():
            self.bg_process.kill()
            self.exit_button.text = 'Exit'
        else:
            exit(0)

    def override_print(self, _, text):
        """
        This method will take print statements from cleaner_app and redirect to this method (which should print into
        a textBox
        :param self:  (me)
        :param _:     (cleaner APP)
        :param text:  (what we want to display)
        :return:
        """
        mp_print_queue.put(text)

    @staticmethod
    def override_progress(_):
        mp_processed_value.value = mp_processed_value.value + 1


class FolderSelector(BoxLayout):
    '''
    Provide a get (for input_label_value) and optionally set/callback function for each checkbox item
    '''

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
        if not value.text:
            dismiss_dialog("You must enter a value for the new folder name,   select cancel if you changed your mind")
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
                           f"This is usually due to a permission problem.    Make sure you actually select a folder\n"
                           f"before you make a new 'child' folder\n")

    # Non Generic Functions

    def get_input(self):
        '''
        Get(ters) should return the label value for the UI and set self.load_base for future load functions
        :return:
        '''
        value = str(cleaner_app.input_folder)
        self.input_label_value = value
        self.load_base = str(cleaner_app.input_folder.parent)
        return value

    def set_input(self, path, filename):
        self.input_label_value = os.path.join(path, filename[0])
        cleaner_app.input_folder = Path(self.input_label_value)
        Process(target=calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()

    def get_output(self):
        value = str(cleaner_app.output_folder)
        self.input_label_value = value
        self.load_base = str(cleaner_app.output_folder.parent)

        return value

    def set_output(self, path, filename):
        self.input_label_value = os.path.join(path, filename[0])
        cleaner_app.output_folder = Path(self.input_label_value)
        Process(target=calculate_size, args=(cleaner_app.output_folder, mp_input_count)).start()

    def get_skip_name(self):
        value = ''
        for entry in cleaner_app.bad_parents:
            value += f'{entry}\n'
        self.input_label_value = value
        self.load_base = str(cleaner_app.input_folder)

        return value

    def clear_skip_name(self):
        cleaner_app.bad_parents = []
        self.input_label_value = self.get_skip_name()

    def set_skip_name(self, path, filename):
        for path_value in filename:
            if path_value != path:
                cleaner_app.bad_parents.append(Path(path_value).name)
        self.input_label_value = self.get_skip_name()

    def clear_ignore_folder(self):
        cleaner_app.ignore_folders = []
        self.input_label_value = self.get_ignore_folder()

    def get_ignore_folder(self):
        value = ''
        for entry in cleaner_app.ignore_folders:
            value += f'{entry}\n'
        self.input_label_value = value
        self.load_base = str(cleaner_app.input_folder)
        return value

    def set_ignore_folder(self, path, filename):
        for path_value in filename:
            if path_value != path:
                cleaner_app.ignore_folders.append(Path(path_value))
        self.input_label_value = self.get_ignore_folder()


class Main(BoxLayout):
    input_selector = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Main, self).__init__(**kwargs)

        self.progress = Progress()

        cleaner_app.print = types.MethodType(self.progress.override_print, cleaner_app)
        cleaner_app.increment_progress = types.MethodType(self.progress.override_progress, cleaner_app)
        Process(target=calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()
        Process(target=calculate_size, args=(cleaner_app.output_folder, mp_output_count)).start()

    def help(self):
        print('foobar')
        dismiss_dialog('Help',
                       f"ImageClean: Organize images based on dates and custom folder names.  The date format is:\n"
                       f"  * Level 1 - Year,  Level 2 - Month,  Level 3 - Date as in 2002/12/5 (December 5th, 2002)\n"
                       f"  * If the original folder had a name like 'Florida',  the new folder would be 2002/Florida\n"
                       f"       This structure should help you find your pictures much easier\n\n"
                       f"Input Folder is where the images will be loaded from\n"
                       f"Output Folder is where they will be stored - it can be the same as Input Folder\n\n"
                       f"Options\n"
                       f"Recreate: The output folder will be replaced \n"
                       f"Keep options - files that would normally be erased after they are relocated, "
                       f"Paranoid sets these.\n"
                       f"Add a folder to Ignore - This allows you to skip sub-folders of the Input Folder\n"
                       f"Add a folder NAME to Ignore - This is used to prevent custom names from being used,  "
                       f"the images\nare still processed, but with the example above 'Florida', would not be used as a"
                       f"custom folder name\n"
                       )

    def about(self):
        dismiss_dialog('About',
                       f"This application is provided as is.\n\n"
                       f"Author: Matthew Sargent\n"
                       f"Support: matthew.sargent61@gmail.com\n\n"
                       #f"Attributions:\n\n"
                       #f"https://www.vecteezy.com/free-vector/buttons - Buttons Vectors by Vecteezy"
                      )

    def check_recreate(self, touch):
        cleaner_app.set_recreate(touch)
        logger.debug(f'recreate is {touch}')

    @staticmethod
    def get_recreate():
        return cleaner_app.recreate

    def check_keep_dups(self, touch):
        cleaner_app.set_keep_duplicates(touch)
        logger.debug(f'Duplicate is {touch}')

    def check_keep_clips(self, touch):
        cleaner_app.set_keep_movie_clips(touch)
        logger.debug(f'Keep Movies is {touch}')

    def check_keep_converted(self, touch):
        cleaner_app.set_keep_converted_files(touch)
        logger.debug(f'Keep Converted is {touch}')

    def check_keep_original(self, touch):
        cleaner_app.set_keep_original_files(touch)
        logger.debug(f'Keep original is {touch}')

    def log_hit(checkbox, value):
        pass

    def exit(self, value):
        print(f'Exit {self} - value is {value}')
        exit(value)

    def calculate_size(self, path, which):
        which.value = -1  # -1 is a test for uninitialized
        value = 0
        for base, dirs, files in os.walk(path):
            if Path(base) not in cleaner_app.ignore_folders:
                for _ in files:
                    value += 1
            #else:
            #    print(f'Ignoring: {base}')
        which.value = value

    def set_input_folder(self):
        return 'a value'


class ImageCleanApp(App):
    external_app = cleaner_app

    def build(self):
        return Main()


if __name__ == '__main__':

    #my_app = ImageCleanApp()
    #LOOP.run_until_complete(
    #    async_runTouchApp(my_app, async_lib='asyncio')
    #)

    my_app = ImageCleanApp()
    my_app.run()
    print('foobar')

    #ImageCleanApp().run()
