import requests
from beautifultable import BeautifulTable
from bs4 import BeautifulSoup


def get_weather_detail(weather_url, file_out, maxwidth=999):
    print("Downloading the detail weather report")
    web_request = requests.get(weather_url)
    soup = BeautifulSoup(web_request.content, 'html.parser')

    weather_days = [a.text for a in soup.findAll("h2", {"class": "header-3 heading--color-primary"})]
    weather_tables = soup.findAll("table", {"class": "fluid-table__table"})
    info_tables = []
    for wt in weather_tables:
        btable = BeautifulTable(maxwidth=maxwidth)

        table_head = wt.find("thead")
        btable.columns.header = [a.text for a in table_head.findAll("th", {"class": "fluid-table__cell"})]

        rows = wt.findAll("tr", {"class": "fluid-table__row"})

        table_info = []
        for row in rows:
            row_info = []
            cells = row.findAll("td", {"class": "fluid-table__cell"})
            for ci, cell in enumerate(cells):
                if ci == 1:
                    weather_image = cell.find("img", {"class": "weather-symbol__img"})
                    call_info = weather_image["alt"]
                else:
                    call_info = cell.text
                row_info.append(call_info)
            btable.rows.append(row_info)

        info_tables.append(btable)

    with open(file_out, "w") as fp:
        for wday, wtable in zip(weather_days, info_tables):
            fp.write(wday)
            fp.write("\n")
            fp.write(str(wtable))
            fp.write("\n\n\n")


pass
