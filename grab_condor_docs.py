#!/usr/bin/env python

import bs4
import requests
import os
import urlparse
import re
import json
from itertools import takewhile

# replace with dict?
class CondorCmd(object):
    """Holds info about a Condor command"""
    
    def __init__(self, name, brief=None, synopsis=None, 
                 description=None, options=None, url=None):
        """
        name: str
            command name
        brief: str
            Brief summary of what command does.
        synopsis: str
            Brief summary of command usage.
        description: str
            Full info about the command.
        options: str
            Flags and values that the command can use.
        url: str
            URL with info about the command. 
            Should be the full page URL. 
            e.g. 'https://research.cs.wisc.edu/htcondor/manual/current/condor_q.html'
            instead of 'condor_q.html'
        """
        self.name = name
        self.brief = brief
        self.synopsis = synopsis
        self.description = description
        self.options = options
        self.url = url       


def check_version_str(version):
    """Check if version string is either "current" or the form vX.Y.Z"""
    if not version.startswith('v') and version != 'current':
        version = 'v%s' % version
    return version


def get_linked_versions(version='current'):
    """Use a version of the manual to list previous HTCondor releases based on
    Version History chapter.

    Returns a list of strings of HTCondor versions. If no list is available,
    returns an empty list.

    version: str
        HTCondor release version. 'current' is the latest release.
    """
    version = check_version_str(version)
    chapters = [10, 9, 8]
    version_page = 'https://research.cs.wisc.edu/htcondor/manual/{ver}/{chapter}_Version_History.html'
    r = requests.get(version_page.format(ver=version, chapter=chapters[0]))
    if r.status_code == 404:
        # Try different chapter numbers, as it changes for different versions
        i = 1
        while r.status_code == 404 and i < len(chapters):
            r = requests.get(version_page.format(ver=version, chapter=chapters[i]))
            i += 1
    if r.status_code == 404:
        return []
    soup_vers = bs4.BeautifulSoup(r.text, 'lxml')
    versions = [x.text.replace('Version ', '')
                for x in soup_vers.find_all('a')
                if x.text.startswith('Version')]
    return versions


def check_manual_exists(version='current'):
    """Check that online manual exists for a given version of HTCondor manual.

    Returns bool.
    """
    version = check_version_str(version)
    r = requests.get('https://research.cs.wisc.edu/htcondor/manual/%s/' % version)
    return r.status_code == requests.codes.ok


def sort_versions(version_list, reverse=True):
    """Utility function to sort list of HTCondor version numbers.

    reverse: bool
        If True, sorts by descending order.
    """
    # first chop off any starting 'v'
    version_list = [x.replace('v', '') for x in version_list]

    # sort by 3rd index first (descending), then minor release num then major
    sorted_list = sorted(version_list, key=lambda x: int(x.split('.')[2]), reverse=reverse)
    sorted_list.sort(key=lambda x: int(x.split('.')[1]), reverse=reverse)
    sorted_list.sort(key=lambda x: int(x.split('.')[0]), reverse=reverse)
    return sorted_list


def get_versions(start='current'):
    """Get all previous versions of HTCondor for which there is an online manual.
    Version strings are sorted, with the newest release first.

    Can optionally choose the starting version. If not specified, starts from
    the latest release.
    """
    start = check_version_str(start)
    versions = get_linked_versions(start)

    results = versions[:]
    while results:
        results = get_linked_versions(results[-1])
        print results
        if results:
            versions.extend(results)

    versions = [x for x in set(versions) if check_manual_exists(x)]
    return sort_versions(versions, reverse=True)


def grab_command_list(index_url):
    """Scrape the list of commands from the index webpage"""
    r = requests.get(index_url)
    r.raise_for_status()
    soup = bs4.BeautifulSoup(r.text, 'lxml')
    main_list = soup.ul
    commands = []
    base_url = os.path.dirname(index_url)
    for item in main_list.children:
        if not isinstance(item, bs4.element.Tag):
            continue
        cmd_tag = item.find_all('a')[0]
        name = cmd_tag.string
        page = cmd_tag.attrs['href']
        c = CondorCmd(name, url=os.path.join(base_url, page))
        commands.append(c)
    return commands


def grab_cmd_info(cmd):
    """Grab from the URL information about the command
    including synopsis, description, options, etc.

    Returns a dict of information.

    cmd: str
        Condor command object.
    """
    r = requests.get(cmd.url)
    r.raise_for_status()
    soup_cmd = bs4.BeautifulSoup(r.text, 'lxml')

    # get body text, sanitise
    body = soup_cmd.body.text
    body = re.sub(r'\n\n+', '\n', body) # get rid of extra lines
    body = re.sub(r'\n[\s\xa0]+', '\n', body) # remove leading spaces
    body = re.sub(r'[\s\xa0]+\n', '\n', body) # remove trailing spaces

    info = {}

    # get brief description
    p_brief = re.compile(cmd.name+r'\n([\d\w.()-/ \'\n]*)\nSynopsis', re.IGNORECASE)
    brief_search = p_brief.search(body)
    if brief_search:
        info['brief'] = brief_search.group(1).replace('\n', ' ')
    else:
        print 'No brief info for', cmd.name
        info['brief'] = None

    # get synopsis
    p_synopsis = re.compile(r'Synopsis\n('+cmd.name+r'.+)[\n ]+Description', re.IGNORECASE | re.DOTALL)
    synopsis_search = p_synopsis.search(body)
    if synopsis_search:
        synopsis_raw = synopsis_search.group(1)
        info['synopsis'] = [i.replace('\n', ' ').strip() for i in synopsis_raw.split(cmd.name) if i]
    else:
        print 'No synopsis info for', cmd.name
        info['synopsis'] = None

    # get description
#     p_desc = re.compile(r'Description\n(.*?)\nOptions', re.IGNORECASE | re.DOTALL)
    return info


def grab_condor_docs(version='current'):
    # get list of all commands
    commands = grab_command_list('https://research.cs.wisc.edu/htcondor/manual/%s/11_Command_Reference.html' % version)

    # parse each command webpage into dict
    for cmd in commands:
        print cmd.name, cmd.url
        if cmd.name != 'condor_submit_dag':
            continue
        info_dict = grab_cmd_info(cmd)
        cmd.brief = info_dict['brief']
        cmd.synopsis = info_dict['synopsis']

    # save as JSON
    with open('dump.json', 'w') as json_file:
        json_file.write(json.JSONEncoder(indent=1).encode([c.__dict__ for c in commands]))


if __name__ == "__main__":
    # get all versions of docs
    # versions = get_versions(start='current')
    # print versions

    # scrape and save info for each version
    # for v in versions:
    grab_condor_docs()