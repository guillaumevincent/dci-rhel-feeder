import ConfigParser
import hashlib
import io

import os

import requests
import sys
from dciauth.signature import Signature
from dciauth.request import AuthRequest
from lxml import html

from log import debug, error

DCI_CLIENT_ID = os.getenv('DCI_CLIENT_ID')
DCI_API_SECRET = os.getenv('DCI_API_SECRET')
DCI_CS_URL = os.getenv('DCI_CS_URL')


def get_url(endpoint):
    return '%s/api/v1/%s' % (DCI_CS_URL, endpoint)


def get(endpoint, params={}):
    url = '/api/v1/%s' % endpoint
    r = AuthRequest(endpoint=url, params=params)
    headers = Signature(r).generate_headers('feeder', DCI_CLIENT_ID, DCI_API_SECRET)
    return requests.get(url='%s%s' % (DCI_CS_URL, url), params=params, headers=headers)


def post(endpoint, payload, params={}):
    url = '/api/v1/%s' % endpoint
    r = AuthRequest(method='POST', endpoint=url, payload=payload, params=params)
    headers = Signature(r).generate_headers('feeder', DCI_CLIENT_ID, DCI_API_SECRET)
    return requests.post(url='%s%s' % (DCI_CS_URL, url), headers=headers, json=payload)


def delete(endpoint, data):
    url = '/api/v1/%s' % endpoint
    r = AuthRequest(endpoint=url)
    headers = Signature(r).generate_headers('feeder', DCI_CLIENT_ID, DCI_API_SECRET)
    headers['etag'] = data['etag']
    return requests.delete(url='%s%s' % (DCI_CS_URL, url), headers=headers)


def upload_file(component, file_name):
    url = '/api/v1/components/%s/files' % component['id']
    debug('upload %s on %s%s' % (file_name, DCI_CS_URL, url))
    r = AuthRequest(method='POST', endpoint=url)
    headers = Signature(r).generate_headers('feeder', DCI_CLIENT_ID, DCI_API_SECRET)
    r = requests.post(url='%s%s' % (DCI_CS_URL, url), headers=headers, data=open(file_name, 'rb'))
    debug(r.text)


def get_config(url):
    debug('read config from %s' % url)
    config_parser = ConfigParser.ConfigParser()
    content = requests.get(url).text.encode('utf-8')
    config_parser.readfp(io.BytesIO(content))
    first_section = config_parser.sections()[0]
    return dict(config_parser.items(first_section))


def get_latest_qcow2_image_url(config):
    arch = 'x86_64'
    repo = config['repo'].split(',')[-1]
    repo_url = repo.replace('$arch/os', '%s/images/' % arch)
    latest_rhel_page = requests.get(repo_url)
    tree = html.fromstring(latest_rhel_page.content)
    for link in tree.xpath('//body//a/@href'):
        if link.endswith('.x86_64.qcow2'):
            latest_qcow2_image_url = '%s%s' % (repo_url, link)
            debug('get_latest_qcow2_image_url: %s' % latest_qcow2_image_url)
            return latest_qcow2_image_url


def download_file(url, file_name):
    debug('download file: %s (%s)' % (file_name, url))
    r = requests.get(url, stream=True)
    with open(file_name, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    return file_name


def get_product(label):
    products = get('products').json()['products']
    for product in products:
        if product['label'] == label:
            debug('get_product: %s' % product)
            return product


def get_or_create_topic(product, topic_name, component_types):
    topics = get('topics', {'where': 'name:%s' % topic_name}).json()['topics']
    if len(topics) == 0:
        created_topic = post('topics', {
            'name': topic_name,
            'component_types': component_types,
            'product_id': product['id'],
        }).json()['topic']
        debug('create topic: %s' % created_topic)
        return created_topic
    topic = topics[0]
    debug('get topic: %s' % topic)
    return topic


def get_my_team_id():
    team_id = get('identity').json()['identity']['team_id']
    debug('team id: %s' % team_id)
    return team_id


def associate_topic_team(topic, team_id):
    topic_id = topic['id']
    post('topics/%s/teams' % topic_id, {'team_id': team_id})


def get_or_create_component(topic, component_name, type, url):
    debug('get component %s for topic %s' % (component_name, topic))
    topic_id = topic['id']
    params = {'embed': 'files', 'where': 'name:%s' % component_name}
    components = get('topics/%s/components' % topic_id, params).json()['components']
    if len(components) == 0:
        created_component = post('components', {
            'name': component_name,
            'type': type,
            'url': url,
            'topic_id': topic_id,
            'export_control': True,
            'state': 'active'
        }).json()['component']
        debug('create component: %s' % created_component)
        return created_component
    component = components[0]
    debug('get component: %s' % component)
    return component


def md5sum(file_name):
    hash_md5 = hashlib.md5()
    with open(file_name, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def component_file_is_not_valid(file_name, component):
    if 'files' not in component or len(component['files']) == 0:
        return True
    expected_md5 = md5sum(file_name)
    debug('md5 of %s: %s' % (file_name, expected_md5))
    component_file = component['files'][0]
    md5 = component_file['md5']
    debug('md5 of component file %s: %s' % (component_file['id'], md5))
    return expected_md5 != md5


def delete_all_files_for_component(component):
    debug('delete all files for component %s ' % component)
    if 'files' in component:
        for file in component['files']:
            debug('delete file %s for component %s' % (file['id'], component['id']))
            delete('components/%s/files/%s' % (component['id'], file['id']), file)


def download_and_upload(config_file_url, topic_name):
    config = get_config(config_file_url)
    qcow2_url = get_latest_qcow2_image_url(config)
    file_name = qcow2_url.split('/')[-1]
    if not os.path.exists(file_name):
        file_name = download_file(qcow2_url, file_name)
    upload_on_dci(file_name, qcow2_url, topic_name)
    os.remove(file_name)


def upload_on_dci(file_name, qcow2_url, topic_name):
    product = get_product('RHEL')
    topic = get_or_create_topic(product, topic_name, ['qcow2'])
    team_id = get_my_team_id()
    associate_topic_team(topic, team_id)
    component_name = file_name.replace('.x86_64.qcow2', '')
    component = get_or_create_component(topic, component_name, 'qcow2', qcow2_url)
    iteration = 0
    while component_file_is_not_valid(file_name, component):
        iteration += 1
        debug('component file is not valid')
        delete_all_files_for_component(component)
        upload_file(component, file_name)
        component = get('components/%s' % component['id'], {'embed': 'files'}).json()['component']
        if iteration > 5:
            sys.exit('too many try, cannot upload %s' % file_name)
    debug('upload ok, delete %s' % file_name)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        error('You need to specify the RHEL version. "%s 7" for RHEL 7' % sys.argv[0])
        sys.exit(1)
    configs = {
        "7": 'http://download-node-02.eng.bos.redhat.com/nightly/latest-RHEL-7/work/image-build/Server/raw-xz_rhel-server-ec2_x86_64.cfg',
        "8": 'http://download-node-02.eng.bos.redhat.com/nightly/latest-RHEL-8/work/image-build/Components/qcow2-raw-xz_rhel-guest-image_ppc64le-x86_64.cfg'
    }
    rhel_version = sys.argv[1]
    config_file_url = configs[rhel_version]
    topic_name = 'RHEL-%s' % rhel_version
    download_and_upload(config_file_url, topic_name)
