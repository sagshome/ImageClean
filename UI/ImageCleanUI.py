import logging
import os
import sys
from random import randint
from pathlib import Path
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty
from kivy.vector import Vector
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.factory import Factory
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.popup import Popup

from kivy.uix.button import Button

from Backend.Cleaner import ImageClean, FileCleaner

verbose = False

#screen_manager = ScreenManager()
#screen_manager.add_widget(Screen(name='config'))
#screen_manager.add_widget(Screen(name='processing'))

app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]

log_file = Path.home().joinpath(f'{app_name}.log')
if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

debugging = os.getenv(f'{app_name.upper()}_DEBUG')
logger = logging.getLogger(app_name)

fh = logging.FileHandler(filename=log_file)
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

cleaner_app = ImageClean(app_name)

if debugging:
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(fh_formatter)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)

def my_callback(instance):
    print('Popup', instance, 'is being dismissed but is prevented!')
    return True

def dismiss_dialog(text):

    content = DismissDialog(text)
    _popup = Popup(title="", content=content, size_hint=(0.9, 0.9))
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



class CheckBoxItemLabel(Label):
    def __init__(self, **kwargs):
        super(CheckBoxItemLabel, self).__init__(**kwargs)


class CheckBoxItemCheckBox(CheckBox):
    def __init__(self, **kwargs):
        super(CheckBoxItemCheckBox, self).__init__(**kwargs)


class CheckBoxItem(BoxLayout):
    def __init__(self, text, status, callback, **kwargs):
        super(CheckBoxItem, self).__init__(**kwargs)
        self.text = text
        self.selected = status
        self.callback = callback

    def log_hit(self, touch):
        if self.callback:
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


class SaveDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
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
            cleaner_app.add_ignore_folder(Path(file))
            self.text = f'{self.text}\n{file}'
        self.dismiss_popup()


class SkipFoldersSelector(BoxLayout):

    def __init__(self, **kwargs):
        super(SkipFoldersSelector, self).__init__(**kwargs)
        self._popup = None
        self.text = ''

    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(str(cleaner_app.input_folder), rooted=True, load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="Select folder base to skip definition", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) == 1:
            file = Path(os.path.join(path, filename[0])).name
            cleaner_app.add_bad_parents(file)
            self.text = f'{self.text}\n{file}'
        self.dismiss_popup()


class EnterFolder(TextInput):
    pass



class OutputFolderSelector(BoxLayout):

    def __init__(self, initial=None, **kwargs):
        super(OutputFolderSelector, self).__init__(**kwargs)
        self._popup = None
        self._popup2 = None
        self.text = initial
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

    def __init__(self, continue_config=None, **kwargs):
        super(InputFolderSelector, self).__init__(**kwargs)
        self.text = ''
        self.cont = continue_config
        self._popup = None

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()


    def selected(self, path, filename):
        pass
        #if len(filename) == 1:
        #    self.text = os.path.join(path, filename[0])
        #    cleaner_app.input_folder = Path(self.text)
        #    cleaner_app.output_folder = cleaner_app.input_folder.parent
        #    self.cont(self.text)
        #self.dismiss_popup()

    def show_load(self):
        path_str = str(cleaner_app.input_folder) if cleaner_app.input_folder else str(Path.home())
        content = LoadDialog(path_str, load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="Select Folder", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        if len(filename) == 1:
            self.text = os.path.join(path, filename[0])
            cleaner_app.input_folder = Path(self.text)
            cleaner_app.output_folder = cleaner_app.input_folder.parent
            self.cont(self.text)
        self.dismiss_popup()


class ConfigScreen(Screen):
    def __init__(self, config_directory, **kwargs):
        super(ConfigScreen, self).__init__(**kwargs)

        dismiss_dialog('testing')
        self.settings_dir = config_directory
        self.config_complete = False

        self.screen_root = self.children[0]
        self.paranoid_selector = CheckBoxItem('Paranoid mode - Do not remove anything', False, self.check_paranoid)
        self.verbose_selector = CheckBoxItem('Verbose - keep me in the loop', False, self.check_verbose)
        self.recreate_selector = CheckBoxItem('Recreate - recreate output folder', False, self.check_recreate)
        self.keep_dups_selector = CheckBoxItem('Keep Duplicates - Move Duplicates to a separate folder', False, self.check_keep_dups)
        self.keep_clips_selector = CheckBoxItem('Keep Movie Clips - When a movie clip image (iphone) is found,  preserve the movie clip in a separate folder', False, self.check_keep_clips)
        self.keep_converted_selector = CheckBoxItem('Keep Converted - Converted files are preserved', False, self.check_keep_converted)
        self.keep_original_selector = CheckBoxItem('Keep Original - when files are moved (to a differant output path) keep the originals', False, self.check_keep_original)

        self.inputs = InputFolderSelector(continue_config=self.other)
        self.outputs = OutputFolderSelector(initial='')
        self.extras = IgnoreFoldersSelector()
        self.skip_name = SkipFoldersSelector()

        self.screen_root.add_widget(self.inputs)
        self.screen_root.add_widget(Label(text=''))
        DismissDialog('try this')

    def other(self, text):
        if not self.config_complete:
            self.screen_root.remove_widget(self.screen_root.children[0])
            self.outputs.text = str(cleaner_app.output_folder)
            self.screen_root.add_widget(self.outputs)
            self.screen_root.add_widget(self.paranoid_selector)
            self.screen_root.add_widget(self.verbose_selector)
            self.screen_root.add_widget(self.recreate_selector)
            self.screen_root.add_widget(self.keep_dups_selector)
            self.screen_root.add_widget(self.keep_clips_selector)
            self.screen_root.add_widget(self.keep_converted_selector)
            self.screen_root.add_widget(self.keep_original_selector)
            self.screen_root.add_widget(self.extras)
            self.screen_root.add_widget(self.skip_name)
            self.screen_root.add_widget(Button(text='Go'))
            self.config_complete = True

    def check_paranoid(self, touch):
        cleaner_app.set_paranoid(touch)
        self.keep_dups_selector.selected = touch
        self.keep_clips_selector.selected = touch
        self.keep_converted_selector.selected = touch
        self.keep_original_selector.selected = touch

        print(f'Paranoid mode is turned {touch}!') if cleaner_app.verbose else None

        logger.debug(f'Paranoid is {touch}')

    def check_recreate(self, touch):
        cleaner_app.set_recreate(touch)
        print(f'Recreate mode is turned {touch}!') if cleaner_app.verbose else None
        logger.debug(f'recreate is {touch}')

    def check_keep_dups(self, touch):
        cleaner_app.set_keep_duplicates(touch)
        print(f'Keep duplicate mode is turned {touch}!') if cleaner_app.verbose else None

        logger.debug(f'Duplicate is {touch}')

    def check_keep_clips(self, touch):
        cleaner_app.set_keep_movie_clips(touch)
        print(f'Keep movie clips mode is turned {touch}!') if cleaner_app.verbose else None

        logger.debug(f'Keep Movies is {touch}')

    def check_keep_converted(self, touch):
        cleaner_app.set_keep_converted_files(touch)
        print(f'Keep Converted mode is turned {touch}!') if cleaner_app.verbose else None

        logger.debug(f'Keep Converted is {touch}')

    def check_keep_original(self, touch):
        cleaner_app.set_keep_original_files(touch)
        print(f'Keep Original mode is turned {touch}!') if cleaner_app.verbose else None

        logger.debug(f'Keep original is {touch}')

    def check_verbose(self, touch):
        cleaner_app.verbose = touch
        print('Verbose is turned on!') if cleaner_app.verbose else None
        logger.debug(f'Verbose is {touch}')

    def log_hit(checkbox, value):
        pass


class ProcessingScreen(Screen):
    pass


class ImageCleanApp(App):

    def build(self):
        screen_manager = ScreenManager()
        screen_manager.add_widget(ConfigScreen(self.user_data_dir, name='config'))
        screen_manager.add_widget(ProcessingScreen(name='processing'))
        return screen_manager


#Factory.register('Root', cls=InputSelector)
#Factory.register('LoadDialog', cls=LoadDialog)
#Factory.register('SaveDialog', cls=SaveDialog)

if __name__ == '__main__':

    ImageCleanApp().run()
