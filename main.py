import os
import shutil
import re

from lib.handel_email import send_mail

from bs4 import BeautifulSoup
import requests
import codecs
import py7zr
import numpy as np
import click

from datetime import datetime
from dateutil import tz


def cvt_datasize(data_size, data_unit_from, data_unit_to, use_1024=True):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    cvt_s = 1000 if not use_1024 else 1024
    try:
        from_idx = units.index(data_unit_from)
        to_idx = units.index(data_unit_to)
    except ValueError:
        raise ValueError(f"One of the given units {[data_unit_from, data_unit_to]} are not implemented ({units}).")

    diff = from_idx - to_idx
    cvt_diff = cvt_s ** diff
    cvt_size = data_size * cvt_diff
    return cvt_size


url = 'https://www.dr.dk/nyheder'
news_item_class_name = "hydra-latest-news-page__short-news-item"
time_class_name = "dre-teaser-meta-label"
heading_class_name = "dre-title-text"
body_class_name = [
    {"name": "div", "attrs": {"class": "hydra-latest-news-page-short-news-article__body", "itemprop": "articleBody"}},
    {"name": "p", "attrs": {"class": "hydra-latest-news-page-short-news-card__summary"}}
]
file_out = "news.txt"
encoding = "utf-8"

last_headline_file = "last.txt"

compres_filters = {
    "LZMA2_Delta": [{'id': py7zr.FILTER_DELTA}, {'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT}],
    "LZMA2_BCJ": [{'id': py7zr.FILTER_X86}, {'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT}],
    "LZMA2_ARM": [{'id': py7zr.FILTER_ARM}, {'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT}],
    "LZMA_BCJ": [{'id': py7zr.FILTER_X86}, {'id': py7zr.FILTER_LZMA}],
    "LZMA2": [{'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT}],
    "LZMA": [{'id': py7zr.FILTER_LZMA}],
    "BZip2": [{'id': py7zr.FILTER_BZIP2}],
    "Deflate": [{'id': py7zr.FILTER_DEFLATE}],
    "ZStandard": [{'id': py7zr.FILTER_ZSTD, 'level': 3}],
    "PPMd0": [{'id': py7zr.FILTER_PPMD, 'order': 6, 'mem': 16}],
    "PPMd1": [{'id': py7zr.FILTER_PPMD, 'order': 6, 'mem': 32}],
    "PPMd2": [{'id': py7zr.FILTER_PPMD, 'order': 6, 'mem': 24}],
    "PPMd3": [{'id': py7zr.FILTER_PPMD, 'order': 3, 'mem': 24}],
    "PPMd4": [{'id': py7zr.FILTER_PPMD, 'order': 12, 'mem': 24}],
    "PPMd5": [{'id': py7zr.FILTER_PPMD, 'order': 24, 'mem': 24}],
    "PPMd6": [{'id': py7zr.FILTER_PPMD, 'order': 48, 'mem': 24}],
    "PPMd7": [{'id': py7zr.FILTER_PPMD, 'order': 12, 'mem': 32}],
    "Brolti": [{'id': py7zr.FILTER_BROTLI, 'level': 11}],
    "7zAES_LZMA2_Delta": [{'id': py7zr.FILTER_DELTA}, {'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT},
                          {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}],
    "7zAES_LZMA2_BCJ": [{'id': py7zr.FILTER_X86}, {'id': py7zr.FILTER_LZMA2, 'preset': py7zr.PRESET_DEFAULT},
                        {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}],
    "7zAES_LZMA": [{'id': py7zr.FILTER_LZMA}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}],
    "7zAES_Deflate": [{'id': py7zr.FILTER_DEFLATE}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}],
    "7zAES_BZip2": [{'id': py7zr.FILTER_BZIP2}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}],
    "7zAES_ZStandard": [{'id': py7zr.FILTER_ZSTD}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}]
}


def insert_newlines(s, n=64):
    if n == -1:
        return s
    string_list = []
    last_space = -1
    current_string = ""
    s = s.replace("\n", " ")
    for i, c in enumerate(s):
        current_string += c
        if c == " ":
            last_space = i
        if len(current_string) >= n:
            if last_space != -1:
                diff = i - last_space
                if diff != 0:
                    string_list.append(current_string[:-diff])
                    current_string = current_string[-diff:]
                else:
                    string_list.append(current_string)
                    current_string = ""
            else:
                string_list.append(current_string[:-1] + "-")
                current_string = current_string[-1]

            last_space = -1
    if current_string != "":
        string_list.append(current_string)
    return "\n".join(string_list)


def load_last_heading(file, encoding):
    last_headline = None
    if os.path.exists(file):
        last_headline = codecs.open(last_headline_file, "r", encoding).read()
    return last_headline


def write_heading(file, heading, encoding):
    with codecs.open(file, "w", encoding) as fp:
        fp.write(heading)


def remove_foto(target_str):
    res_str = re.sub(r"\(Foto.+\)", "", target_str)
    return res_str


def remove_link(s):
    s = s.replace("/ritzau/", "")
    s = s.replace("/Ritzau/", "")
    s = s.replace("FacebookTwitterKopier Link", "")
    return s


def add_space(s):
    c_space = ["."]

    ensure_space = False
    s_out = ""
    for c in s:
        if c in c_space:
            ensure_space = True
        elif ensure_space:
            ensure_space = False
            if c != " ":
                s_out += " "
        s_out += c
    return s_out


def handle_body(s):
    s = remove_foto(s)
    s = remove_link(s)

    s = add_space(s)
    return s


@click.command()
@click.option('--to_mail', required=True, type=str, help='email to send the news to')
@click.option('--server_username', required=True, type=str,
              help='the username for the smtp_ssl server. If using gmail then use the mail you want to send from')
@click.option('--server_password', required=True, type=str,
              help='the password for the smtp_ssl server. '
                   'If using gmail you need a app password: https://myaccount.google.com/apppasswords')
@click.option('--smtp_ssl', default='smtp.gmail.com',
              help="The stmp ssl server to send the email with. If using google the stmp ssl server is: smtp.gmail.com")
@click.option('--from_str', default="DR News Compressed Service",
              help="The text there shoud be used in the \"From:\" field on the mail")
@click.option('--subject_str', default="DR News compressed", help="What the subject field on the mail should be")
@click.option('-o', '--only_new', default=True,
              help="If 1 then only new news are send. "
                   "This is based on the last news heading there has previse been sent")
@click.option('-c', '--char_per_line', default=-1, help="The number of chars per line in the news.txt file. "
                                                        "If set to -1 there is no limit")
@click.option('-s', '--sep_char', default="-", help="The separator used between each news")
@click.option('-m', '--send', default=True, help="If 1 the mail will be sent")
@click.option('-e', '--end_date', default="FFFFFFFF", help="The date for when to stop sending news in format YYYYMMDD. "
                                                           "If set to FFFFFFFF no end date")
@click.option('-e', '--max_bytes', default="100KB", help="The max size of the compressed news in bytes. "
                                                         "More than the given size the news will not be sent")
@click.option('-d', '--debug', is_flag=True, help="If set in debug mode the first call will save a html "
                                                  "with the current news and all later calls will use this "
                                                  "html file instead of fetching new news")
def main(only_new, char_per_line, sep_char, from_str, subject_str, to_mail,
         server_username, server_password, smtp_ssl, send, end_date, max_bytes, debug):
    """Scraps https://www.dr.dk/nyheder for news, rewrite the news in size aware format and send a compressed version to the given email
    7zip can then be used to open the compressed file there contains a news.txt file
    """
    print("Script running at:", datetime.now().isoformat())
    sep_length = char_per_line
    if sep_length == -1:
        sep_length = 60
    sep_string = sep_char * sep_length

    if isinstance(max_bytes, str):
        old_format = max_bytes
        format_size = ""
        format_unit = ""
        for i, c in enumerate(max_bytes):
            if c.isnumeric() or c == ".":
                format_size += c
            else:
                format_unit = max_bytes[i:]
                format_size = float(format_size)
                break
        format_unit = format_unit.upper()
        max_bytes = cvt_datasize(format_size, format_unit, "B", use_1024=False)
        print(f"Max size is set to {max_bytes} bytes from {old_format} argument")

    if end_date != "FFFFFFFF":
        end_date_dt = datetime.strptime(end_date, '%Y%m%d')
        current_day = datetime.now()
        if current_day >= end_date_dt:
            print("Current day is later than end day")
            exit()

    if debug:
        print("Running in debug mode. This will not use updated new!!!")
    if only_new:
        print("Only new news will be used. This is based on heading of the news so a duplet of a "
              "heading will course unseen news to not be used")
    compress_folder = "compress"
    if os.path.exists(compress_folder):
        shutil.rmtree(compress_folder)
    os.makedirs(compress_folder)

    debug_html_file = "debug_dr_nyheder.html"
    if debug and os.path.exists(debug_html_file):
        html = open(debug_html_file).read()
    else:
        web_request = requests.get(url)
        html = web_request.text
        if debug:
            with open(debug_html_file, "w") as fp:
                fp.write(html)

    last_headline = load_last_heading(last_headline_file, encoding)

    soup = BeautifulSoup(html, 'html.parser')
    news_to_save = []

    news_list = soup.find_all("li", {"class": news_item_class_name})
    for i, news in enumerate(news_list):
        time_elements = news.findChildren("span", {"class": time_class_name})
        time_text = "Unknown time"
        for time_el in time_elements:
            if "dre-teaser-meta-label--primary" in time_el.attrs["class"]:
                continue
            time_text = time_el.text

        heading_el = news.findChild("span", {"class": heading_class_name})
        heading_text = heading_el.text

        if i == 0:
            write_heading(last_headline_file, heading_text, encoding)

        if only_new and last_headline is not None and heading_text == last_headline:
            break

        body_text = ""
        for body_class_name_sub in body_class_name:
            body_el = news.findChild(**body_class_name_sub)
            if body_el is not None:
                break
        if body_el is not None:
            body_text = body_el.text

        if body_text is not None:
            body_text = handle_body(body_text)

            news_to_save.append([time_text, heading_text, body_text])
    if len(news_to_save):
        print(f"New news was found. ({len(news_to_save)})")
        with codecs.open(file_out, "w", encoding) as fp:
            timestamp = str(datetime.now(tz=tz.tzlocal()))
            fp.write(f"Nyheder fra DR: {timestamp}\n{sep_string}\n")
            for i, (time, heading, body) in enumerate(news_to_save):
                save_text = ""
                save_text += insert_newlines(f"{time}: {heading}\n", char_per_line)
                if body != "":
                    save_text += "\n"
                    if char_per_line != -1:
                        save_text += "\n"
                    save_text += insert_newlines(body, char_per_line) + "\n"
                elif char_per_line != -1:
                    save_text += "\n"
                save_text += f"{sep_string}\n"
                fp.write(save_text)

        files = []
        file_sizes = []
        for filters_name in compres_filters:
            filters = compres_filters[filters_name]
            file_name = os.path.join(compress_folder, filters_name + '_news.7z')
            try:
                with py7zr.SevenZipFile(file_name, 'w', filters=filters) as z:
                    z.write(file_out)
            except:
                pass
            else:
                file_size = os.path.getsize(file_name)
                print("Success:", filters_name, "with a size of", file_size, "bytes")
                file_sizes.append(file_size)
                files.append(file_name)

        min_size_file_idx = np.argmin(file_sizes)
        best_file = files[min_size_file_idx]
        compresse_size = file_sizes[min_size_file_idx]
        print("The best compressing method was:", os.path.basename(best_file),
              "with a size of ", compresse_size, "bytes")

        if send and compresse_size <= max_bytes:
            # Send email with file
            print(f"Sending mail to {to_mail}")
            send_mail(from_str, to_mail, server_username, server_password, subject_str,
                      body="News from DR nyheder. Uncompress with 7zip",
                      file_attachments=[best_file], smtp_ssl=smtp_ssl)
        elif compresse_size > max_bytes:
            print(f"The compressed new was to big! "
                  f"The max byte size if {max_bytes} while the file was {compresse_size}")
    else:
        print("No new news was found.")


if __name__ == '__main__':
    main()
