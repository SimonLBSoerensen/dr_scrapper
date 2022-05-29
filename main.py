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

url = 'https://www.dr.dk/nyheder'
news_item_class_name = "hydra-latest-news-page__short-news-item"
time_class_name = "hydra-latest-news-page-short-news__meta"
heading_class_name = "hydra-latest-news-page-short-news__heading"
body_class_name = "hydra-latest-news-page-short-news__body"
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
@click.option('-c', '--char_per_line', default=64, help="The number of chars per line in the news.txt file")
@click.option('-s', '--sep_char', default="-", help="The separator used between each news")
@click.option('-m', '--send', default=True, help="If 1 the mail will be sent")
@click.option('-d', '--debug', is_flag=True, help="If set in debug mode the first call will save a html "
                                                  "with the current news and all later calls will use this "
                                                  "html file instead of fetching new news")
def main(only_new, char_per_line, sep_char, from_str, subject_str, to_mail,
         server_username, server_password, smtp_ssl, send, debug):
    """Scraps https://www.dr.dk/nyheder for news, rewrite the news in size aware format and send a compressed version to the given email
    7zip can then be used to open the compressed file there contains a news.txt file
    """
    sep_string = sep_char * char_per_line

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
        time_el = news.find_next("div", {"class": time_class_name})
        time_text = time_el.text

        heading_el = news.find_next("div", {"class": heading_class_name})
        heading_text = heading_el.text

        if i == 0:
            write_heading(last_headline_file, heading_text, encoding)
        if only_new and last_headline is not None and heading_text == last_headline:
            break

        body_el = news.find_next("div", {"class": body_class_name})
        body_text = body_el.text
        body_text = remove_foto(body_text)

        news_to_save.append([time_text, heading_text, body_text])

    if len(news_to_save):
        print(f"New news was found. ({len(news_to_save)})")
        with codecs.open(file_out, "w", encoding) as fp:
            for i, (time, heading, body) in enumerate(news_to_save):
                save_text = ""
                save_text += insert_newlines(f"{time}: {heading}\n\n", char_per_line) + "\n\n"
                save_text += insert_newlines(body, char_per_line) + "\n"
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
                print("Success:", filters_name, "with a size of", file_size)
                file_sizes.append(file_size)
                files.append(file_name)

        min_size_file_idx = np.argmin(file_sizes)
        best_file = files[min_size_file_idx]
        print("The best compressing method was:", os.path.basename(best_file),
              "with a size of ", file_sizes[min_size_file_idx])

        # Send email with file
        print(f"Sending mail to {to_mail}")
        if send:
            send_mail(from_str, to_mail, server_username, server_password, subject_str,
                      body="News from DR nyheder. Uncompress with 7zip",
                      file_attachments=[best_file], smtp_ssl=smtp_ssl)

    else:
        print("No new news was found.")


if __name__ == '__main__':
    main()
