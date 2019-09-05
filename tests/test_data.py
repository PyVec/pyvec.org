import re
import os
import json
from contextlib import contextmanager

import pytest
import requests
import jsonschema

from pyvecorg.data import (load_data, select_language,
                           DATA_PATH, SUPPORTED_LANGS)


STATIC_PATH = os.path.join(DATA_PATH, '..', 'static')
RE_MISSING_LANG = re.compile(
    f"'(" +
    '|'.join([re.escape(lang) for lang in SUPPORTED_LANGS]) +
    ")' is a required property"
)
DATA = load_data()

# If you run 'pipenv run build', memebers_list.yml gets generated and it will
# be tested. If you don't have the file present, the relevant tests will be
# skipped
DATA_MEMBERS_LIST = DATA.get('members_list', {}).get('entries', [])


def is_working_link(url):
    response = requests.head(url)  # this can raise connection-related errors

    # if it's 5xx, it kinda means the link leads to an existing page, only
    # the page is unavailable at the moment because of high load or internal
    # error - we don't need to fail tests of pyvec.org because of that
    if str(response.status_code)[0] == '4':
        raise AssertionError(f'URL {url} returns HTTP {response.status_code}')


@contextmanager
def transform_missing_lang_exc():
    try:
        yield
    except jsonschema.exceptions.ValidationError as top_level_exc:
        for exc in top_level_exc.context or []:
            match = RE_MISSING_LANG.search(exc.message)
            if match:
                raise AssertionError(
                    f"Missing '{match.group(1)}' translation "
                    f"for:\n\n{exc.instance}"
                ) from None
        raise


def test_data_not_empty():
    assert DATA


@pytest.mark.parametrize('section_name,section', DATA.items())
def test_data_section_is_valid(section_name, section):
    schema_file = os.path.join(DATA_PATH, f'{section_name}_schema.json')
    with open(schema_file) as f:
        schema = json.load(f)

    resolver = jsonschema.RefResolver(base_uri=f'file://{DATA_PATH}/',
                                      referrer=schema)
    with transform_missing_lang_exc():
        jsonschema.validate(section, schema, resolver=resolver)


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('email')
])
def test_data_member_with_email_is_valid(member):
    assert '@' in member['email']


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('linkedin')
])
def test_data_member_with_linkedin_is_valid(member):
    assert not member['linkedin'].startswith('http')


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('github')
])
def test_data_member_with_github_is_valid(member):
    assert not member['github'].startswith('http')


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('twitter')
])
def test_data_member_with_twitter_is_valid(member):
    assert not member['twitter'].startswith('http')
    assert not member['twitter'].startswith('@')


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('role')
])
def test_data_member_with_role_is_valid(member):
    assert member['role'] in list(DATA['members']['roles'].keys())


@pytest.mark.parametrize('member', [
    member for member in DATA_MEMBERS_LIST
    if member.get('avatar')
])
def test_data_member_with_avatar_is_valid(member):
    assert member['avatar'] in ('github', 'twitter', 'email')


@pytest.mark.parametrize('logo', frozenset(
    entry['logo'] for entry
    in (
        DATA['partners']['entries'] +
        DATA['projects']['entries'] +
        DATA['supporters']['entries']
    )
    if entry.get('logo')
))
def test_data_entry_has_existing_logo(logo):
    assert os.path.isfile(os.path.join(STATIC_PATH, logo))


@pytest.mark.parametrize('url', frozenset(
    entry['url'] for entry
    in (
        DATA['partners']['entries'] +
        DATA['profiles']['entries'] +
        DATA['projects']['entries'] +
        DATA['supporters']['entries']
    )
    if entry.get('url')
))
def test_data_entry_has_valid_url(url):
    is_working_link(url)


@pytest.mark.parametrize('photo', [
    project['photo'] for project in DATA['projects']['entries']
    if project.get('photo')
])
def test_data_project_has_valid_photo(photo):
    with open(os.path.join(STATIC_PATH, 'main.css')) as f:
        css = f.read()
    assert f'.project-header-{photo}' in css

    filename = os.path.join(STATIC_PATH, 'img', 'projects', f'{photo}.jpg')
    assert os.path.isfile(filename)


@pytest.mark.parametrize('pyvec_help', [
    project['pyvec_help'] for project in DATA['projects']['entries']
    if project.get('pyvec_help')
])
def test_data_project_has_valid_pyvec_help(pyvec_help):
    available_values = frozenset(DATA['projects']['pyvec_help'].keys())
    assert frozenset(pyvec_help) <= available_values


@pytest.mark.parametrize('lang,expected', [
    ('cs', 'česky'),
    ('en', 'anglicky'),
])
def test_select_language(lang, expected):
    data_in = {'deep': {'nested': [{'key': {
        'cs': 'česky',
        'en': 'anglicky',
    }}]}}
    data_out = {'deep': {'nested': [{'key': expected}]}}
    assert select_language(data_in, lang) == data_out


def test_select_language_unsupported():
    data_in = {'deep': {'nested': [{'key': {
        'cs': 'česky',
        'en': 'anglicky',
    }}]}}
    with pytest.raises(ValueError):
        assert select_language(data_in, 'pl')


def test_select_language_missing():
    data_in = {'deep': {'nested': [{'key': {
        'cs': 'česky',
    }}]}}
    data_out = {'deep': {'nested': [{'key': None}]}}
    assert select_language(data_in, 'en') == data_out
