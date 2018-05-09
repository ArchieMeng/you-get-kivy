import os
import re
import sys
from threading import Thread
from time import sleep

_srcdir = '%s/you-get/src/' % os.path.dirname(os.path.realpath(__file__))
_filepath = os.path.dirname(sys.argv[0])
sys.path.insert(1, os.path.join(_filepath, _srcdir))

import you_get.common as you_get


def get_info(url):
    result = None
    try:
        result = you_get.any_download(
            url,
            json_output=True
        )
    except Exception as e:
        print(type(e), e)
    return result


def download(url, **kwargs):
    info = get_info(url)
    if isinstance(info, dict):
        you_get.download_main(
            you_get.any_download,
            you_get.any_download_playlist,
            urls=[url],
            playlist=False,
            output_dir='.',
            merge=True,
            **kwargs
        )
    else:
        return info


def validate_url(url):
    """
    test whether the given url is a video url or not
    :param url: url to test
    :return: url if true, Exception if false
    """
    try:
        _, true_url = you_get.url_to_module(url)
    except Exception as e:
        return e
    return true_url


def fix_bilibili_title(title):
    return re.sub(r'<.*?>', "", title)


def test_validate(url):
    print("result of url", validate_url(url))


if __name__ == "__main__":
    valid_url = "http://www.bilibili.com/video/av22632738"
    # error_url = "http://bilibili.com/video/av14092"
    # wrong_url = "fdjkajfakjha"
    # test_validate(valid_url)
    # test_validate(wrong_url)
    # test_validate(error_url)
    # print(get_info(error_url))
    download_info = {'stop': False}
    thread = Thread(target=download, args=(valid_url,), kwargs={'download_info': download_info}, daemon=True)
    thread.start()
    i = 0
    while thread.is_alive() and i < 15:
        print("download_info:", download_info)
        sleep(1)
        i += 1
    download_info['stop'] = True
    # info = get_info(url)
    # print(info)
    # filename, ext = info['title'], info['ext']
    # try:
    #     download(url)
    # except OSError as e:
    #     # handle filename too long exception
    #     if str(e.strerror) == "File name too long":
    #         download(url, output_filename="测试")
    # with open('.'.join((filename, ext)), 'rb') as fp:
    #     fp.seek(0, 2)
    #     print(fp.tell())