import re
import time
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup


class SteamSearchGame:

    def __init__(self, game_name, removed, source="Steam"):
        self.game_name = self.game_name_searchable(game_name)
        if removed:
            self.url_banned = 'https://steam-tracker.com/apps/banned'
            self.url_delisted = 'https://steam-tracker.com/apps/delisted'
            self.appid = self.appidremoved(self.url_banned)
            if self.appid == 0:
                self.appid = self.appidremoved(self.url_delisted)
        else:
            self.url = 'https://store.steampowered.com/search/?term=' + self.game_name + '&ignore_preferences=1'
            while True:
                try:
                    self.gamePage = BeautifulSoup(requests.get(self.url, timeout=30).text, "html.parser")
                    break
                except requests.exceptions.RequestException:
                    print("Steam store timeout: sleep for 30 seconds and try again")
                    time.sleep(30)
            self.appid = self.appid(removed, source)

    @classmethod
    def game_name_searchable(cls, game_name):
        # Put a space after a dash otherwise the word is excluded from search
        game_name = re.sub(r'^-*', '', game_name.strip())
        game_name = re.sub("dlc", '', game_name, flags=re.IGNORECASE)
        game_name = game_name.replace("  ", " ")
        game_name = game_name.strip()
        return re.sub(r'-(\w)', r'- \1', game_name)

    @classmethod
    def write_roman(cls, num):
        # Change number into roman numeral
        if num <= 999:
            roman = OrderedDict()
            roman[900] = "cm"
            roman[500] = "d"
            roman[400] = "cd"
            roman[100] = "c"
            roman[90] = "xc"
            roman[50] = "l"
            roman[40] = "xl"
            roman[10] = "x"
            roman[9] = "ix"
            roman[5] = "v"
            roman[4] = "iv"
            roman[1] = "i"

            def roman_num(num):
                for r in roman.keys():
                    x, y = divmod(num, r)
                    yield roman[r] * x
                    num -= (r * x)
                    if num <= 0:
                        break

            return "".join([a for a in roman_num(num)])
        return str(num)

    @classmethod
    def write_num(cls, roman_num):
        # Change roman numeral into number
        if roman_num != "":
            roman = OrderedDict()
            roman["i"] = 1
            roman["v"] = 5
            roman["x"] = 10
            roman["l"] = 50
            roman["c"] = 100
            roman["d"] = 500
            roman["m"] = 1000
            roman["iv"] = 4
            roman["ix"] = 9
            roman["xl"] = 40
            roman["xc"] = 90
            roman["cd"] = 400
            roman["cm"] = 900

            pos = 0
            num = 0
            while pos < len(roman_num):
                if pos+1 < len(roman_num) and roman_num[pos:pos+2] in roman:
                    num += roman[roman_num[pos:pos+2]]
                    pos += 2
                else:
                    num += roman[roman_num[pos]]
                    pos += 1
            return str(num)
        return roman_num

    def appid(self, removed, source):
        if removed:
            games = self.gamePage.select('tr[data-type="app"]')
        else:
            search_data = self.gamePage.find("div", id="search_result_container")
            games = search_data.find_all('a', {'class': 'search_result_row'})
        appid = 0
        game_name = ""

        def repl_roman(match):
            return self.write_roman(int(match.group(0)))

        def repl_num(match):
            return self.write_num(match.group(0))

        for game in games:
            # Find search result with the same name as target and get appid
            if removed:
                get_title = game.find('a').text.strip()
            else:
                get_title = game.find('span', {"class": "title"}).text
            # Get rid of commas to avoid number issues
            get_title = get_title.replace(",", "")
            game_name = self.game_name.replace(",", "")
            # Get rid of all non-alphanumerics and convert to lowercase
            get_title = re.sub(r'[\W_]+', u' ', get_title, flags=re.UNICODE).lower()
            game_name = re.sub(r'[\W_]+', u' ', game_name, flags=re.UNICODE).lower()
            # Some dlc have the word DLC in the name
            get_title = get_title.replace("dlc", "").replace("  ", " ")
            game_name = game_name.replace("dlc", "").replace("  ", " ")

            if (
                # exactly the same
                get_title == game_name
                # words are the same but different order
                or set(get_title.split(" ")) == set(game_name.split(" "))
                # typo in target
                or sorted(get_title.replace(" ", "")) == sorted(game_name.replace(" ", ""))
            ):
                if removed:
                    appid = game['data-id']
                else:
                    appid = game['data-ds-appid']
                break
            # Check for Roman numeral variant if posted with number
            game_name_roman = re.compile(r"\b\d+\b").sub(repl_roman, game_name)
            game_name_number = re.compile(r"\b(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})\b").sub(repl_num, game_name)
            if (
                get_title == game_name_roman
                or set(get_title.split(" ")) == set(game_name_roman.split(" "))
                or sorted(get_title.replace(" ", "")) == sorted(game_name_roman.replace(" ", ""))
                or get_title == game_name_number
                or set(get_title.split(" ")) == set(game_name_number.split(" "))
                or sorted(get_title.replace(" ", "")) == sorted(game_name_number.replace(" ", ""))
            ):
                if removed:
                    appid = game['data-id']
                else:
                    appid = game['data-ds-appid']
                break
        if removed and appid == 0:
            # Try backup site
            appid = self.appidbackup(self.urlbackup_banned)
            if appid == 0:
                self.appid = self.appidbackup(self.urlbackup_delisted)
        if not removed and appid == 0 and "random" not in game_name and source == "Steam":
            # If nothing found, try again but allow one word to be missing from target
            for game in games:
                # game_name is used from previous loop
                get_title = game.find('span', {"class": "title"}).text
                get_title = get_title.replace(",", "")
                get_title = re.sub(r'[\W_]+', u' ', get_title, flags=re.UNICODE).lower()
                get_title = get_title.replace("dlc", "").replace("  ", " ")
                if len(get_title.split(" ")) <= len(game_name.split(" ")) + 1:
                    if (
                        # target name is fully in search result
                        game_name in get_title
                        # target words are all in search result
                        or all(x in get_title for x in game_name.split(" "))
                    ):
                        appid = game['data-ds-appid']
                        break
                # Check for Roman numeral variant if posted with number
                if len(get_title.split(" ")) <= len(game_name_roman.split(" ")) + 1:
                    if (
                        game_name_roman in get_title
                        or all(x in get_title for x in game_name_roman.split(" "))
                        or game_name_number in get_title
                        or all(x in get_title for x in game_name_number.split(" "))
                    ):
                        appid = game['data-ds-appid']
                        break

        return appid

    def appidremoved(self, url):
        try:
            self.gamePage = BeautifulSoup(requests.get(url, timeout=30).text, "html.parser")
        except requests.exceptions.RequestException:
            print('removed game backup request timeout')
            return 0
        else:
            # adjust game name if needed
            if "TOTI" in self.game_name:
                self.game_name = self.game_name.replace("TOTI", "Trials of the Illuminati")
            games = self.gamePage.find_all("a", string=re.compile(str(self.game_name.split(" ")[0])))
            appid = 0
            game_name = ""

            def repl_roman(match):
                return self.write_roman(int(match.group(0)))

            def repl_num(match):
                return self.write_num(match.group(0))

            for game in games:
                # Find search result with the same name as target and get appid
                get_title = game.text.strip()
                # Get rid of commas to avoid number issues
                get_title = get_title.replace(",", "")
                game_name = self.game_name.replace(",", "")
                # Get rid of all non-alphanumerics and convert to lowercase
                get_title = re.sub(r'[\W_]+', u' ', get_title, flags=re.UNICODE).lower()
                game_name = re.sub(r'[\W_]+', u' ', game_name, flags=re.UNICODE).lower()
                # Some dlc have the word DLC in the name
                get_title = get_title.replace("dlc", "").replace("  ", " ")
                game_name = game_name.replace("dlc", "").replace("  ", " ")
                if (
                    # exactly the same
                    get_title == game_name
                    # words are the same but different order
                    or set(get_title.split(" ")) == set(game_name.split(" "))
                    # typo in target
                    or sorted(get_title.replace(" ", "")) == sorted(game_name.replace(" ", ""))
                    or ("random" not in game_name and game_name in get_title)
                ):
                    href = game.get('href').split("/")
                    app = href.index("app") + 1
                    appid = href[app]
                    break
                # Check for Roman numeral variant if posted with number
                game_name_roman = re.compile(r"\b\d+\b").sub(repl_roman, game_name)
                game_name_number = re.compile(r"\b(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})\b").sub(repl_num, game_name)
                if (
                    get_title == game_name_roman
                    or set(get_title.split(" ")) == set(game_name_roman.split(" "))
                    or sorted(get_title.replace(" ", "")) == sorted(game_name_roman.replace(" ", ""))
                    or ("random" not in game_name_roman and game_name_roman in get_title)
                    or get_title == game_name_number
                    or set(get_title.split(" ")) == set(game_name_number.split(" "))
                    or sorted(get_title.replace(" ", "")) == sorted(game_name_number.replace(" ", ""))
                    or ("random" not in game_name_number and game_name_number in get_title)
                ):
                    href = game.get('href').split("/")
                    app = href.index("app") + 1
                    appid = href[app]
                    break

            return appid
