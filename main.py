import os
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import functions_framework

TEXTBELT_API_KEY = os.environ.get("TEXTBELT_API_KEY")
ADMIN_PHONE_NUMBER = os.environ.get("ADMIN_PHONE_NUMBER")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


def text_alert(message):
    res = requests.post(
        "https://textbelt.com/text",
        {
            "phone": ADMIN_PHONE_NUMBER,
            "message": message,
            "key": TEXTBELT_API_KEY,
            "sender": "W4H",
        },
        timeout=5000,
    ).json()
    if res["success"] and res["quotaRemaining"] == 1:
        text_alert(
            "W4H Alert: need to purchase more text credits for textbelt.com SMS API"
        )
    return (message, 500)


@functions_framework.http
def main(request):
    try:
        print(f"{datetime.now()}: checking for new data")
        previous_data_source = request.json["latestSuccessfulUpdateSource"]

        # ====== Web Scrape for link to latest available OPeNDAP data ======
        # ------ find latest date ------
        dates_directory = "https://nomads.ncep.noaa.gov/dods/gfs_0p25_1hr"
        dates_source = requests.get(dates_directory, timeout=5000).text
        dates_soup = BeautifulSoup(dates_source, "lxml").body
        date_link_regex = r"^http:\/\/nomads\.ncep\.noaa\.gov(:80)?\/dods\/gfs_0p25_1hr\/gfs\d{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$"
        dates = dates_soup.find_all(href=re.compile(date_link_regex))
        del dates_source
        del dates_soup
        if not dates:
            return text_alert(
                f"W4H Data Pipeline Error: zero dates found at {dates_directory}"
            )
        latest_date = max(dates, key=lambda link: int(link.attrs["href"][-8:]))
        # ------ find latest time ------
        times_directory = latest_date.attrs["href"]
        times_source = requests.get(times_directory, timeout=5000).text
        times_soup = BeautifulSoup(times_source, "lxml").body
        time_link_regex = r"^http:\/\/nomads\.ncep\.noaa\.gov(:80)?\/dods\/gfs_0p25_1hr\/gfs\d{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])\/gfs_0p25_1hr_(00|06|12|18)z\.info$"
        times = times_soup.find_all(href=re.compile(time_link_regex))
        if not times:
            return text_alert(
                f"W4H Data Pipeline Error: found zero times at {times_directory}"
            )
        latest_time = max(times, key=lambda link: int(link.attrs["href"][-8:-6]))
        # ------ get latest data link ------
        data_source = latest_time.attrs["href"][0:-5]

        if data_source != previous_data_source:
            print(f"{datetime.now()}: New data available at {data_source}")
            response = requests.post(
                "https://www.weatherforhumans.com/api/status",
                headers={"Authorization": f"apikey {ADMIN_API_KEY}"},
                json={"latestSuccessfulUpdateSource": data_source},
            )
            if response.status_code != 200:
                return ("Error updating website status", 500)
            # requests.post(
            #     "https://weatherforhumans.com/api/status",
            #     headers={"Authorization": f"apikey: {ADMIN_API_KEY}"},
            #     data={"isUpdating": True},
            # )
            return f"updating from data from {previous_data_source} to data from {data_source}"
        else:
            return f"Already using latest data from {previous_data_source}"
    except Exception as e:
        return (f"Uncaught error: {e}", 500)
