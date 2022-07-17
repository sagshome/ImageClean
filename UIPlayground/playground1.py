

from kivy.app import App
from kivy.event import EventDispatcher
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.filechooser import FileChooserListView

from kivy.core.window import Window  # You must import this



class BasicWindow(FloatLayout):
    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(BasicWindow, self).__init__(**kwargs)
        Window.size = (400, 600)  # Set it to a tuple with the (width, height) in Pixels
        btn1 = Button(text='Hello')
        btn2 = Button(text='World')
        #self.add_widget(btn1, size_hint=(0.8, 0.1), pos_hint={'left': 0.8, 'top': .8})
        #self.add_widget(btn2)


class CheckItem:
    def __init__(self, label: str):
        self.name = label
        self.label = Label(text=label, halign='left', valign='middle', pos=(0,0), size_hint=(1.0, 1.0))
        self.label.text_size = self.label.size
        self.checkbox = CheckBox()

    def add(self, parent: Widget):
        parent.add_widget(self.label)
        parent.add_widget(self.checkbox)


class ChooserItem:
    def __init__(self, label: str):
        self.name = label
        self.label = Label(text=label)
        self.chooser = CheckBox()

    def add(self, parent: Widget):
        parent.add_widget(self.label)
        parent.add_widget(self.chooser)


class ConfigScreen(Widget):
    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(ConfigScreen, self).__init__(**kwargs)
        pass
        # self.cols = 2
        #self.add_widget(Button(text = 'twop', ))
        #self.add_widget(Label(text = '[b]Hello [color=ccccccc]world[/color][/b]' ))


        '''

        #self.row_force_default = False
        #self.row_default_height = 30
        self.add_widget(Button(text = 'One', pos_hint=(1,1)))
        self.add_widget(Label(text = 'twop',))

        self.add_widget(Label(text = 'Optionally select a different output folder'))

        self.add_widget(Button(text = 'four'))

        self.config_items = [
            ['arg', ChooserItem('Select the Input Folder to process')],
            ['-o', ChooserItem('Optionally select a differant output folder')],
            ['-h', CheckItem('Display help information')],
            ['-s', CheckItem('Save images after conversion')]
        ]
        for key, value in self.config_items:
            value.add(self)
        '''

class MyEventDispatcher(EventDispatcher):
    def __init__(self, **kwargs):
        self.register_event_type('on_test')
        super(MyEventDispatcher, self).__init__(**kwargs)

    def do_something(self, value):
        # when do_something is called, the 'on_test' event will be
        # dispatched with the value
        self.dispatch('on_test', value)

    def on_test(self, *args):
        print("I am dispatched", args)




        return self.root

def my_callback(value, *args):
    print("Hello, I got an event!", args)


class CustomBtn(Widget):

    pressed = ListProperty([0, 0])

    def on_touch_down(self, touch):
        print(*touch.pos)
        print(f'on_touch_down... {touch.pos} my_pos {self.pos} - {self.collide_point(*touch.pos)}')
        if self.collide_point(*touch.pos):
            self.pressed = touch.pos
            return True
        return super(CustomBtn, self).on_touch_down(touch)

    def on_pressed(self, instance, pos):
        print(f'on_pressed... {pos}')

class RootWidget(BoxLayout):

    def __init__(self, **kwargs):
        super(RootWidget, self).__init__(**kwargs)
        self.add_widget(Button(text='btn 1'))
        cb = CustomBtn()
        cb.bind(pressed=self.btn_pressed)
        self.add_widget(cb)
        self.add_widget(Button(text='btn 2'))

    def btn_pressed(self, instance, pos):
        print(f'possss: printed from root widget: {pos}')

class PlayGroundApp(App):
    def build(self):
        return RootWidget()
# self.root = BoxLayout(orientation='vertical')

if __name__ == '__main__':
    #ev = MyEventDispatcher()
    #ev.bind()
    #ev.bind(on_test=my_callback)
    #ev.do_something('bogus')

    PlayGroundApp().run()
