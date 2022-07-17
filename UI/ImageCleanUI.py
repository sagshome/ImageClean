from random import randint

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty
from kivy.vector import Vector
from kivy.clock import Clock

from kivy.uix.button import Button

from Backend.image_clean import *

verbose = False

screen_manager = ScreenManager()
screen_manager.add_widget(Screen(name='config'))
screen_manager.add_widget(Screen(name='processing'))

class CheckBoxItemLabel(Label):
    def __init__(self, **kwargs):
        super(CheckBoxItemLabel, self).__init__(**kwargs)

        pass

class CheckBoxItemCheckBox(CheckBox):
    def __init__(self, **kwargs):
        super(CheckBoxItemCheckBox, self).__init__(**kwargs)
        pass


class CheckBoxItem(BoxLayout):
    def __init__(self, text, status, callback, **kwargs):
        super(CheckBoxItem, self).__init__(**kwargs)
        self.text = text
        self.selected = status
        self.callback = callback

    def log_hit(self, touch):
        print('hit touch')
        if self.callback:
            self.callback(touch)
        else:
            print('touched without callback')

class ConfigScreen(Screen):

    def __init__(self, **kwargs):
        super(ConfigScreen, self).__init__(**kwargs)

        self.screen_root = self.children[0]
        self.paranoid_selector = CheckBoxItem('Paranoid mode - Do not remove anything', False, self.check_paranoid)
        self.verbose_selector = CheckBoxItem('Verbose - keep me in the loop', True, self.verbose)
        #row1 = BoxLayout(orientation='horizontal', size_hint=(1.0, 0.1))
        #row1.add_widget(CheckBoxItemLabel('Paranoid mode - Do not remove anything'))
        #row1.add_widget(CheckBox(active=False, size_hint=(0.1, 1.0), pos_hint={'right': 1, 'top': 1}))
        self.screen_root.add_widget(self.paranoid_selector)
        self.screen_root.add_widget(self.verbose_selector)

        self.screen_root.add_widget(Button(text='Foo'))
        self.screen_root.add_widget(Button(text='nst'))

    def check_paranoid(self, touch):
        logger.debug(f'Paranoid is {touch}')

    def check_verbose(self, touch):
        verbose = True if touch else False
        logger.debug(f'Verbose is {touch}')

    def log_hit(checkbox, value):
        if value:
            print('Touched')
        else:
            print('Chill')


class ProcessingScreen(Screen):
    pass


class ImageCleanApp(App):

    def build(self):
        screen_manager = ScreenManager()
        screen_manager.add_widget(ConfigScreen(name='config'))
        screen_manager.add_widget(ProcessingScreen(name='processing'))
        return screen_manager



if __name__ == '__main__':
    ImageCleanApp().run()
