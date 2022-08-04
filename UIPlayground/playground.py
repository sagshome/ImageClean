from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang.builder import Builder

kv = """
<OtherClass>:
    root_widget: 'Root Widget Property - From KV code'
    BoxLayout:
        orientation: 'vertical'
        parent_widget: "Button's Parent Widget Property (BoxLayout in KV Code)"
        Label:
            text: "Object References"
        Button:
            text: str(root.parent)
        Button:
            text: str(app)
        Button:
            text: str(root)
        Button:
            text: str(root.children)
        Button:
            text: str(self)
        Button:
            text: str(self.children)
        Label:
            text: "Property References"
        Button:
            text: app.main_app_class
        Button:
            text: app.root
        Button:
            text: root.other_class_property
        Button:
            text: root.root_widget
        Button:
            text: self.parent.parent_widget
        Button:
            self_widget: 'Self Widget Property (Button in KV Code)'
            text: self.self_widget
        Button:
            text: str(self.children[0].child_label_widget)
            Label:
                child_label_widget: "Button's Child Widget Property (Label in KV Code)"   
"""

Builder.load_string(kv)


class OtherClass(BoxLayout):
    other_class_property = 'Other Class Property - From Python Code'


class Main(App):
    main_app_class = 'Main App Class Property - From Python Code'

    def build(self):
        # Have to specify self.root otherwise it doesn't exist
        self.root = "Main App Class Root"
        return OtherClass()


Main().run()
