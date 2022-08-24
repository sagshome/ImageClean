from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, BooleanProperty
from kivy.app import App
from kivy.clock import Clock

import os
from pathlib import Path


class DataClass:
    def __init__(self):
        self.input = '/home/msargent'
        self.output = '/shared/pout'
        self.ignore = []
        self.skip = []
        self.checked = False


data = DataClass()


class CheckBoxItem(BoxLayout):
    '''
    Provide a get and set function for each checkbox item
    '''

    def selected(self, checkbox):
        if hasattr(self, 'callback') and self.callback:
            self.callback(checkbox.active)

    def get_buddy(self):
        self.value = True
        return self.value

    def get_sam(self):
        self.value = False
        return self.value

    def set_buddy(self, value):
        print(f'Set Buddy {value}')

    def set_sam(self, value):
        print(f'Set sam {value}')


class GenericFolderSelector(BoxLayout):
    '''
    Provide a get (for input_label_value) and optionally set/callback function for each checkbox item
    '''

    input_label_value = StringProperty('')
    show_new_button = NumericProperty(1)
    load_callback = ObjectProperty(None)
    allow_multiselect = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(GenericFolderSelector, self).__init__(**kwargs)
        self._popup = None
        self._popup2 = None
        self.content = None
        self.input_label_value = ''

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(str(Path(self.input_label_value).parent),
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
        self.content = EnterFolder(multiline=False, text='', hint_text='<Enter> to select')
        self.content.bind(on_text_validate=self.on_enter)
        self._popup2 = Popup(title="Folder Name", content=self.content, size_hint=(0.7, 0.2))
        self._popup2.open()

    def on_enter(self, value):
        if not value.text:
            dismiss_dialog("You must enter a value for the new folder name,   select cancel if you changed your mind")
        if len(self.content.filechooser.selection) == 1:
            new_path = Path(self.content.filechooser.selection[0]).joinpath(value.text)
        else:
            new_path = self.path.joinpath(value.text)

        try:
            os.mkdir(new_path) if not new_path.exists() else None
            data.output_folder = new_path
            self.output_result.text = str(new_path)
            self._popup2.dismiss()
        except PermissionError:
            dismiss_dialog('New Folder Error',
                           f"We are unable to create the new folder {new_path}. \n\n"
                           f"This is usually due to a permission problem.    Make sure you actually select a folder\n"
                           f"before you make a new 'child' folder\n")

    def get_input(self):
        value = data.input if data.input else '/home'
        self.input_label_value = value
        return value

    def get_output(self):
        value = data.output if data.output else '/home'
        self.input_label_value = value
        return value

    def get_ignore(self):
        value = ''
        for entry in data.ignore:
            value += f'{entry}\n'
        self.input_label_value = value
        return value

    def set_ignore(self, path, filename):
        for path_value in filename:
            data.ignore.append(Path(path_value).name)
        value = ''
        for entry in data.ignore:
            value += f'{entry}\n'
        self.input_label_value = value


class EnterFolder(TextInput):
    pass

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


class Main(BoxLayout):
    pass


class PlaygroundApp(App):

    def build(self):
        return Main()


if __name__ == '__main__':
    my_app = PlaygroundApp()
    my_app.run()
