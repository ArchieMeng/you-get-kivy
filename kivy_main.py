import pickle
import subprocess
import traceback
import mimetypes

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.utils import platform
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

if platform == 'android':
    # init android classes
    from jnius import autoclass, cast
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    PythonActivity = autoclass('org.renpy.android.PythonActivity')


def get_file_dir():
    if platform == 'android':
        currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
        return currentActivity.getFilesDir()
    else:
        return '.'


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''


class VideoItem(RecycleDataViewBehavior, BoxLayout):
    # Todo add status indicator
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    video_title = StringProperty()  # used by title label
    video_ext = StringProperty()
    video_url = StringProperty()

    def __init__(self):

        super().__init__()
        # schedule a task to update progress bar
        Clock.schedule_interval(lambda dt: self.set_progress_bar_values(), 1 / 4.)
        self.download_thread = None
        self.download_dir_name = get_file_dir()

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(VideoItem, self).refresh_view_attrs(
            rv, index, data)

    def get_download_info(self):
        if self.download_info:
            return self.download_info
        else:
            self.download_info = {
                'stop': True,
                'received': 0.,
                'total_size': 100.
            }

    def open_video(self):
        # open video with system app
        filePath = os.path.join(self.download_dir_name, self.video_filename)
        if platform == 'android':
            # do android open video file
            intent = Intent(Intent.ACTION_VIEW)
            mimetype = mimetypes.guess_type(filePath)[0]
            intent.setDataAndType(
                Uri.parse(filePath),
                mimetype)
            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivity(intent)
        if sys.platform.startswith('darwin'):
            # OS X
            subprocess.call(('open', filePath))
        elif os.name == 'nt':
            # Windows
            subprocess.call(('start ', filePath))
        elif os.name == 'posix':
            # Linux
            subprocess.call(('xdg-open', filePath))

    @mainthread
    def set_progress_bar_values(self):
        info = self.get_download_info()
        self.ids.video_progress_bar.value = info['received']
        self.ids.video_progress_bar.max = info['total_size']

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(VideoItem, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        # Todo implement resume / pause animation
        # Todo implement video file open operation
        ''' Respond to the selection of items in the view. '''
        ''' Video items on_click function '''
        self.selected = is_selected
        self.video_filename = '.'.join([self.video_title, self.video_ext])
        if is_selected:
            print("select {}:{}".format(self.video_filename, self.download_info))
            # rv.validate_then_download(self.video_url, self.index)
            # change download status pause/resume
            download_info = self.get_download_info()
            # Todo implement download function with popup warning
            if download_info:
                download_info['stop'] = (not download_info['stop'])
                # only one thread running
                if self.download_info['received'] != self.download_info['total_size'] and \
                        not download_info['stop'] and \
                        (self.download_thread is None or not self.download_thread.is_alive()):
                    self.download_thread = Thread(
                        target=download,
                        args=(self.video_url,),
                        kwargs={
                            'download_info': download_info,
                            'output_dir': self.download_dir_name
                        },
                        daemon=True
                    )
                    self.download_thread.start()
                elif self.download_info['received'] == self.download_info['total_size'] or \
                        self.video_filename in os.listdir(self.download_dir_name):
                    self.open_video()


class VideoListView(RecycleView):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)
        self.executing_tasks = set()
        self.download_dir_name = get_file_dir()

    def add_video_item(self, title, ext, url, **kwargs):
        index = len(self.data)
        download_info = kwargs.get(
            'download_info',
            {
                'stop': False,
                'received': 0,
                'total_size': 100
            }
        )
        if 'download_info' in kwargs:
            kwargs.pop('download_info')
        data = {
            'video_title': str(title),
            'video_ext': ext,
            'video_url': str(url),
            'download_info': download_info,
            **kwargs
        }
        print(data)
        self.data.append(data)
        return index

    @mainthread
    def set_video_item(self, idx, title, ext, url, **kwargs):
        # # fix bilibili video title
        # if 'bilibili' in url:
        #     title = fix_bilibili_title(title)

        self.data[idx] = {
            'video_title': str(title),
            'video_ext': ext,
            'video_url': str(url),
            **kwargs
        }
        print(self.data[idx])

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
        download_info = {
            'stop': False,
            'received': 0,
            'total_size': 100
        }
        if isinstance(url, Exception):
            # URL is not legal
            popup = Popup(
                title="Error",
                content=Label(
                    text="exception:{}\t{}happened".format(url.__class__, url),
                    size_hint=(.2, None),
                    multiline=True,
                    font_name="FZQKBYJT"
                ),
                size_hint=(.6, .4)
            )
            traceback.print_exception(type(url), url, url.__traceback__)
            self.set_video_item(data_idx, url, "Failed", url, download_info=download_info)
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
                self.set_video_item(data_idx, title, ext, url, download_info=download_info)
                download_thread = Thread(
                    target=download,
                    args=(url,),
                    kwargs={
                        'download_info': download_info,
                        'output_dir': self.download_dir_name
                    },
                    daemon=True
                )
                download_thread.start()
            else:
                popup = Popup(
                    title="Error",
                    content=Label(
                        text="video url:{} doesn\'t exist".format(url),
                        size_hint=(.2, None),
                        multiline=True,
                        font_name="FZQKBYJT"
                    ),
                    size_hint=(.6, .4)
                )
                self.set_video_item(data_idx, url, "Failed", url, download_info=download_info)
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

        def print_file_path(tb):
            print("app source file", os.path.realpath(__file__), tb)

        Clock.schedule_once(print_file_path)


if __name__ == "__main__":
    YouGetApp().run()