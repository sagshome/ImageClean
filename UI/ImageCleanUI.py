import logging
import os
import sys
from multiprocessing import Process, Value, Queue
import types

from pathlib import Path
from time import sleep  # Hangs head in shame

from kivy.clock import Clock
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from Backend.Cleaner import ImageClean, FileCleaner, FolderCleaner


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]

run_path = Path(Path.home().joinpath(f'.{app_name}'))
os.mkdir(run_path) if not run_path.exists() else None

log_file = run_path.joinpath('logfile')
results_file = run_path.joinpath(f'{app_name}.results')

if results_file.exists():
    FileCleaner.rollover_name(results_file)
RESULTS = open(results_file, "w")

if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

debugging = os.getenv(f'{app_name.upper()}_DEBUG')
logger = logging.getLogger(app_name)

fh = logging.FileHandler(filename=str(log_file))
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

# The App will run in the background,  value and queue are used for some basic info passing
cleaner_app = ImageClean(app_name, restore=True)  # save options over each run
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
    def __init__(self, text, status, callback, **kwargs):
        super(CheckBoxItem, self).__init__(**kwargs)
        self.text = text
        self.selected = status
        self.callback = callback

    def log_hit(self, touch):
        if hasattr(self, 'callback'):
            self.callback(touch)
        else:
            print('touched without callback')


class AddDialog(FloatLayout):

    def __init__(self, load_path=None, **kwargs):
        super(AddDialog, self).__init__(**kwargs)
        self.filechooser.path = load_path if load_path else '/'

    def new(path, filename):
        print(path, filename)

    load = ObjectProperty(None)
    cancel = ObjectProperty(None)
    new = ObjectProperty(new)


class LoadDialog(FloatLayout):

    def __init__(self, load_path=None, rooted=False, **kwargs):
        super(LoadDialog, self).__init__(**kwargs)
        self.filechooser.path = load_path if load_path else '/'
        self.filechooser.rootpath = None if not rooted else load_path

    def new(path, filename):
        print(path, filename)

    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class IgnoreFoldersSelector(BoxLayout):

    def __init__(self, **kwargs):
        super(IgnoreFoldersSelector, self).__init__(**kwargs)
        self._popup = None
        self.text = ''

    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(str(cleaner_app.input_folder), rooted=True, load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="Select a Folder to ignore", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) == 1:
            file = os.path.join(path, filename[0])
            if cleaner_app.add_ignore_folder(Path(file)):
                self.text = f'{self.text}\n{file}'
                Process(target=self.parent.calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()
                self.dismiss_popup()

    def clear(self):
        self.text = ''
        cleaner_app.ignore_folders = []
        Process(target=self.parent.calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()


class SkipFoldersSelector(BoxLayout):

    def __init__(self, **kwargs):
        super(SkipFoldersSelector, self).__init__(**kwargs)
        self._popup = None
        self.text = ''

    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(str(cleaner_app.input_folder), rooted=True, load=self.load, cancel=self.dismiss_popup)
        self.text = ''
        for item in cleaner_app.bad_parents:
            self.text = f'{self.text}\n{item}'
        self._popup = Popup(title="Select folder base to skip definition", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) == 1:
            file = Path(os.path.join(path, filename[0])).name
            if cleaner_app.add_bad_parents(file):
                self.text = f'{self.text}\n{file}'
        self.dismiss_popup()

    def clear(self):
        self.text = ''
        cleaner_app.bad_parents = []


class EnterFolder(TextInput):
    pass


class OutputFolderSelector(BoxLayout):

    def __init__(self, **kwargs):
        super(OutputFolderSelector, self).__init__(**kwargs)
        self._popup = None
        self._popup2 = None
        self.result = str(cleaner_app.output_folder)
        self.path = None
        self.folder = ''
        self.content = None

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

    def show_load(self):
        self.path = cleaner_app.output_folder if cleaner_app.output_folder else cleaner_app.input_folder.parent
        self.content = AddDialog(str(self.path), new=self.new, load=self.load, cancel=self.dismiss_popup)

        self._popup = Popup(title="Select Output Folder", content=self.content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        self.text = os.path.join(path, filename[0])
        cleaner_app.output_folder = Path(self.text)
        Process(target=self.parent.calculate_size, args=(cleaner_app.output_folder, mp_output_count)).start()
        self.dismiss_popup()

    def new(self, path, filename):
        content = EnterFolder(multiline=False, text='', hint_text='<Enter> to select')
        content.bind(on_text_validate=self.on_enter)
        self._popup2 = Popup(title="Folder Name", content=content, size_hint=(0.7, 0.2))
        self._popup2.open()

    def on_enter(self, value):
        if not value.text:
            dismiss_dialog("You must enter a value for the new folder name,   select cancel if you changed your mind")
        if len(self.content.filechooser.selection) == 1:
            new_path = Path(self.content.filechooser.selection[0]).joinpath(value.text)
        else:
            new_path = self.path.joinpath(value.text)

        os.mkdir(new_path) if not new_path.exists() else None
        cleaner_app.output_folder = new_path
        self.text = str(new_path)
        self._popup2.dismiss()
        self._popup.dismiss()


class InputFolderSelector(BoxLayout):

    def __init__(self, **kwargs):
        super(InputFolderSelector, self).__init__(**kwargs)
        self.result = str(cleaner_app.input_folder)
        self.cont = None
        self._popup = None

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

    def show_load(self):
        path_str = str(cleaner_app.input_folder) if cleaner_app.input_folder else str(Path.home())
        content = LoadDialog(path_str, load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="Select Folder", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) == 1:
            self.result = os.path.join(path, filename[0])
            cleaner_app.input_folder = Path(self.result)
            cleaner_app.output_folder = cleaner_app.input_folder.parent
            Process(target=self.parent.calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()
            self.dismiss_popup()


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

        # Update progress bar
        self.progress_bar.value = mp_processed_value.value
        if cleaner_app.recreate:
            mp_output_count.value = mp_processed_value.value

        # Update results text
        new_text = self.progress_text.text
        while not mp_print_queue.empty():
            new_line = f'{mp_print_queue.get()}\n'
            RESULTS.write(new_line)
            new_text = f'{new_text}{new_line}'
        if len(new_text) > self.max_results_size:
            new_text = new_text[len(new_text)-self.max_results_size:]
        self.progress_text.text = new_text

        # We are complete
        if not self.bg_process.is_alive():
            self.exit_button.text = 'Exit'  # Abort -> Exit
            self.parent.calculate_size(cleaner_app.output_folder, mp_output_count)
            self.progress_summary.text = f"Summary:\n\nInput Folder: {cleaner_app.input_folder}\n" \
                                         f"Input File Count: {mp_input_count.value}\n" \
                                         f"Output Folder: {cleaner_app.output_folder}\n" \
                                         f"Output File Count: {mp_output_count.value}"
            self.progress_text.text += f"\n\n\n Full Results can be found in: {RESULTS.name}\n"
            RESULTS.close()
            return False

    def start_application(self):
        # Take up to 30 seconds to see if values are in the background  todo: improve this approach
        count = 0
        while mp_input_count.value == -1 or mp_output_count.value == -1:
            sleep(1)
            count += 1
            if count == 30:
                continue
        self.progress_bar.max = mp_input_count.value
        self.progress_summary.text = f"Summary:\n\nInput Folder: {cleaner_app.input_folder}\n" \
                                     f"Input File Count: {mp_input_count.value}\n" \
                                     f"Output Folder: {cleaner_app.output_folder}\n" \
                                     f"Output File Count: {mp_output_count.value}"

        self.progress_text.text = "Results:\n\n"
        self.bg_process = Process(target=self.run_application)
        self.bg_process.start()

    def run_application(self):

        master = FolderCleaner(cleaner_app.input_folder,
                               parent=None,
                               root_folder=cleaner_app.input_folder,
                               output_folder=cleaner_app.output_folder,
                               no_date_folder=cleaner_app.no_date_path)

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


class MainScreen(BoxLayout):

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)

        self.recreate_selector = CheckBoxItem('Recreate - recreate output folder',
                                              cleaner_app.recreate,
                                              self.check_recreate)
        self.keep_dups_selector = CheckBoxItem('Keep Duplicates - Move Duplicates to a separate folder',
                                               cleaner_app.keep_duplicates,
                                               self.check_keep_dups)
        self.keep_clips_selector = CheckBoxItem('Keep Movie Clips - When a movie clip image (iphone) is found,  '
                                                'preserve the it in a separate folder',
                                                cleaner_app.keep_movie_clips, self.check_keep_clips)
        self.keep_converted_selector = CheckBoxItem('Keep Converted - Converted files are preserved',
                                                    cleaner_app.keep_converted_files,
                                                    self.check_keep_converted)
        self.keep_original_selector = CheckBoxItem('Keep Original - when files are moved (to a differant output path) '
                                                   'keep the originals',
                                                   cleaner_app.keep_original_files,
                                                   self.check_keep_original)

        self.inputs = InputFolderSelector()
        self.outputs = OutputFolderSelector()
        self.extras = IgnoreFoldersSelector()
        self.skip_name = SkipFoldersSelector()

        self.add_widget(self.inputs)
        self.add_widget(self.outputs)
        self.add_widget(self.recreate_selector)
        self.add_widget(self.keep_dups_selector)
        self.add_widget(self.keep_clips_selector)
        self.add_widget(self.keep_converted_selector)
        self.add_widget(self.keep_original_selector)
        self.add_widget(self.extras)
        self.add_widget(self.skip_name)
        self.add_widget(ActionBox())

        self.progress = Progress()

        cleaner_app.print = types.MethodType(self.progress.override_print, cleaner_app)
        cleaner_app.increment_progress = types.MethodType(self.progress.override_progress, cleaner_app)

        self.skip_name.text = ''
        for item in cleaner_app.bad_parents:
            self.skip_name.text = f'{self.skip_name.text}\n{item}'

        self.extras.text = ''
        for item in cleaner_app.ignore_folders:
            self.extras.text = f'{self.extras.text}\n{item}'

        Process(target=self.calculate_size, args=(cleaner_app.input_folder, mp_input_count)).start()
        Process(target=self.calculate_size, args=(cleaner_app.output_folder, mp_output_count)).start()

    def help(self):
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
            else:
                print(f'Ignoring: {base}')
        which.value = value


class ImageCleanApp(App):

    def on_stop(self):
        # The Kivy event loop is about to stop, set a stop signal;
        # otherwise the app window will close, but the Python process will
        # keep running until all secondary threads exit.
        self.root.stop.set()

    def build(self):
        return MainScreen()


if __name__ == '__main__':

    my_app = ImageCleanApp()
    my_app.run()

    #ImageCleanApp().run()
