import requests
from bs4 import BeautifulSoup

def fetch_nikkei_index(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    tables = soup.find_all("table", class_="cmn-table_style1")
    if not tables:
        return None

    all_index_data = []

    for table in tables:
        rows = table.find_all("tr")

        index_data = []

        for row in rows:
            header = row.find("th")
            columns = row.find_all("td")
            if header and len(columns) >= 2:
                index_name = header.text.strip()
                value = columns[0].text.strip()
                change = columns[1].text.strip()
                index_data.append(f"{index_name}: {value} ({change})")

        all_index_data.append("\n".join(index_data))

    return "\n\n".join(all_index_data)
