from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty
from kivy.app import App
from kivy.clock import Clock


class Progress(Widget):
    progress_bar = ObjectProperty(None)
    progress_summary = ObjectProperty(None)
    progress_text = ObjectProperty(None)

    def update_progress(self, count):
        print('Count is....:', count)
        # self.progess_bar.value = cleaner_app.progress
        value = self.progress_bar.value
        self.progress_bar.value = value + 100
        print(f'{self.progress_bar.value} out of {self.progress_bar.max}')

    def set_summary(self, kwargs):
        print('kwargs are....:')
        self.progress_summary.text = f"Summary:\n\nInputFolder:1000"
        self.progress_text.text = "Results:\n\n"

    def start_clock(self):
        Clock.schedule_interval(self.update_progress, 2.0)


class PlaygroundApp(App):

    def build(self):
        return Progress()

if __name__ == '__main__':
    my_app = PlaygroundApp()
    my_app.run()
