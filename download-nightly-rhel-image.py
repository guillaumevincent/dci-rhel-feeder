import configparser

from lxml import html
import requests


def get_config(url):
    config_parser = configparser.RawConfigParser()
    config_parser.read_string(requests.get(url).text)
    return dict(config_parser[config_parser.sections()[0]])


def get_latest_qcow2_image_url(config):
    arch = 'x86_64'
    repo = config['repo'].split(',')[-1]
    repo_url = repo.replace('$arch/os', '%s/images/' % arch)

    latest_rhel_page = requests.get(repo_url)
    tree = html.fromstring(latest_rhel_page.content)
    for link in tree.xpath('//body//a/@href'):
        if link.endswith('.x86_64.qcow2'):
            return '%s%s' % (repo_url, link)


def download_file(url):
    file_path = url.split('/')[-1]
    r = requests.get(url, stream=True)
    with open(file_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    return file_path


config_file_url = 'http://download-node-02.eng.bos.redhat.com/nightly/latest-RHEL-7/work/image-build/Server/raw-xz_rhel-server-ec2_x86_64.cfg'
config = get_config(config_file_url)
qcow2_url = get_latest_qcow2_image_url(config)
file_path = download_file(qcow2_url)

