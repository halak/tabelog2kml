import click
import json
import xml.etree.ElementTree as ET
from collections import defaultdict, namedtuple

Icons = {
    'default': '1577',
    'fastfood': '1567',
    'noodle': '1640',
    'sushi': '1835',
    'beef': '1553',
    'chicken': '1545',
    'beer': '1879',
    'cafe': '1534',
    'dessert': '1607',
    'cocktail': '1517',
    'fish': '1573',
}

Colors = {
    'default': '0288D1',
    'red': 'A52714',
    'orange': 'F9A825',
    'yellow': 'FFD600',
    'green': '097138',
    'blue': '0288D1',
    'purple': '673AB7',
    'black': '000000',
    'brown': '4E342E',
    'gray': '757575',
}

class Restaurant(object):
    CategoryDescription = namedtuple('CategoryDescription', ['key', 'icon', 'translated_text'])
    categories = None

    def __init__(self, page, userdata):
        information = page.find('div', {'class': 'rstinfo-table'}).find('table')
        self.url = page.find('link', {'rel': 'canonical'})['href']

        string = lambda s: ''.join(s.stripped_strings)

        rows = information.find_all('tr')
        rows = {string(row.find('th')): string(row.find('td')) for row in rows}

        self.name = rows.get('店名')
        self.categories = [Restaurant.get_category(s.strip()) for s in rows.get('ジャンル').replace('、', ',').split(',')]

        from urllib.parse import urlparse, parse_qs as urldecode
        m = information.find('div', {'class': 'rstinfo-table__map'}).find('img')
        location = urldecode(urlparse(m['data-original']).query)['center']
        location = tuple([s.strip() for s in location[0].split(',')] + ['0.0'])
        self.location = (location[1], location[0], location[2])

        self.closed_comment = rows.get('定休日')

        self.thumbnail_urls = [img['src'] for img in page.find('ul', 'rstdtl-top-postphoto__list').find_all('img')]
        self.comment = userdata.get('comment', '')
        self.icon = userdata.get('icon', self.primary_category.icon if self.primary_category else 'default')
        self.color = userdata.get('color', 'default')

    @property
    def primary_category(self):
        if len(self.categories) > 0:
            for category in self.categories:
                if category.key not in ('その他',):
                    return category
            else:
                return self.categories[0]
        else:
            return None

    @classmethod
    def get_category(cls, key):
        if cls.categories is None:
            cls.categories = cls.build_categories('category.csv')

        return cls.categories.get(key, cls.CategoryDescription(key, 'default', key))

    @classmethod
    def build_categories(cls, path):
        categories = {}
        import csv
        with open(path, encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                key, icon, translated = row
                categories[key] = cls.CategoryDescription(key, icon, translated)
        return categories


def main():
    import yaml

    with open('example.yaml', 'r', encoding='utf-8') as f:
        data = yaml.load(f)

    restaurants = load_restaurants(data['restaurants'])

    kml = ET.Element('kml', {'xmlns': 'http://www.opengis.net/kml/2.2'})
    document = ET.SubElement(kml, 'Document')
    name = ET.SubElement(document, 'name')
    name.text = data.get('name', '')
    description = ET.SubElement(document, 'description')
    description.text = data.get('description', '')

    for icon in Icons.values():
        for color in Colors.values():
            insert_style(document, icon, color)

    folder = ET.SubElement(document, 'Folder')
    for restaurant in restaurants:
        placemark = ET.SubElement(folder, 'Placemark')
        name = ET.SubElement(placemark, 'name')
        name.text = build_name(restaurant)
        description = ET.SubElement(placemark, 'description')
        description.text = build_description(restaurant)
        style_url = ET.SubElement(placemark, 'styleUrl')
        style_url.text = build_style_map_id(restaurant)
        point = ET.SubElement(placemark, 'Point')
        coordinates = ET.SubElement(point, 'coordinates')
        coordinates.text = ','.join(restaurant.location)
        extended_data = ET.SubElement(placemark, 'ExtendedData')
        data = ET.SubElement(extended_data, 'Data', {'name': 'gx_media_links'})
        ET.SubElement(data, 'value').text = ' '.join(restaurant.thumbnail_urls[:5])

    from xml.dom import minidom
    xml = minidom.parseString(ET.tostring(kml)).toprettyxml(indent='\t', encoding='utf-8')
    with open('example.kml', 'wb') as f:
        f.write(xml)


def load_restaurants(restaurants):
    pages = load_pages([restaurant['url'] for restaurant in restaurants])
    return [Restaurant(pages[restaurant['url']], restaurant) for restaurant in restaurants]


def load_pages(urls):
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_page, url) for url in urls]
        with click.progressbar(length=len(futures), label='fetching...') as bar:
            pages = {}
            count = 0
            for future in concurrent.futures.as_completed(futures):
                url, page = future.result()
                pages[url] = page
                bar.update(1)

            return pages


def load_page(url):
    import time
    from requests import get
    from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout
    from requests.packages.urllib3.exceptions import ReadTimeoutError

    retry = 0
    while True:
        try:
            response = get(url, timeout=10.0)
            break
        except (ChunkedEncodingError, ConnectionError, ReadTimeout, ReadTimeoutError):
            retry += 1

        time.sleep(min(retry * 0.5, 20))

    from bs4 import BeautifulSoup
    return (url, BeautifulSoup(response.text, 'html5lib'))


def build_name(restaurant):
    primary_category = restaurant.primary_category
    if primary_category:
        return primary_category.translated_text + ' - ' + restaurant.name
    else:
        return restaurant.name


def build_description(restaurant):
    s = restaurant.closed_comment + '<br>' + restaurant.url

    if len(restaurant.comment) > 0:
        s = s + '<br>' + restaurant.comment

    return s


def build_style_map_id(restaurant):
    icon = Icons.get(restaurant.icon, Icons['default'])
    color = Colors.get(restaurant.color, Colors['default'])
    return f'#icon-{icon}-{color}'


def insert_style(document, icon, color):
    style_map_id = f'icon-{icon}-{color}'
    normal_style_id = style_map_id + '-normal'
    highlight_style_id = style_map_id + '-highlight'

    for style_id in (normal_style_id, highlight_style_id):
        style = ET.SubElement(document, 'Style', {'id': style_id})
        iconStyle = ET.SubElement(style, 'IconStyle')
        ET.SubElement(iconStyle, 'color').text = f'ff{color[4:6]}{color[2:4]}{color[0:2]}'
        ET.SubElement(iconStyle, 'scale').text = '1.0'
        icon = ET.SubElement(iconStyle, 'Icon')
        ET.SubElement(icon, 'href').text = 'http://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png'
        labelStyle = ET.SubElement(style, 'LabelStyle')
        ET.SubElement(labelStyle, 'scale').text = '0.0'

    style_map = ET.SubElement(document, 'StyleMap', {'id': style_map_id})
    pair = ET.SubElement(style_map, 'Pair')
    ET.SubElement(pair, 'Key').text = 'normal'
    ET.SubElement(pair, 'styleUrl').text = '#' + normal_style_id
    pair = ET.SubElement(style_map, 'Pair')
    ET.SubElement(pair, 'Key').text = 'highlight'
    ET.SubElement(pair, 'styleUrl').text = '#' + highlight_style_id


if __name__ == '__main__':
    main()