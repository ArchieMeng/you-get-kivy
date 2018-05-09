import pickle
import traceback

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.properties import BooleanProperty, StringProperty, ObjectProperty
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from videos_fetcher import *


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''


class VideoItem(RecycleDataViewBehavior, BoxLayout):
    # Todo update progress bar info
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    video_title = StringProperty()  # used by title label
    video_ext = StringProperty()
    video_url = StringProperty()
    video_list = ObjectProperty()
    data_item = ObjectProperty()
    download_info = ObjectProperty({
                    'stop': False,
                    'received': 0,
                    'total_size': 100
                })

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(VideoItem, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(VideoItem, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        # Todo implement resume / pause function
        ''' Respond to the selection of items in the view. '''
        ''' Video items on_click function '''
        self.selected = is_selected
        if is_selected:
            print("select {0}".format(rv.data[index]))
            # rv.validate_then_download(self.video_url, self.index)
            # change download status pause/resume
            if self.download_info:
                self.download_info['stop'] = self.download_info['stop'] if self.download_info['stop'] else True
                if not self.download_info['stop']:
                    download_thread = Thread(
                        target=download,
                        args=(self.video_url,),
                        kwargs={'download_info': self.download_info},
                        daemon=True
                    )
                    download_thread.start()


class VideoListView(RecycleView):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)
        self.executing_tasks = set()

    def add_video_item(self, title, ext, url, **kwargs):
        index = len(self.data)
        data = {
            'video_title': str(title),
            'video_ext': ext,
            'video_url': str(url),
            **kwargs
        }
        print(data)
        data['data_item'] = data
        self.data.append(data)
        return index

    @mainthread
    def set_video_item(self, idx, title, ext, url, **kwargs):
        self.data[idx] = {
            'video_title': str(title),
            'video_ext': ext,
            'video_url': str(url),
            **kwargs
        }
        print(self.data[idx])
        self.data[idx]['data_item'] = self.data[idx]

    @mainthread
    def remove_video_item(self, idx):
        del self.data[idx]

    def validate_then_download(self, url, data_idx):
        """
        Threading function of validate url.
        if validated, then download it.
        :param data_idx: corresponding video_item data index
        :param url: url to validate and download
        :return:
        """
        url = validate_url(url)
        if isinstance(url, Exception):
            # URL is not legal
            popup = Popup(
                title="Error",
                content=Label(
                    text="exception:{}\t{}happened".format(url.__class__, url),
                    size_hint=(.4, None)
                ),
                size_hint=(.6, .4)
            )
            traceback.print_exception(type(url), url, url.__traceback__)
            self.set_video_item(data_idx, url, "Failed", url)
            Clock.schedule_once(
                popup.open,
                0
            )
        else:
            # URL is legal, start download
            info = get_info(url)
            if info:
                title, ext = info['title'], info['ext']
                print("add video", title)
                # Todo update progress bar with download info
                download_info = {
                    'stop': False,
                    'received': 0,
                    'total_size': 100
                }
                self.set_video_item(data_idx, title, ext, url, download_info=download_info)
                download_thread = Thread(
                    target=download,
                    args=(url,),
                    kwargs={'download_info': download_info},
                    daemon=True
                )
                download_thread.start()
            else:
                popup = Popup(
                    title="Error",
                    content=Label(
                        text="video url:{} doesn\'t exist".format(url),
                        size_hint=(.4, None)
                    ),
                    size_hint=(.6, .4)
                )
                self.set_video_item(data_idx, url, "Failed", url)
                Clock.schedule_once(
                    popup.open,
                    0
                )

    def add_video(self, url):
        # implement video download and video validate function with gui
        if url:
            for video_info in self.data:
                if url == video_info['video_url']:
                    return
            if url not in self.executing_tasks:
                idx = self.add_video_item(url, "validating", url)
                self.executing_tasks.add(url)
                Thread(
                    target=self.validate_then_download, args=(url, idx)
                ).start()


class YouGetWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class YouGetApp(App):
    def build(self):
        self.youget_widget = YouGetWidget()
        self.video_list = self.youget_widget.ids['video_list']
        return self.youget_widget

    def on_stop(self):
        # save application data at here
        if self.video_list.data:
            with open('video_list.pickle', 'wb') as fp:
                pickle.dump(list(self.video_list.data), fp)
            # stop all downloading threads
            for data in self.video_list.data:
                # Todo fix not download_info error in data
                if 'download_info' in data:
                    data['download_info']['stop'] = True

    def on_start(self):
        # restore application data at here
        try:
            with open('video_list.pickle', 'rb') as fp:
                video_list = pickle.load(fp)
                self.video_list.data.extend(video_list)
        except FileNotFoundError:
            # bypass file not found
            pass


if __name__ == "__main__":
    YouGetApp().run()