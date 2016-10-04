import xml.etree.ElementTree as ET

class Restaurant(object):
    def __init__(self, page):        
        information = page.find('div', id='rstdata-wrap').find('table')
        self.url = page.find(id='rdnavi2-top').find('a')['href']

        string = lambda s: ''.join(s.stripped_strings)
        self.name = string(information.find(property='v:name'))
        self.category = string(information.find(property='v:category'))
        self.address = string(information.find(rel='v:address'))

        from urllib.parse import urlparse, parse_qs as urldecode
        m = information.find('div', 'rst-map').find('img')
        location = urldecode(urlparse(m['data-original']).query)['center']
        location = tuple([s.strip() for s in location[0].split(',')] + ['0.0'])
        self.location = (location[1], location[0], location[2])

        rows = information.find_all('tr')
        rows = {string(row.find('th')): string(row.find('td')) for row in rows}

        self.closed_comment = rows.get('定休日')

        self.thumbnail_urls = [img['src'] for img in page.find('ul', 'rstdtl-top-photo__list').find_all('img', height='150')]
        

def main():
    import yaml

    with open('example.yaml', 'r') as f:
        data = yaml.load(f)

    restaurants = load_restaurants(data['urls'])

    kml = ET.Element('kml', {'xmlns': 'http://www.opengis.net/kml/2.2'})
    document = ET.SubElement(kml, 'Document')
    name = ET.SubElement(document, 'name')
    name.text = data.get('name', '')
    description = ET.SubElement(document, 'description')
    description.text = data.get('description', '')

    style_name = insert_basic_style(document)
    folder = ET.SubElement(document, 'Folder')
    for restaurant in restaurants:
        placemark = ET.SubElement(folder, 'Placemark')
        name = ET.SubElement(placemark, 'name')
        name.text = build_name(restaurant)
        description = ET.SubElement(placemark, 'description')
        description.text = build_description(restaurant)
        style_url = ET.SubElement(placemark, 'styleUrl')
        style_url.text = style_name
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


def load_restaurants(urls):
    pages = load_pages(urls)
    return [Restaurant(pages[url]) for url in urls]


def load_pages(urls):
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(load_page, url) for url in urls]
        return dict([future.result() for future in concurrent.futures.as_completed(futures)])


def load_page(url):
    from urllib.request import urlopen
    from bs4 import BeautifulSoup

    with urlopen(url, timeout=10) as f:
        return (url, BeautifulSoup(f.read().decode('utf-8'), 'html5lib'))


def build_name(restaurant):
    return translate(restaurant.category) + ' - ' + restaurant.name


def build_description(restaurant):
    return restaurant.closed_comment + '<br>' + restaurant.url


def insert_basic_style(document):
    style_map_id = 'icon-1899-0288D1'
    normal_style_id = style_map_id + '-normal'
    highlight_style_id = style_map_id + '-highlight'

    for style_id in (normal_style_id, highlight_style_id):
        style = ET.SubElement(document, 'Style', {'id': style_id})
        iconStyle = ET.SubElement(style, 'IconStyle')
        ET.SubElement(iconStyle, 'color').text = 'ffD18802'
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

    return '#' + style_map_id


def translate(key):
    return {
        '寿司': '스시',
        'ラーメン': '라멘',
        '魚介料理・海鮮料理': '해산물',
        '海鮮丼': '해산물',
        'うなぎ': '장어',
        'おでん': '오뎅',
        'とんかつ': '돈까스',
        'そば': '소바',
        '汁なし担々麺': '국물 없는 탄탄면',
        '西洋各国料理（その他）': '서양요리',
        'ジンギスカン': '징기스칸',
    }[key]


if __name__ == '__main__':
    main()